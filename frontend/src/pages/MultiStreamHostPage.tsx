import { useEffect, useMemo, useRef, useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { createStreamSession, updateStreamSessionStatus } from '../services/streamService';
import { getParkingLotsByOwner, addCameraToParkingLot, removeCameraFromParkingLot, getParkingLot } from '../services/parkingLotService';
import { 
  getUserESP32Configs,
  type ESP32Config 
} from '../services/esp32ConfigService';
import {
  optimizeVideoQuality,
  optimizeVideoTrack,
  createHighQualityOffer,
} from '../utils/webrtcQuality';

const SIGNALING_URL = 'ws://localhost:3001';
const ICE_SERVERS = [{ urls: 'stun:stun.l.google.com:19302' }];

type HostStatus = 'idle' | 'connecting' | 'streaming' | 'error';

interface HostTileConfig {
  id: string;
  parkingLotId: string;
  cameraId: string;
}

interface HostTileProps extends HostTileConfig {
  ownerId: string;
  onRemove: (id: string) => void;
}

function StreamHostTile({ id, parkingLotId, cameraId, ownerId, onRemove }: HostTileProps) {
  const [status, setStatus] = useState<HostStatus>('idle');
  const [error, setError] = useState<string | null>(null);
  const [fileName, setFileName] = useState<string | null>(null);
  const [hasFile, setHasFile] = useState(false);

  const videoRef = useRef<HTMLVideoElement>(null);
  const sourceVideoRef = useRef<HTMLVideoElement>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const pcRef = useRef<RTCPeerConnection | null>(null);
  const socketRef = useRef<WebSocket | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const videoFileRef = useRef<File | null>(null);
  const streamSessionIdRef = useRef<string | null>(null);
  const hasViewerConnectedRef = useRef<boolean>(false); // Track if viewer ever connected

  const roomId = useMemo(() => {
    if (!parkingLotId.trim() || !cameraId.trim()) return null;
    return `${parkingLotId.trim()}__${cameraId.trim()}`;
  }, [parkingLotId, cameraId]);

  const handleSelectFileClick = () => {
    fileInputRef.current?.click();
  };

  const handleVideoFileSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) {
      setHasFile(false);
      setFileName(null);
      return;
    }

    if (!file.type.startsWith('video/')) {
      setError('File phải là video');
      return;
    }

    videoFileRef.current = file;
    setFileName(file.name);
    setHasFile(true);
    const url = URL.createObjectURL(file);

    if (sourceVideoRef.current) {
      sourceVideoRef.current.src = url;
      sourceVideoRef.current.onloadedmetadata = () => {
        console.log(`[Host ${id}] Video loaded:`, file.name, sourceVideoRef.current?.duration);
      };
    }
  };

  // Tạo MediaStream từ video file (captureStream + fallback canvas)
  const createStreamFromVideo = (): Promise<MediaStream> => {
    return new Promise((resolve, reject) => {
      if (!sourceVideoRef.current) {
        reject(new Error('Video element not found'));
        return;
      }

      const video = sourceVideoRef.current;

      const createStream = () => {
        if (video.videoWidth === 0 || video.videoHeight === 0) {
          video.onloadedmetadata = () => createStream();
          return;
        }

        const videoWithCapture = video as HTMLVideoElement & {
          captureStream?: (frameRate?: number) => MediaStream;
          mozCaptureStream?: (frameRate?: number) => MediaStream;
        };

        const captureFn =
          typeof videoWithCapture.captureStream === 'function'
            ? videoWithCapture.captureStream
            : typeof videoWithCapture.mozCaptureStream === 'function'
              ? videoWithCapture.mozCaptureStream
              : null;

        if (captureFn) {
          console.log(`[Host ${id}] Using captureStream`);
          // Gọi với ngữ cảnh là video element, tránh lỗi "Illegal invocation"
          const stream = captureFn.call(videoWithCapture, 30);

          video.onended = () => {
            console.log(`[Host ${id}] Video ended, looping`);
            video.currentTime = 0;
            video.play().catch((err) => console.error(`[Host ${id}] Replay error:`, err));
          };

          if (video.paused) {
            video
              .play()
              .catch((err) => console.error(`[Host ${id}] Error playing video:`, err));
          }

          resolve(stream);
          return;
        }

        const canvas = document.createElement('canvas');
        const ctx = canvas.getContext('2d');
        if (!ctx) {
          reject(new Error('Canvas context not available'));
          return;
        }

        canvas.width = video.videoWidth || 1280;
        canvas.height = video.videoHeight || 720;
        const stream = canvas.captureStream(30);
        let isDrawing = false;

        const draw = () => {
          if (!isDrawing) return;
          if (video.ended || video.paused) {
            video.currentTime = 0;
            video.play().catch((err) => console.error(`[Host ${id}] Loop play error:`, err));
          }
          if (video.readyState >= 2) {
            ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
          }
          requestAnimationFrame(draw);
        };

        video.onended = () => {
          video.currentTime = 0;
          video.play().catch((err) => console.error(`[Host ${id}] Loop play error:`, err));
        };

        video
          .play()
          .then(() => {
            isDrawing = true;
            draw();
            resolve(stream);
          })
          .catch((err) => reject(new Error(`Failed to play video: ${err.message}`)));
      };

      if (video.readyState < 2) {
        video.onloadedmetadata = () => createStream();
        video.onerror = () => reject(new Error('Failed to load video'));
      } else {
        createStream();
      }
    });
  };

  const connect = async () => {
    try {
      if (!ownerId) {
        setError('Bạn cần đăng nhập để host stream.');
        return;
      }
      if (!roomId) {
        setError('Room ID không hợp lệ');
        return;
      }
      if (!videoFileRef.current) {
        setError('Vui lòng chọn video file');
        return;
      }

      setStatus('connecting');
      setError(null);

      // Chuẩn bị video element
      if (!sourceVideoRef.current) {
        setError('Không tìm thấy video element');
        setStatus('error');
        return;
      }
      sourceVideoRef.current.loop = true;
      sourceVideoRef.current.muted = true;

      const stream = await createStreamFromVideo();
      streamRef.current = stream;

      if (videoRef.current) {
        const preview = videoRef.current;
        // Reset trước khi gán stream mới
        preview.pause();
        // eslint-disable-next-line @typescript-eslint/ban-ts-comment
        // @ts-ignore
        preview.srcObject = null;
        // Gán stream và play
        // eslint-disable-next-line @typescript-eslint/ban-ts-comment
        // @ts-ignore
        preview.srcObject = stream;
        preview.muted = true;
        preview.playsInline = true;
        const playPromise = preview.play();
        if (playPromise !== undefined) {
          playPromise.catch((err) => {
            // AbortError thường vô hại (do browser tự pause khi đổi src)
            if (err?.name !== 'AbortError') {
              console.error(`[Host ${id}] Error playing preview:`, err);
            }
          });
        }
      }

      const pc = new RTCPeerConnection({ iceServers: ICE_SERVERS });
      
      // Thêm tracks và tối ưu video quality
      stream.getTracks().forEach((track) => {
        optimizeVideoTrack(track);
        pc.addTrack(track, stream);
      });
      
      // Tối ưu video quality (bitrate, codec, resolution)
      await optimizeVideoQuality(pc);
      pcRef.current = pc;

      // Log session
      try {
        const result = await createStreamSession({
          ownerId,
          parkingId: parkingLotId.trim(),
          cameraId: cameraId.trim(),
          roomId,
          sourceType: 'video',
          videoFileName: videoFileRef.current?.name ?? null,
        });
        if (result.success && result.id) {
          streamSessionIdRef.current = result.id;
        }
        console.log(`[Host ${id}] Stream session created successfully`);
        
        // Add camera to parking lot cameras array
        console.log(`[Host ${id}] Adding camera to parking lot...`);
        const addCameraResult = await addCameraToParkingLot(parkingLotId.trim(), cameraId.trim());
        if (addCameraResult.success) {
          console.log(`[Host ${id}] ✅ Camera added to parking lot ${parkingLotId.trim()}`);
        } else {
          console.warn(`[Host ${id}] ⚠️ Failed to add camera to parking lot:`, addCameraResult.error);
        }
      } catch (logErr) {
        console.warn(`[Host ${id}] Failed to create stream session:`, logErr);
      }

      const socket = new WebSocket(SIGNALING_URL);
      socketRef.current = socket;

      const connectionTimeout = setTimeout(() => {
        if (socket.readyState !== WebSocket.OPEN) {
          console.error(`[Host ${id}] WebSocket connection timeout`);
          setError('Không thể kết nối đến signaling server');
          setStatus('error');
          socket.close();
        }
      }, 5000);

      socket.onopen = async () => {
        clearTimeout(connectionTimeout);
        console.log(`[Host ${id}] ✅ Connected to signaling server`);
        socket.send(JSON.stringify({ type: 'join', role: 'host', roomId }));

        // Tạo offer với codec preferences chất lượng cao
        const offer = await createHighQualityOffer(pc);
        await pc.setLocalDescription(offer);
        socket.send(JSON.stringify({ type: 'offer', offer }));
        console.log(`[Host ${id}] ✅ High quality offer created and sent`);
        
        // Host đã sẵn sàng stream ngay cả khi chưa có viewer
        setStatus('streaming');
        setError(null); // Clear any previous errors
        if (streamSessionIdRef.current) {
          updateStreamSessionStatus(streamSessionIdRef.current, 'active');
        }
      };

      socket.onmessage = async (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.type === 'answer') {
            await pc.setRemoteDescription(new RTCSessionDescription(data.answer));
            hasViewerConnectedRef.current = true; // Đánh dấu đã có viewer kết nối
            console.log(`[Host ${id}] ✅ Received answer from viewer`);
          } else if (data.type === 'ice') {
            await pc.addIceCandidate(data.candidate);
          }
        } catch (err) {
          console.error(`[Host ${id}] Error handling message:`, err);
        }
      };

      socket.onerror = (err) => {
        clearTimeout(connectionTimeout);
        console.error(`[Host ${id}] WebSocket error:`, err);
        setError('Lỗi kết nối signaling server');
        setStatus('error');
      };

      socket.onclose = () => {
        clearTimeout(connectionTimeout);
        console.log(`[Host ${id}] WebSocket closed`);
        if (status !== 'idle' && status !== 'error') {
          setStatus('idle');
        }
      };

      pc.onicecandidate = (event) => {
        if (event.candidate && socket.readyState === WebSocket.OPEN) {
          socket.send(JSON.stringify({ type: 'ice', candidate: event.candidate }));
        }
      };

      pc.onconnectionstatechange = () => {
        console.log(`[Host ${id}] Connection state:`, pc.connectionState);
        
        // Nếu đã connected với viewer, giữ status streaming
        if (pc.connectionState === 'connected') {
          hasViewerConnectedRef.current = true;
          setStatus('streaming');
          setError(null); // Clear error nếu có
          if (streamSessionIdRef.current) {
            updateStreamSessionStatus(streamSessionIdRef.current, 'active');
          }
        } 
        // Chỉ coi là lỗi nếu đã từng có viewer và bị disconnect
        else if ((pc.connectionState === 'failed' || pc.connectionState === 'disconnected') && hasViewerConnectedRef.current) {
          // Đã từng có viewer nhưng bị mất kết nối - chỉ cảnh báo, không dừng stream
          console.warn(`[Host ${id}] ⚠️ Viewer disconnected, but host continues streaming`);
          setError(null); // Không hiển thị error, host vẫn tiếp tục stream
          // Giữ status = 'streaming' vì host vẫn đang stream, chỉ là không có viewer
        }
        // Nếu chưa có viewer, không làm gì - host vẫn stream bình thường
      };
    } catch (err: any) {
      console.error(`[Host ${id}] Error starting stream:`, err);
      setError(err.message || 'Không thể bắt đầu stream');
      setStatus('error');
    }
  };

  const disconnect = () => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop());
      streamRef.current = null;
    }
    if (pcRef.current) {
      pcRef.current.close();
      pcRef.current = null;
    }
    if (socketRef.current) {
      socketRef.current.close();
      socketRef.current = null;
    }
    if (videoRef.current) {
      videoRef.current.srcObject = null;
    }
    if (sourceVideoRef.current) {
      sourceVideoRef.current.pause();
      sourceVideoRef.current.src = '';
      videoFileRef.current = null;
    }
    setHasFile(false);
    setFileName(null);
    if (streamSessionIdRef.current) {
      updateStreamSessionStatus(streamSessionIdRef.current, 'ended');
      streamSessionIdRef.current = null;
    }
    hasViewerConnectedRef.current = false; // Reset viewer connection tracking
    setStatus('idle');
    setError(null);
  };

  useEffect(() => {
    return () => {
      disconnect();
    };
  }, []);

  const canStart = hasFile && !!roomId && status === 'idle';

  return (
    <div className="bg-white rounded-xl shadow border border-gray-200 flex flex-col overflow-hidden">
      <div className="px-4 py-3 border-b border-gray-100 flex items-center justify-between">
        <div>
          <div className="text-xs uppercase tracking-wide text-gray-500">
            {parkingLotId} • {cameraId}
          </div>
          <div className="text-xs text-gray-400 truncate max-w-xs">
            Room: {roomId || '—'}
          </div>
        </div>
        <div className="flex items-center gap-2">
          <span
            className={`text-xs font-semibold px-2 py-1 rounded-full ${
              status === 'streaming'
                ? 'bg-green-100 text-green-700'
                : status === 'connecting'
                  ? 'bg-yellow-100 text-yellow-700'
                  : status === 'error'
                    ? 'bg-red-100 text-red-700'
                    : 'bg-gray-100 text-gray-600'
            }`}
          >
            {status === 'idle' && 'Idle'}
            {status === 'connecting' && 'Connecting'}
            {status === 'streaming' && 'Streaming'}
            {status === 'error' && 'Error'}
          </span>
          <button
            onClick={() => {
              disconnect();
              onRemove(id);
            }}
            className="text-xs text-gray-500 hover:text-red-600"
          >
            ✕
          </button>
        </div>
      </div>
      <div className="px-4 pt-3 pb-2 border-b border-gray-100 flex items-center gap-3">
        <button
          type="button"
          onClick={handleSelectFileClick}
          className="px-3 py-1.5 text-xs rounded-lg bg-gray-100 hover:bg-gray-200 text-gray-700"
          disabled={status !== 'idle'}
        >
          📁 Chọn video
        </button>
        <input
          type="file"
          accept="video/*"
          ref={fileInputRef}
          className="hidden"
          onChange={handleVideoFileSelect}
        />
        <span className="text-xs text-gray-500 truncate">
          {fileName || 'Chưa chọn video'}
        </span>
        <button
          onClick={status === 'idle' ? connect : disconnect}
          disabled={!canStart && status === 'idle'}
          className={`ml-auto px-4 py-1.5 text-xs rounded-lg font-semibold transition ${
            status === 'idle'
              ? canStart
                ? 'bg-indigo-600 text-white hover:bg-indigo-700'
                : 'bg-gray-200 text-gray-500 cursor-not-allowed'
              : 'bg-red-600 text-white hover:bg-red-700'
          }`}
        >
          {status === 'idle' ? 'Bắt đầu phát' : 'Dừng phát'}
        </button>
      </div>
      <div className="bg-black relative aspect-video">
        <video
          ref={videoRef}
          autoPlay
          playsInline
          muted
          className="w-full h-full object-contain"
          controls
        />
        <video
          ref={sourceVideoRef}
          loop
          muted
          playsInline
          className="hidden"
        />
      </div>
      {error && (
        <div className="px-4 py-2 text-xs text-red-600 bg-red-50 border-t border-red-100">
          {error}
        </div>
      )}
    </div>
  );
}

export function MultiStreamHostPage() {
  const { user, role } = useAuth();
  const ownerId = user?.uid ?? '';

  const [availableParkings, setAvailableParkings] = useState<string[]>([]);
  const [availableESP32Cameras, setAvailableESP32Cameras] = useState<ESP32Config[]>([]);
  const [parkingLotId, setParkingLotId] = useState('');
  const [cameraId, setCameraId] = useState('');
  const [parkingIdError, setParkingIdError] = useState<string | null>(null);
  const [cameraIdError, setCameraIdError] = useState<string | null>(null);
  const [tiles, setTiles] = useState<HostTileConfig[]>([]);
  const [existingCameras, setExistingCameras] = useState<string[]>([]);
  const [loadingCameras, setLoadingCameras] = useState(false);
  const [camerasLoaded, setCamerasLoaded] = useState(false);

  // Load ESP32 cameras from saved configs
  useEffect(() => {
    const loadESP32Cameras = async () => {
      console.log('[MultiStreamHost] Loading ESP32 cameras for owner:', ownerId);
      
      if (!ownerId) {
        console.log('[MultiStreamHost] No ownerId, skipping ESP32 camera load');
        setAvailableESP32Cameras([]);
        return;
      }
      
      try {
        const configs = await getUserESP32Configs(ownerId);
        console.log('[MultiStreamHost] ✅ Loaded', configs.length, 'ESP32 cameras:', configs);
        setAvailableESP32Cameras(configs);
      } catch (err) {
        console.error('[MultiStreamHost] ❌ Failed to load ESP32 cameras:', err);
        setAvailableESP32Cameras([]);
      }
    };
    
    loadESP32Cameras();
  }, [ownerId]);

  useEffect(() => {
    const load = async () => {
      if (!ownerId) {
        setAvailableParkings([]);
        return;
      }
      try {
        // Load parking lots from database
        const parkingLots = await getParkingLotsByOwner(ownerId);
        const parkingIds = parkingLots.map(lot => lot.id).sort();
        setAvailableParkings(parkingIds);
      } catch (err) {
        console.error('Failed to load parking lots and cameras:', err);
      }
    };
    load();
  }, [ownerId]);

  // Reset cameras when parking lot changes
  useEffect(() => {
    setExistingCameras([]);
    setCamerasLoaded(false);
  }, [parkingLotId]);

  // Manual load cameras function
  const loadCameras = async () => {
    if (!parkingLotId.trim()) {
      setExistingCameras([]);
      return;
    }
    
    setLoadingCameras(true);
    try {
      const lot = await getParkingLot(parkingLotId.trim());
      if (lot) {
        console.log(`[MultiStreamHost] Loaded cameras for ${parkingLotId}:`, lot.cameras);
        setExistingCameras(lot.cameras || []);
        setCamerasLoaded(true);
      } else {
        setExistingCameras([]);
      }
    } catch (err) {
      console.error('[MultiStreamHost] Failed to load cameras:', err);
      setExistingCameras([]);
    } finally {
      setLoadingCameras(false);
    }
  };

  const validateParkingId = (value: string) => {
    if (!value.trim()) {
      setParkingIdError('Parking Lot ID không được để trống');
      return false;
    }
    setParkingIdError(null);
    return true;
  };

  const validateCameraId = (value: string) => {
    if (!value.trim()) {
      setCameraIdError('Camera ID không được để trống');
      return false;
    }
    setCameraIdError(null);
    return true;
  };

  const handleAddTile = async () => {
    if (!validateParkingId(parkingLotId) || !validateCameraId(cameraId)) {
      return;
    }
    const lot = parkingLotId.trim();
    const cam = cameraId.trim();
    const id = `${lot}__${cam}__${Date.now()}`;
    
    // Add camera to parking lot immediately
    console.log(`[MultiStreamHost] Adding camera ${cam} to parking lot ${lot}...`);
    try {
      const result = await addCameraToParkingLot(lot, cam);
      if (result.success) {
        console.log(`[MultiStreamHost] ✅ Camera ${cam} added to parking lot ${lot}`);
        // Only update local state if cameras are already loaded
        if (camerasLoaded) {
          setExistingCameras(prev => [...prev, cam]);
        }
      } else {
        console.warn(`[MultiStreamHost] ⚠️ Failed to add camera:`, result.error);
        alert(`⚠️ Không thể thêm camera vào parking lot: ${result.error}`);
      }
    } catch (error) {
      console.error(`[MultiStreamHost] ❌ Error adding camera:`, error);
      alert(`❌ Lỗi khi thêm camera: ${error}`);
    }
    
    setTiles((prev) => {
      const exists = prev.some((t) => t.parkingLotId === lot && t.cameraId === cam);
      if (exists) return prev;
      return [...prev, { id, parkingLotId: lot, cameraId: cam }];
    });
  };

  const handleRemoveCamera = async (cameraIdToRemove: string) => {
    if (!parkingLotId.trim()) return;
    
    const confirmed = window.confirm(
      `Bạn có chắc chắn muốn xóa camera "${cameraIdToRemove}" khỏi parking lot "${parkingLotId}"?`
    );
    
    if (!confirmed) return;
    
    try {
      const result = await removeCameraFromParkingLot(parkingLotId.trim(), cameraIdToRemove);
      if (result.success) {
        console.log(`[MultiStreamHost] ✅ Camera ${cameraIdToRemove} removed from parking lot ${parkingLotId}`);
        // Update local state only - no Firebase read
        setExistingCameras(prev => prev.filter(cam => cam !== cameraIdToRemove));
        alert(`✅ Đã xóa camera "${cameraIdToRemove}" thành công!`);
      } else {
        console.warn(`[MultiStreamHost] ⚠️ Failed to remove camera:`, result.error);
        alert(`⚠️ Không thể xóa camera: ${result.error}`);
      }
    } catch (error) {
      console.error(`[MultiStreamHost] ❌ Error removing camera:`, error);
      alert(`❌ Lỗi khi xóa camera: ${error}`);
    }
  };

  const canAdd =
    parkingLotId.trim().length > 0 &&
    cameraId.trim().length > 0 &&
    !parkingIdError &&
    !cameraIdError;

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <div className="flex flex-wrap items-center justify-between gap-4 mb-6">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">📹 Multi Stream Host</h1>
          <p className="text-gray-500 text-sm">
            Host camera streams để thêm camera vào parking lot. Sau khi host, camera sẽ tự động xuất hiện trong parking lot dashboard.
          </p>
        </div>
        {role !== 'admin' && (
          <div className="text-sm text-red-600 bg-red-50 border border-red-100 px-3 py-2 rounded-lg">
            Chỉ Admin mới có quyền host stream.
          </div>
        )}
      </div>

      {/* No Parking Lots Warning */}
      {availableParkings.length === 0 && role === 'admin' && (
        <div className="mb-6 bg-yellow-50 border-2 border-yellow-300 rounded-xl p-5">
          <div className="flex items-start gap-3">
            <span className="text-3xl">⚠️</span>
            <div className="flex-1">
              <h3 className="text-lg font-bold text-yellow-900 mb-2">
                Chưa có bãi đỗ xe nào
              </h3>
              <p className="text-sm text-yellow-800 mb-3">
                Bạn cần tạo bãi đỗ xe trước khi host camera streams.
              </p>
              <a
                href="/parking-lots"
                className="inline-flex items-center gap-2 px-4 py-2 bg-yellow-600 hover:bg-yellow-700 text-white rounded-lg font-semibold transition"
              >
                🏢 Đến trang Quản lý Bãi đỗ xe →
              </a>
            </div>
          </div>
        </div>
      )}

      {/* Debug Info Panel */}
      {role === 'admin' && (
        <details className="mb-6 bg-gray-50 border border-gray-300 rounded-lg p-4">
          <summary className="cursor-pointer font-semibold text-gray-700 hover:text-blue-600">
            🔍 Debug Info (Click to expand)
          </summary>
          <div className="mt-3 space-y-2 text-sm font-mono">
            <div className="flex gap-2">
              <span className="text-gray-600">Owner ID:</span>
              <span className="text-blue-600">{ownerId || '(not logged in)'}</span>
            </div>
            <div className="flex gap-2">
              <span className="text-gray-600">Parking Lots:</span>
              <span className="text-green-600">{availableParkings.length} loaded</span>
              {availableParkings.length > 0 && (
                <span className="text-gray-500">({availableParkings.join(', ')})</span>
              )}
            </div>
            <div className="flex gap-2">
              <span className="text-gray-600">ESP32 Cameras:</span>
              <span className="text-purple-600">{availableESP32Cameras.length} saved</span>
            </div>
            {availableESP32Cameras.length > 0 && (
              <div className="mt-2 p-2 bg-white rounded border border-gray-200">
                <div className="text-xs text-gray-600 mb-1">Saved ESP32 Cameras:</div>
                {availableESP32Cameras.map((esp32, idx) => (
                  <div key={esp32.id} className="text-xs text-gray-700 ml-2">
                    {idx + 1}. 📹 {esp32.name} - {esp32.ipAddress} {esp32.isDefault && '⭐'}
                  </div>
                ))}
              </div>
            )}
            <div className="mt-2 p-2 bg-blue-50 rounded border border-blue-200 text-xs text-blue-800">
              💡 <strong>Troubleshooting:</strong> ESP32 cameras are loaded from the saved configs you add in /stream/multi
            </div>
          </div>
        </details>
      )}

      {/* Config add tile */}
      <div className="mb-6 bg-white border border-gray-200 rounded-2xl shadow-sm p-4">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 items-end">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Parking Lot ID {availableParkings.length > 0 && (
                <span className="text-xs text-green-600 font-normal">
                  ({availableParkings.length} bãi đỗ xe có sẵn)
                </span>
              )}
            </label>
            <select
              value={parkingLotId}
              onChange={(e) => {
                setParkingLotId(e.target.value);
                validateParkingId(e.target.value);
              }}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
              disabled={role !== 'admin'}
            >
              <option value="">-- Chọn Parking Lot --</option>
              {availableParkings.map((p) => (
                <option key={p} value={p}>
                  {p}
                </option>
              ))}
            </select>
            {availableParkings.length === 0 && (
              <p className="mt-1 text-xs text-orange-600">
                ⚠️ Chưa có bãi đỗ xe nào. Tạo bãi mới tại{' '}
                <a href="/parking-lots" className="underline font-semibold hover:text-orange-800">
                  /parking-lots
                </a>
              </p>
            )}
            {parkingIdError && (
              <p className="mt-1 text-xs text-red-600">{parkingIdError}</p>
            )}
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Camera ID {availableESP32Cameras.length > 0 && (
                <span className="text-xs text-blue-600 font-normal">
                  ({availableESP32Cameras.length} ESP32 camera đã lưu)
                </span>
              )}
            </label>
            <select
              value={cameraId}
              onChange={(e) => {
                setCameraId(e.target.value);
                validateCameraId(e.target.value);
              }}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
              disabled={role !== 'admin'}
              title="Chọn camera ESP32 đã lưu"
            >
              <option value="">-- Chọn ESP32 Camera --</option>
              {availableESP32Cameras.map((esp32) => (
                <option key={esp32.id} value={esp32.id}>
                  📹 {esp32.name} ({esp32.ipAddress})
                </option>
              ))}
            </select>
            {availableESP32Cameras.length === 0 && ownerId && (
              <p className="mt-1 text-xs text-red-600">
                ⚠️ Chưa có ESP32 camera nào được lưu. Thêm camera ở <a href="/stream/multi" className="underline font-bold">/stream/multi</a> trước!
              </p>
            )}
            {availableESP32Cameras.length > 0 && (
              <p className="mt-1 text-xs text-blue-600">
                ✅ Có {availableESP32Cameras.length} ESP32 camera đã lưu. Chọn từ dropdown.
              </p>
            )}
            {cameraIdError && (
              <p className="mt-1 text-xs text-red-600">{cameraIdError}</p>
            )}
          </div>
          <div className="flex items-center md:justify-end">
            <button
              onClick={handleAddTile}
              disabled={!canAdd || role !== 'admin'}
              className={`w-full md:w-auto px-6 py-2 rounded-lg font-semibold transition ${
                canAdd && role === 'admin'
                  ? 'bg-indigo-600 text-white hover:bg-indigo-700'
                  : 'bg-gray-200 text-gray-500 cursor-not-allowed'
              }`}
            >
              ➕ Thêm host
            </button>
          </div>
        </div>
        <div className="mt-3 p-3 bg-blue-50 border border-blue-200 rounded-lg">
          <p className="text-xs text-blue-800">
            <strong>💡 Hướng dẫn:</strong>
          </p>
          <ul className="mt-2 space-y-1 text-xs text-blue-700">
            <li>• <strong>Parking Lot ID:</strong> Chọn từ dropdown (đã tạo tại <a href="/parking-lots" className="underline font-semibold">/parking-lots</a>)</li>
            <li>• <strong>Camera ID:</strong> 
              <ul className="ml-4 mt-1 space-y-0.5">
                <li>→ Chọn từ dropdown để tái sử dụng camera đã cấu hình (tự động điền Parking Lot)</li>
                <li>→ Hoặc nhập tên mới (VD: CAM1, ENTRANCE, EXIT)</li>
              </ul>
            </li>
            <li>• Một combo Parking Lot + Camera chỉ được thêm một lần</li>
            <li>• Camera ID chỉ gồm chữ cái và số, không dấu, không khoảng trắng</li>
          </ul>
        </div>
      </div>

      {/* Existing Cameras in Selected Parking Lot */}
      {parkingLotId && (
        <div className="mb-6 bg-white border border-gray-200 rounded-2xl shadow-sm p-4">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-lg font-bold text-gray-900">
              📹 Cameras trong "{parkingLotId}"
            </h3>
            <button
              onClick={loadCameras}
              disabled={loadingCameras}
              className={`px-4 py-2 rounded-lg font-semibold text-sm transition ${
                loadingCameras
                  ? 'bg-gray-300 text-gray-500 cursor-not-allowed'
                  : 'bg-blue-600 hover:bg-blue-700 text-white'
              }`}
            >
              {loadingCameras ? '⏳ Đang tải...' : '🔄 Tải danh sách cameras'}
            </button>
          </div>
          
          {!camerasLoaded && !loadingCameras ? (
            <div className="p-4 bg-blue-50 border border-blue-200 rounded-lg text-center">
              <p className="text-sm text-blue-800 mb-2">
                <strong>💡 Click "🔄 Tải danh sách cameras"</strong> để xem cameras trong parking lot này
              </p>
              <p className="text-xs text-blue-600">
                (Chỉ tải khi cần để tiết kiệm Firebase quota)
              </p>
            </div>
          ) : existingCameras.length === 0 && camerasLoaded ? (
            <div className="p-4 bg-gray-50 border border-gray-200 rounded-lg text-center text-sm text-gray-500">
              Chưa có camera nào trong parking lot này.
            </div>
          ) : camerasLoaded ? (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
              {existingCameras.map((cam) => (
                <div
                  key={cam}
                  className="flex items-center justify-between p-3 bg-gradient-to-r from-blue-50 to-indigo-50 border border-blue-200 rounded-lg hover:shadow-md transition"
                >
                  <div className="flex items-center gap-2">
                    <span className="text-2xl">📹</span>
                    <span className="font-semibold text-gray-800">{cam}</span>
                  </div>
                  <button
                    onClick={() => handleRemoveCamera(cam)}
                    className="px-3 py-1 bg-red-500 hover:bg-red-600 text-white text-xs font-semibold rounded-lg transition"
                    title="Xóa camera khỏi parking lot"
                  >
                    🗑️ Xóa
                  </button>
                </div>
              ))}
            </div>
          ) : null}
          
          <div className="mt-3 p-2 bg-yellow-50 border border-yellow-200 rounded-lg">
            <p className="text-xs text-yellow-800">
              <strong>⚠️ Lưu ý:</strong> Xóa camera khỏi parking lot sẽ không xóa stream đang chạy. 
              Bạn cần dừng stream host tile bên dưới nếu muốn. Click "🔄 Tải danh sách" để refresh sau khi thêm/xóa camera.
            </p>
          </div>
        </div>
      )}

      {/* Grid hosts */}
      {tiles.length === 0 ? (
        <div className="p-10 bg-white border border-dashed border-gray-300 rounded-2xl text-center text-gray-500">
          Chưa có host nào. Hãy chọn Parking Lot ID + Camera ID rồi bấm{' '}
          <span className="font-semibold">“Thêm host”</span>.
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {tiles.map((tile) => (
            <StreamHostTile
              key={tile.id}
              id={tile.id}
              parkingLotId={tile.parkingLotId}
              cameraId={tile.cameraId}
              ownerId={ownerId}
              onRemove={(removeId) =>
                setTiles((prev) => prev.filter((t) => t.id !== removeId))
              }
            />
          ))}
        </div>
      )}

      {/* Step-by-Step Guide - BOTTOM */}
      <div className="mt-8 mb-6 bg-gradient-to-r from-green-50 to-blue-50 border-2 border-green-300 rounded-xl p-5">
        <div className="flex items-start gap-3">
          <span className="text-3xl">🎯</span>
          <div className="flex-1">
            <h3 className="text-lg font-bold text-gray-900 mb-3">
              📚 Cách thêm camera vào Parking Lot
            </h3>
            <div className="grid md:grid-cols-3 gap-4">
              {/* Step 1 */}
              <div className="bg-white rounded-lg p-4 border-2 border-blue-200">
                <div className="flex items-center gap-2 mb-2">
                  <span className="bg-blue-600 text-white rounded-full w-6 h-6 flex items-center justify-center text-sm font-bold">1</span>
                  <span className="font-bold text-gray-800">Chọn Parking Lot</span>
                </div>
                <p className="text-xs text-gray-600 mb-2">
                  Chọn bãi đỗ xe từ dropdown
                </p>
                <p className="text-xs text-blue-600">
                  💡 Chưa có? Tạo tại <a href="/parking-lots" className="underline font-bold">/parking-lots</a>
                </p>
              </div>

              {/* Step 2 */}
              <div className="bg-white rounded-lg p-4 border-2 border-purple-200">
                <div className="flex items-center gap-2 mb-2">
                  <span className="bg-purple-600 text-white rounded-full w-6 h-6 flex items-center justify-center text-sm font-bold">2</span>
                  <span className="font-bold text-gray-800">Chọn Camera</span>
                </div>
                <p className="text-xs text-gray-600 mb-2">
                  Chọn ESP32 camera đã lưu từ dropdown
                </p>
                <p className="text-xs text-purple-600">
                  💡 Lưu camera tại <a href="/stream/multi" className="underline font-bold">/stream/multi</a>
                </p>
              </div>

              {/* Step 3 */}
              <div className="bg-white rounded-lg p-4 border-2 border-green-200">
                <div className="flex items-center gap-2 mb-2">
                  <span className="bg-green-600 text-white rounded-full w-6 h-6 flex items-center justify-center text-sm font-bold">3</span>
                  <span className="font-bold text-gray-800">Thêm Host</span>
                </div>
                <p className="text-xs text-gray-600 mb-2">
                  Click "➕ Thêm host" → Chọn video → "Bắt đầu phát"
                </p>
                <p className="text-xs text-green-600">
                  ✅ Camera tự động thêm vào parking lot!
                </p>
              </div>
            </div>

            {/* Result */}
            <div className="mt-4 p-3 bg-yellow-50 border border-yellow-300 rounded-lg">
              <p className="text-sm text-gray-800">
                <strong>🎉 Kết quả:</strong> Camera xuất hiện tại{' '}
                <a href="/parking-lots" className="text-blue-600 underline font-bold hover:text-blue-800">
                  /parking-lots
                </a>
                {' '}→ Chọn bãi đỗ xe → Xem danh sách cameras! 
                Xem tất cả tại{' '}
                <a href="/stream/view-multi" className="text-blue-600 underline font-bold hover:text-blue-800">
                  /stream/view-multi
                </a>
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Quick Navigation - Bottom */}
      <div className="mt-8 pt-6 border-t border-gray-200">
        <div className="flex gap-3 overflow-x-auto pb-2">
          <a
            href="/parking-lots"
            className="px-4 py-2 bg-white border-2 border-gray-300 rounded-lg hover:border-blue-500 hover:shadow-md transition flex items-center gap-2 whitespace-nowrap"
          >
            <span className="text-xl">🏢</span>
            <div className="text-left">
              <div className="text-xs text-gray-500">Bước 1</div>
              <div className="font-semibold text-sm">Quản lý Bãi đỗ xe</div>
            </div>
          </a>
          <div className="px-4 py-2 bg-gradient-to-r from-indigo-500 to-purple-500 text-white border-2 border-indigo-600 rounded-lg shadow-lg flex items-center gap-2 whitespace-nowrap">
            <span className="text-xl">📹</span>
            <div className="text-left">
              <div className="text-xs opacity-90">Bước 2 (Đang ở đây)</div>
              <div className="font-bold text-sm">Host Camera Streams</div>
            </div>
          </div>
          <a
            href="/stream/view-multi"
            className="px-4 py-2 bg-white border-2 border-gray-300 rounded-lg hover:border-blue-500 hover:shadow-md transition flex items-center gap-2 whitespace-nowrap"
          >
            <span className="text-xl">👁️</span>
            <div className="text-left">
              <div className="text-xs text-gray-500">Bước 3</div>
              <div className="font-semibold text-sm">Xem Live Streams</div>
            </div>
          </a>
        </div>
      </div>
    </div>
  );
}


