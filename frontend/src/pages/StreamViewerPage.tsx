import { useEffect, useRef, useState, useMemo } from 'react';
import { useAuth } from '../context/AuthContext';
import { fetchLatestDetections, type DetectionRecord } from '../services/detectionService';
import {
  optimizeVideoElement,
  createHighQualityAnswer,
} from '../utils/webrtcQuality';

const STREAM_URL = 'http://localhost:8000/stream';
const ICE_SERVERS = [{ urls: 'stun:stun.l.google.com:19302' }];
const PARKING_ID_REGEX = /^[A-Za-z0-9]+$/;

export function StreamViewerPage() {
  const { user } = useAuth();
  const ownerId = user?.uid ?? null;

  // Refs
  const videoRef = useRef<HTMLVideoElement>(null);
  const pcRef = useRef<RTCPeerConnection | null>(null);
  const socketRef = useRef<WebSocket | null>(null);

  // State
  const [status, setStatus] = useState<'idle' | 'connecting' | 'connected' | 'error'>('idle');
  const [error, setError] = useState<string | null>(null);
  const [parkingLotId, setParkingLotId] = useState('');
  const [cameraId, setCameraId] = useState('');
  const [parkingIdError, setParkingIdError] = useState<string | null>(null);
  const [cameraIdError, setCameraIdError] = useState<string | null>(null);
  const [availableParkings, setAvailableParkings] = useState<string[]>([]);
  const [availableCameras, setAvailableCameras] = useState<string[]>([]);

  // Fetch available parking lots and cameras from Firebase
  useEffect(() => {
    const loadCameras = async () => {
      if (!ownerId) {
        setAvailableParkings([]);
        setAvailableCameras([]);
        return;
      }

      try {
        const result = await fetchLatestDetections({ ownerId });
        if (result.success && result.data) {
          const parkings = new Set<string>();
          const cameras = new Set<string>();

          result.data.forEach((record: DetectionRecord) => {
            if (record.parkingId) parkings.add(record.parkingId);
            if (record.cameraId) cameras.add(record.cameraId);
          });

          setAvailableParkings(Array.from(parkings).sort());
          setAvailableCameras(Array.from(cameras).sort());
        }
      } catch (err) {
        console.error('Failed to load cameras:', err);
      }
    };

    loadCameras();
  }, [ownerId]);

  // Validate parking lot ID
  const validateParkingId = (value: string) => {
    if (!value.trim()) {
      setParkingIdError('Parking Lot ID không được để trống');
      return false;
    }
    if (!PARKING_ID_REGEX.test(value.trim())) {
      setParkingIdError('Parking Lot ID chỉ được chứa chữ cái tiếng Anh và số, không dấu, không khoảng trắng');
      return false;
    }
    setParkingIdError(null);
    return true;
  };

  // Validate camera ID
  const validateCameraId = (value: string) => {
    if (!value.trim()) {
      setCameraIdError('Camera ID không được để trống');
      return false;
    }
    if (!PARKING_ID_REGEX.test(value.trim())) {
      setCameraIdError('Camera ID chỉ được chứa chữ cái tiếng Anh và số, không dấu, không khoảng trắng');
      return false;
    }
    setCameraIdError(null);
    return true;
  };

  // Handle parking lot ID change
  const handleParkingIdChange = (value: string) => {
    setParkingLotId(value);
    validateParkingId(value);
  };

  // Handle camera ID change
  const handleCameraIdChange = (value: string) => {
    setCameraId(value);
    validateCameraId(value);
  };

  // Get room ID from parking and camera
  const roomId = useMemo(() => {
    if (!parkingLotId.trim() || !cameraId.trim()) return null;
    return `${parkingLotId.trim()}__${cameraId.trim()}`;
  }, [parkingLotId, cameraId]);

  // Start viewing stream
  const startViewing = async () => {
    try {
      // Validate inputs
      if (!validateParkingId(parkingLotId) || !validateCameraId(cameraId)) {
        setError('Vui lòng kiểm tra lại thông tin nhập vào');
        return;
      }

      if (!roomId) {
        setError('Room ID không hợp lệ');
        return;
      }

      setStatus('connecting');
      setError(null);

      // Create PeerConnection
      const pc = new RTCPeerConnection({ iceServers: ICE_SERVERS });
      pcRef.current = pc;

      // Receive stream from host
      pc.ontrack = async (event) => {
        console.log('✅ Received track:', event.track.kind, event.track.id);
        console.log('Streams:', event.streams.length);
        
        if (videoRef.current && event.streams && event.streams.length > 0) {
          const stream = event.streams[0];
          console.log('Setting video srcObject, tracks:', stream.getTracks().length);
          
          const video = videoRef.current;
          
          // Tối ưu video element cho chất lượng cao
          optimizeVideoElement(video);
          
          video.srcObject = stream;
          
          // Ensure video plays
          try {
            await video.play();
            console.log('✅ Video playing with optimized quality');
          } catch (playError) {
            console.error('Error playing video:', playError);
            // Try again after a short delay
            setTimeout(async () => {
              if (videoRef.current) {
                try {
                  await videoRef.current.play();
                } catch (e) {
                  console.error('Retry play failed:', e);
                }
              }
            }, 500);
          }
        } else {
          console.warn('No stream or video element available');
        }
      };

      // Connect WebSocket with timeout
      const socket = new WebSocket(SIGNALING_URL);
      socketRef.current = socket;

      // Set timeout for WebSocket connection
      const connectionTimeout = setTimeout(() => {
        if (socket.readyState !== WebSocket.OPEN) {
          console.error('WebSocket connection timeout');
          setError('Không thể kết nối đến signaling server. Đảm bảo server đang chạy tại ws://localhost:3001');
          setStatus('error');
          socket.close();
        }
      }, 5000); // 5 seconds timeout

      socket.onopen = async () => {
        clearTimeout(connectionTimeout);
        console.log('✅ Connected to signaling server');
        socket.send(JSON.stringify({ type: 'join', role: 'viewer', roomId }));
      };

      socket.onmessage = async (event) => {
        try {
          const data = JSON.parse(event.data);

          if (data.type === 'offer') {
            // Tạo answer với codec preferences chất lượng cao
            const answer = await createHighQualityAnswer(pc, data.offer);
            await pc.setLocalDescription(answer);
            socket.send(JSON.stringify({ type: 'answer', answer }));
            console.log('✅ Sent high quality answer to host');
          } else if (data.type === 'ice') {
            await pc.addIceCandidate(data.candidate);
          }
        } catch (err) {
          console.error('Error handling message:', err);
          setError('Lỗi xử lý tín hiệu từ host');
          setStatus('error');
        }
      };

      socket.onerror = (err) => {
        clearTimeout(connectionTimeout);
        console.error('WebSocket error:', err);
        setError('Lỗi kết nối signaling server. Đảm bảo server đang chạy: cd server && npm start');
        setStatus('error');
      };

      socket.onclose = (event) => {
        clearTimeout(connectionTimeout);
        console.log('WebSocket closed', event.code, event.reason);
        if (status !== 'idle' && status !== 'error') {
          setStatus('idle');
          if (event.code !== 1000) {
            setError('Kết nối bị đóng. Code: ' + event.code);
          }
        }
      };

      // Handle ICE candidates
      pc.onicecandidate = (event) => {
        if (event.candidate && socket.readyState === WebSocket.OPEN) {
          socket.send(JSON.stringify({ type: 'ice', candidate: event.candidate }));
        }
      };

      pc.onconnectionstatechange = () => {
        console.log('Connection state:', pc.connectionState);
        if (pc.connectionState === 'connected') {
          setStatus('connected');
          // Ensure video plays when connected
          if (videoRef.current && videoRef.current.srcObject) {
            videoRef.current.play().catch((err) => {
              console.error('Error playing video on connect:', err);
            });
          }
        } else if (pc.connectionState === 'failed' || pc.connectionState === 'disconnected') {
          setStatus('error');
          setError('Mất kết nối với host');
        }
      };
    } catch (err: any) {
      console.error('Error connecting to stream:', err);
      setError(err.message || 'Không thể kết nối');
      setStatus('error');
    }
  };

  // Disconnect
  const disconnect = () => {
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

    setStatus('idle');
    setError(null);
  };

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      disconnect();
    };
  }, []);

  const canConnect = 
    parkingLotId.trim().length > 0 &&
    cameraId.trim().length > 0 &&
    !parkingIdError &&
    !cameraIdError;

  return (
    <div className="p-6 max-w-4xl mx-auto space-y-4">
      <div className="bg-white rounded-lg shadow-md p-6">
        <h1 className="text-2xl font-bold mb-4">👀 Xem Stream</h1>
        <p className="text-gray-600 mb-4">
          Kết nối để xem video trực tiếp từ host. Đảm bảo host đã bắt đầu phát với cùng Parking Lot ID và Camera ID.
        </p>

        {/* Configuration Form */}
        <div className="mb-6 space-y-4 border-b pb-6">
          {/* Parking Lot ID */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Parking Lot ID <span className="text-red-500">*</span>
            </label>
            <div className="flex gap-2">
              <select
                value={parkingLotId}
                onChange={(e) => handleParkingIdChange(e.target.value)}
                className="flex-1 px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-teal-500 focus:border-teal-500"
                disabled={status !== 'idle'}
              >
                <option value="">-- Chọn hoặc nhập mới --</option>
                {availableParkings.map((parking) => (
                  <option key={parking} value={parking}>
                    {parking}
                  </option>
                ))}
              </select>
              <input
                type="text"
                value={parkingLotId}
                onChange={(e) => handleParkingIdChange(e.target.value)}
                placeholder="Nhập Parking Lot ID"
                className="flex-1 px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-teal-500 focus:border-teal-500"
                disabled={status !== 'idle'}
              />
            </div>
            {parkingIdError && (
              <p className="mt-1 text-sm text-red-600">{parkingIdError}</p>
            )}
            <p className="mt-1 text-xs text-gray-500">
              ID chỉ gồm chữ cái tiếng Anh và số, không dấu và không khoảng trắng
            </p>
          </div>

          {/* Camera ID */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Camera ID <span className="text-red-500">*</span>
            </label>
            <div className="flex gap-2">
              <select
                value={cameraId}
                onChange={(e) => handleCameraIdChange(e.target.value)}
                className="flex-1 px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-teal-500 focus:border-teal-500"
                disabled={status !== 'idle'}
              >
                <option value="">-- Chọn hoặc nhập mới --</option>
                {availableCameras.map((camera) => (
                  <option key={camera} value={camera}>
                    {camera}
                  </option>
                ))}
              </select>
              <input
                type="text"
                value={cameraId}
                onChange={(e) => handleCameraIdChange(e.target.value)}
                placeholder="Nhập Camera ID"
                className="flex-1 px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-teal-500 focus:border-teal-500"
                disabled={status !== 'idle'}
              />
            </div>
            {cameraIdError && (
              <p className="mt-1 text-sm text-red-600">{cameraIdError}</p>
            )}
            <p className="mt-1 text-xs text-gray-500">
              ID chỉ gồm chữ cái tiếng Anh và số, không dấu và không khoảng trắng
            </p>
          </div>
        </div>

        {/* Video Display */}
        <div className="mb-4">
          <img 
            src="http://localhost:8000/stream" 
            alt="ESP32 Stream"
            style={{ width: '100%', height: 'auto' }}
          />
        </div>

        {/* Controls */}
        <div className="flex gap-3">
          {status === 'idle' && (
            <button
              onClick={startViewing}
              disabled={!canConnect}
              className={`px-6 py-2 rounded-lg transition ${
                canConnect
                  ? 'bg-teal-600 text-white hover:bg-teal-700'
                  : 'bg-gray-300 text-gray-500 cursor-not-allowed'
              }`}
            >
              Kết nối
            </button>
          )}
          {status !== 'idle' && (
            <button
              onClick={disconnect}
              className="px-6 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 transition"
            >
              Ngắt kết nối
            </button>
          )}
        </div>

        {/* Status */}
        <div className="mt-4">
          <div className="text-sm text-gray-600">
            <strong>Trạng thái:</strong>{' '}
            <span
              className={`font-semibold ${
                status === 'connected'
                  ? 'text-green-600'
                  : status === 'connecting'
                    ? 'text-yellow-600'
                    : status === 'error'
                      ? 'text-red-600'
                      : 'text-gray-500'
              }`}
            >
              {status === 'idle' && 'Chưa kết nối'}
              {status === 'connecting' && 'Đang kết nối...'}
              {status === 'connected' && '✅ Đã kết nối'}
              {status === 'error' && '❌ Lỗi'}
            </span>
          </div>
          {error && (
            <div className="mt-2 text-sm text-red-600 bg-red-50 p-2 rounded">{error}</div>
          )}
          {roomId && (
            <div className="mt-2 text-xs text-gray-500">
              Room ID: <code className="bg-gray-100 px-2 py-1 rounded">{roomId}</code>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
