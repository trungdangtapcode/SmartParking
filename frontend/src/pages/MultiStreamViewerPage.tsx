import { useState, useRef, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import { API_CONFIG } from '../config/api';
import { performVehicleCheckIn } from '../services/checkInService';
import { getParkingLotsByOwner } from '../services/parkingLotService';
import type { ParkingLot } from '../types/parkingLot.types';

// ============================================
// STREAM SOURCE CONFIGURATION
// ============================================

// Video Files (Cấu hình 3 video files)
const VIDEO_FILES = [
  { id: 'video_1', name: 'Video 1 - Parking A', filename: 'parking_a.mp4' },
  { id: 'video_2', name: 'Video 2 - Parking B', filename: 'parking_b.mp4' },
  { id: 'video_3', name: 'Video 3 - Parking C', filename: 'parking_c.mp4' },
];

// FastAPI endpoints
const FASTAPI_BASE = API_CONFIG.baseURL;

type SourceType = 'esp32' | 'video' | 'mock';
type TileStatus = 'idle' | 'connected' | 'error';

interface ESP32Camera {
  id: string;
  name: string;
  ip: string;
}

// Default ESP32 cameras (sẽ được load từ localStorage hoặc dùng default)
const DEFAULT_ESP32_CAMERAS: ESP32Camera[] = [
  { id: 'esp32_1', name: 'ESP32-CAM 1', ip: 'http://192.168.1.100:81/stream' },
  { id: 'esp32_2', name: 'ESP32-CAM 2', ip: 'http://192.168.1.101:81/stream' },
  { id: 'esp32_3', name: 'ESP32-CAM 3', ip: 'http://192.168.1.102:81/stream' },
];

const ESP32_STORAGE_KEY = 'smartparking_esp32_cameras';

interface StreamTileConfig {
  id: string;
  label: string;
  sourceType: SourceType;
  sourceId: string; // esp32_1, video_1, etc.
  streamUrl: string;
  parkingId?: string; // NEW: Parking Lot ID
  cameraId?: string; // NEW: Camera ID
  isCheckInCamera?: boolean; // NEW: Is this the check-in camera (Cam1)?
}

interface StreamTileProps extends StreamTileConfig {
  onRemove: (id: string) => void;
  isStreaming: boolean;
  ownerId?: string; // NEW: Owner ID for check-in
}

// ============================================
// STREAM TILE COMPONENT (HTTP MJPEG)
// ============================================
function StreamViewerTile({ 
  id, 
  label, 
  sourceType, 
  streamUrl, 
  onRemove, 
  isStreaming,
  parkingId,
  cameraId,
  isCheckInCamera,
  ownerId,
}: StreamTileProps) {
  const [status, setStatus] = useState<TileStatus>('idle');
  const [error, setError] = useState<string | null>(null);
  const [isCheckingIn, setIsCheckingIn] = useState(false);
  const [checkInResult, setCheckInResult] = useState<{ vehicleId?: string; licensePlate?: string; error?: string } | null>(null);
  const [isTestingCapture, setIsTestingCapture] = useState(false);
  const [testCaptureImage, setTestCaptureImage] = useState<string | null>(null);
  const [progress, setProgress] = useState<{ stage: string; percentage: number } | null>(null);
  const imgRef = useRef<HTMLImageElement>(null);

  const handleImageError = () => {
    setStatus('error');
    setError(`Không thể kết nối: ${streamUrl}`);
  };

  const handleImageLoad = () => {
    setStatus('connected');
    setError(null);
  };

  // Get snapshot from stream - Ưu tiên canvas (frame hiện tại), fallback snapshot endpoint
  const getSnapshotFromStream = async (): Promise<string | null> => {
    try {
      // Option 1: Capture từ <img> element (frame hiện tại đang hiển thị - TỐT NHẤT)
      if (imgRef.current && imgRef.current.complete && imgRef.current.naturalWidth > 0) {
        try {
          const canvas = document.createElement('canvas');
          canvas.width = imgRef.current.naturalWidth;
          canvas.height = imgRef.current.naturalHeight;
          const ctx = canvas.getContext('2d');
          
          if (ctx) {
            ctx.drawImage(imgRef.current, 0, 0);
            // Use PNG for OCR to preserve quality (no compression loss)
            const imageData = canvas.toDataURL('image/png');
            console.log('✅ Captured frame from <img> element (current frame) - PNG format for OCR');
            return imageData;
          }
        } catch (canvasError) {
          console.warn('⚠️ Canvas capture failed (CORS?), trying snapshot endpoint...', canvasError);
        }
      }
      
      // Option 2: Video file - dùng snapshot endpoint với chất lượng cao (KHÔNG resize, PNG)
      // Ưu tiên dùng endpoint này vì lấy frame gốc từ video, chất lượng tốt hơn capture từ stream
      if (sourceType === 'video') {
        const urlParams = new URLSearchParams(streamUrl.split('?')[1] || '');
        const file = urlParams.get('file');
        
        if (file) {
          console.log('📸 Getting high-quality snapshot from video file (original frame, PNG)...');
          
          // Fetch với timeout
          const controller = new AbortController();
          const timeoutId = setTimeout(() => controller.abort(), 5000); // 5s timeout
          
          try {
            // Dùng quality=high để lấy frame gốc (không resize, PNG format)
            const response = await fetch(
              `${FASTAPI_BASE}/api/stream/snapshot?mode=video_file&file=${encodeURIComponent(file)}&quality=high`,
              { signal: controller.signal }
            );
            clearTimeout(timeoutId);
            
            if (!response.ok) {
              throw new Error(`Snapshot failed: ${response.status}`);
            }
            
            const data = await response.json();
            if (data.success && data.imageData) {
              console.log(`✅ Got high-quality snapshot from backend: ${data.width}x${data.height} (PNG, original frame)`);
              return data.imageData;
            }
          } catch (fetchError) {
            clearTimeout(timeoutId);
            if (fetchError instanceof Error && fetchError.name === 'AbortError') {
              throw new Error('Snapshot request timeout (5s)');
            }
            throw fetchError;
          }
        }
      }
      
      throw new Error('Không thể capture frame. Vui lòng thử lại.');
    } catch (error) {
      console.error('❌ Error getting snapshot:', error);
      return null;
    }
  };

  // Handle test capture
  const handleTestCapture = async () => {
    if (!isStreaming) {
      alert('Vui lòng bắt đầu stream trước khi test capture');
      return;
    }

    setIsTestingCapture(true);
    setTestCaptureImage(null);
    setProgress({ stage: 'Đang capture frame...', percentage: 10 });

    try {
      const imageData = await getSnapshotFromStream();
      setProgress({ stage: 'Capture hoàn tất!', percentage: 100 });

      if (!imageData) {
        throw new Error('Không thể capture frame từ stream.');
      }

      setTestCaptureImage(imageData);
      
      // Auto clear progress after 2s
      setTimeout(() => {
        setProgress(null);
      }, 2000);
    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : 'Unknown error';
      setProgress({ stage: `Lỗi: ${errorMsg}`, percentage: 0 });
      alert(`❌ Lỗi: ${errorMsg}`);
      setTimeout(() => {
        setProgress(null);
      }, 3000);
    } finally {
      setIsTestingCapture(false);
    }
  };

  // Handle check-in với progress
  const handleCheckIn = async () => {
    if (!parkingId || !cameraId || !ownerId) {
      alert('Vui lòng nhập Parking ID và Camera ID trước khi check-in');
      return;
    }

    if (!isStreaming) {
      alert('Vui lòng bắt đầu stream trước khi check-in');
      return;
    }

    setIsCheckingIn(true);
    setCheckInResult(null);
    setProgress({ stage: 'Đang capture frame...', percentage: 10 });

    try {
      // Get snapshot from stream
      console.log('📸 Getting snapshot from stream...');
      const imageData = await getSnapshotFromStream();
      setProgress({ stage: 'Đang gửi frame cho OCR...', percentage: 30 });

      if (!imageData) {
        throw new Error('Không thể capture frame từ stream. Vui lòng thử lại.');
      }

      console.log('🔍 Starting check-in with OCR...');
      console.log('📸 Image data length:', imageData.length, 'chars');
      
      setProgress({ stage: 'Đang xử lý OCR biển số...', percentage: 50 });
      
      // Perform check-in với callback progress
      const result = await performVehicleCheckIn(
        imageData,
        parkingId,
        cameraId,
        ownerId,
        (stage: string, percentage: number) => {
          setProgress({ stage, percentage });
        }
      );
      
      setProgress({ stage: 'Hoàn tất!', percentage: 100 });
      console.log('📋 Check-in result:', result);

      if (result.success && result.vehicleId && result.licensePlate) {
        setCheckInResult({
          vehicleId: result.vehicleId,
          licensePlate: result.licensePlate,
        });
        
        alert(`✅ Check-in thành công!\nBiển số: ${result.licensePlate}\nVehicle ID: ${result.vehicleId}`);
      } else {
        setCheckInResult({ error: result.error || 'Check-in failed' });
        alert(`❌ Check-in thất bại: ${result.error || 'Unknown error'}`);
      }
      
      // Clear progress after 2s
      setTimeout(() => {
        setProgress(null);
      }, 2000);
    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : 'Unknown error';
      setCheckInResult({ error: errorMsg });
      setProgress({ stage: `Lỗi: ${errorMsg}`, percentage: 0 });
      alert(`❌ Lỗi: ${errorMsg}`);
      setTimeout(() => {
        setProgress(null);
      }, 3000);
    } finally {
      setIsCheckingIn(false);
    }
  };

  const getSourceIcon = () => {
    switch (sourceType) {
      case 'esp32':
        return '📹';
      case 'video':
        return '🎬';
      case 'mock':
        return '🧪';
      default:
        return '📺';
        }
  };

  const getSourceTypeLabel = () => {
    switch (sourceType) {
      case 'esp32':
        return 'ESP32-CAM';
      case 'video':
        return 'Video File';
      case 'mock':
        return 'Mock Stream';
      default:
        return 'Unknown';
    }
  };

  return (
    <div className="bg-white rounded-xl shadow-lg border border-gray-200 flex flex-col overflow-hidden hover:shadow-xl transition-shadow">
      {/* Header */}
      <div className="px-4 py-3 bg-gradient-to-r from-strawberry-50 to-matcha-50 border-b border-gray-200 flex items-center justify-between">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-lg">{getSourceIcon()}</span>
            <h3 className="text-sm font-semibold text-gray-800 truncate">
              {label}
            </h3>
          </div>
          <p className="text-xs text-gray-500">
            {getSourceTypeLabel()}
          </p>
        </div>
        <div className="flex items-center gap-2 flex-shrink-0">
          {/* Status Badge */}
          <span
            className={`text-xs font-semibold px-2 py-1 rounded-full ${
              status === 'connected'
                ? 'bg-green-100 text-green-700'
                  : status === 'error'
                    ? 'bg-red-100 text-red-700'
                    : 'bg-gray-100 text-gray-600'
            }`}
          >
            {status === 'connected' && '🟢 Live'}
            {status === 'error' && '🔴 Error'}
            {status === 'idle' && '⚪ Idle'}
          </span>
          {/* Remove Button */}
          <button
            onClick={() => onRemove(id)}
            className="text-gray-400 hover:text-red-600 hover:bg-red-50 rounded-full p-1 transition"
            title="Xóa stream"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
      </div>

      {/* Video Display (MJPEG Stream or Preview) */}
      <div className="bg-black relative aspect-video">
        {isStreaming ? (
          // LIVE MODE: Show actual stream
          <>
            <img
              ref={imgRef}
              src={streamUrl}
              alt={label}
              className="w-full h-full object-contain"
              onError={handleImageError}
              onLoad={handleImageLoad}
              crossOrigin="anonymous"
            />

            {/* Live Indicator */}
            {status === 'connected' && (
              <div className="absolute top-3 left-3 bg-red-600 text-white px-3 py-1 rounded-full text-xs font-semibold flex items-center gap-2 animate-pulse">
                <span className="w-2 h-2 bg-white rounded-full"></span>
                LIVE
              </div>
            )}

            {/* Error Overlay */}
            {status === 'error' && (
              <div className="absolute inset-0 bg-black/80 flex items-center justify-center text-white text-center p-4">
                <div>
                  <div className="text-4xl mb-2">⚠️</div>
                  <p className="text-sm">Không thể kết nối</p>
                </div>
              </div>
            )}
          </>
        ) : (
          // PREVIEW MODE: Show placeholder
          <div className="absolute inset-0 bg-gradient-to-br from-gray-800 to-gray-900 flex items-center justify-center text-white text-center p-4">
            <div>
              <div className="text-6xl mb-4">{getSourceIcon()}</div>
              <p className="text-lg font-semibold mb-2">Đã sẵn sàng</p>
              <p className="text-sm text-gray-400">Nhấn "START" để bắt đầu stream</p>
              <div className="mt-4 px-3 py-1 bg-yellow-500/20 border border-yellow-500/40 rounded text-yellow-400 text-xs">
                ⏸ Preview Mode
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Check-in Section */}
      {isCheckInCamera && (
        <div className="px-4 py-3 bg-gradient-to-r from-blue-50 to-indigo-50 border-t border-blue-200 space-y-2">
          {/* Progress Indicator */}
          {progress && (
            <div className="bg-white rounded-lg p-3 border border-blue-200 shadow-sm">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-semibold text-gray-700">{progress.stage}</span>
                <span className="text-xs text-gray-500">{progress.percentage}%</span>
              </div>
              <div className="w-full bg-gray-200 rounded-full h-2 overflow-hidden">
                <div
                  className="bg-gradient-to-r from-blue-500 to-indigo-600 h-2 rounded-full transition-all duration-300"
                  style={{ width: `${progress.percentage}%` }}
                />
              </div>
            </div>
          )}

          {/* Test Capture Button */}
          <button
            onClick={handleTestCapture}
            disabled={isTestingCapture || !isStreaming}
            className={`w-full px-4 py-2 rounded-lg font-semibold transition-all ${
              isTestingCapture || !isStreaming
                ? 'bg-gray-300 text-gray-500 cursor-not-allowed'
                : 'bg-gradient-to-r from-purple-500 to-pink-600 text-white hover:shadow-lg hover:scale-105'
            }`}
            title={!isStreaming ? 'Vui lòng bắt đầu stream trước' : 'Test capture frame từ stream'}
          >
            {isTestingCapture ? (
              <>
                <span className="inline-block animate-spin mr-2">⏳</span>
                Đang test capture...
              </>
            ) : (
              <>
                <span className="mr-2">📸</span>
                Test Capture
              </>
            )}
          </button>

          {/* Test Capture Preview */}
          {testCaptureImage && (
            <div className="bg-white rounded-lg p-2 border border-purple-200">
              <p className="text-xs font-semibold text-gray-700 mb-1">✅ Capture thành công!</p>
              <img
                src={testCaptureImage}
                alt="Captured frame"
                className="w-full rounded border border-gray-200 max-h-32 object-contain"
              />
              <p className="text-xs text-gray-500 mt-1">
                Size: {(testCaptureImage.length / 1024).toFixed(1)} KB
              </p>
            </div>
          )}

          {/* Check-in Button */}
          <button
            onClick={handleCheckIn}
            disabled={isCheckingIn || !isStreaming || !parkingId || !cameraId}
            className={`w-full px-4 py-2 rounded-lg font-semibold transition-all ${
              isCheckingIn || !isStreaming || !parkingId || !cameraId
                ? 'bg-gray-300 text-gray-500 cursor-not-allowed'
                : 'bg-gradient-to-r from-blue-500 to-indigo-600 text-white hover:shadow-lg hover:scale-105'
            }`}
            title={
              !parkingId || !cameraId
                ? 'Vui lòng nhập Parking ID và Camera ID'
                : !isStreaming
                ? 'Vui lòng bắt đầu stream trước'
                : 'Check-in xe và OCR biển số'
            }
          >
            {isCheckingIn ? (
              <>
                <span className="inline-block animate-spin mr-2">⏳</span>
                Đang check-in...
              </>
            ) : (
              <>
                <span className="mr-2">🚗</span>
                Check-in
              </>
            )}
          </button>

          {/* Check-in Result */}
          {checkInResult && (
            <div
              className={`mt-2 p-3 rounded-lg text-sm ${
                checkInResult.error
                  ? 'bg-red-50 text-red-700 border border-red-200'
                  : 'bg-green-50 text-green-700 border border-green-200'
              }`}
            >
              {checkInResult.error ? (
                <div>
                  <div className="font-semibold mb-1">❌ Lỗi:</div>
                  <div className="text-xs">{checkInResult.error}</div>
                </div>
              ) : (
                <div>
                  <div className="font-semibold mb-1">✅ Check-in thành công!</div>
                  <div className="text-xs space-y-1">
                    <div>Biển số: <strong>{checkInResult.licensePlate}</strong></div>
                    <div>Vehicle ID: <strong className="font-mono text-xs">{checkInResult.vehicleId}</strong></div>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Camera Info */}
          {(parkingId || cameraId) && (
            <div className="mt-2 text-xs text-gray-600">
              <div>Parking: <strong>{parkingId || 'N/A'}</strong></div>
              <div>Camera: <strong>{cameraId || 'N/A'}</strong></div>
            </div>
          )}
        </div>
      )}

      {/* Footer - Stream URL */}
      <div className="px-4 py-2 bg-gray-50 border-t border-gray-100">
        <p className="text-xs text-gray-500 truncate font-mono" title={streamUrl}>
          {streamUrl}
        </p>
      </div>

      {/* Error Message */}
      {error && (
        <div className="px-4 py-2 text-xs text-red-600 bg-red-50 border-t border-red-200">
          ❌ {error}
        </div>
      )}
    </div>
  );
}

// ============================================
// MAIN COMPONENT
// ============================================
export function MultiStreamViewerPage() {
  const { user } = useAuth();
  const ownerId = user?.uid ?? '';
  
  // Stream configuration state
  const [tiles, setTiles] = useState<StreamTileConfig[]>([]);
  const [sourceType, setSourceType] = useState<SourceType>('esp32');
  const [selectedSourceId, setSelectedSourceId] = useState<string>('');
  const [customLabel, setCustomLabel] = useState<string>('');
  
  // NEW: Parking and camera config
  const [parkingId, setParkingId] = useState<string>('');
  const [cameraId, setCameraId] = useState<string>('');
  const [isCheckInCamera, setIsCheckInCamera] = useState<boolean>(false);
  const [parkingLots, setParkingLots] = useState<ParkingLot[]>([]);
  
  // NEW: Streaming control state
  const [isStreaming, setIsStreaming] = useState<boolean>(false);
  
  // ESP32 Cameras state (load from localStorage)
  const [esp32Cameras, setEsp32Cameras] = useState<ESP32Camera[]>(() => {
    try {
      const stored = localStorage.getItem(ESP32_STORAGE_KEY);
      if (stored) {
        return JSON.parse(stored);
      }
    } catch (error) {
      console.error('Error loading ESP32 cameras from localStorage:', error);
    }
    return DEFAULT_ESP32_CAMERAS;
  });

  // ESP32 Camera management state
  const [editingCamera, setEditingCamera] = useState<ESP32Camera | null>(null);
  const [newCameraName, setNewCameraName] = useState<string>('');
  const [newCameraIp, setNewCameraIp] = useState<string>('');

  // Save ESP32 cameras to localStorage whenever they change
  useEffect(() => {
    try {
      localStorage.setItem(ESP32_STORAGE_KEY, JSON.stringify(esp32Cameras));
    } catch (error) {
      console.error('Error saving ESP32 cameras to localStorage:', error);
    }
  }, [esp32Cameras]);
  
  // Load parking lots
  useEffect(() => {
    if (!ownerId) return;
    const loadParkingLots = async () => {
      try {
        const lots = await getParkingLotsByOwner(ownerId);
        setParkingLots(lots);
      } catch (error) {
        console.error('Error loading parking lots:', error);
      }
    };
    loadParkingLots();
  }, [ownerId]);

  // ESP32 Camera management functions
  const handleAddESP32Camera = () => {
    if (!newCameraName.trim() || !newCameraIp.trim()) {
      alert('Vui lòng nhập đầy đủ tên và IP address');
      return;
    }

    // Validate IP format (basic validation)
    try {
      const url = new URL(newCameraIp);
      if (!url.protocol.startsWith('http')) {
        alert('IP address phải bắt đầu bằng http:// hoặc https://');
        return;
      }
    } catch (error) {
      alert('IP address không hợp lệ. Ví dụ: http://192.168.1.100:81/stream');
      return;
    }

    const newCamera: ESP32Camera = {
      id: `esp32_${Date.now()}`,
      name: newCameraName.trim(),
      ip: newCameraIp.trim(),
    };

    setEsp32Cameras((prev) => [...prev, newCamera]);
    setNewCameraName('');
    setNewCameraIp('');
  };

  const handleEditESP32Camera = (camera: ESP32Camera) => {
    setEditingCamera(camera);
    setNewCameraName(camera.name);
    setNewCameraIp(camera.ip);
  };

  const handleUpdateESP32Camera = () => {
    if (!editingCamera || !newCameraName.trim() || !newCameraIp.trim()) {
      alert('Vui lòng nhập đầy đủ tên và IP address');
      return;
    }

    // Validate IP format
    try {
      const url = new URL(newCameraIp);
      if (!url.protocol.startsWith('http')) {
        alert('IP address phải bắt đầu bằng http:// hoặc https://');
        return;
      }
    } catch (error) {
      alert('IP address không hợp lệ. Ví dụ: http://192.168.1.100:81/stream');
      return;
    }

    setEsp32Cameras((prev) =>
      prev.map((cam) =>
        cam.id === editingCamera.id
          ? { ...cam, name: newCameraName.trim(), ip: newCameraIp.trim() }
          : cam
      )
    );
    setEditingCamera(null);
    setNewCameraName('');
    setNewCameraIp('');
  };

  const handleDeleteESP32Camera = (id: string) => {
    if (confirm('Bạn có chắc muốn xóa camera này?')) {
      setEsp32Cameras((prev) => prev.filter((cam) => cam.id !== id));
      // Clear selection if deleted camera was selected
      if (selectedSourceId === id) {
        setSelectedSourceId('');
      }
    }
  };

  const handleCancelEdit = () => {
    setEditingCamera(null);
    setNewCameraName('');
    setNewCameraIp('');
  };

  // Get stream URL based on source type and ID
  const getStreamUrl = (type: SourceType, sourceId: string): string => {
    switch (type) {
      case 'esp32': {
        const esp32 = esp32Cameras.find((cam) => cam.id === sourceId);
        return esp32 ? esp32.ip : '';
      }
      case 'video': {
        const video = VIDEO_FILES.find((vid) => vid.id === sourceId);
        return video ? `${FASTAPI_BASE}/stream?mode=video_file&file=${video.filename}` : '';
      }
      case 'mock':
        return `${FASTAPI_BASE}/stream?mode=mock`;
      default:
        return '';
    }
  };

  // Get default label based on source
  const getDefaultLabel = (type: SourceType, sourceId: string): string => {
    switch (type) {
      case 'esp32': {
        const esp32 = esp32Cameras.find((cam) => cam.id === sourceId);
        return esp32 ? esp32.name : 'ESP32 Camera';
      }
      case 'video': {
        const video = VIDEO_FILES.find((vid) => vid.id === sourceId);
        return video ? video.name : 'Video Stream';
    }
      case 'mock':
        return 'Mock FFmpeg Stream';
      default:
        return 'Camera Stream';
    }
  };

  // Handle add tile
  const handleAddTile = () => {
    if (!selectedSourceId && sourceType !== 'mock') {
      alert('Vui lòng chọn nguồn stream!');
      return;
    }

    const streamUrl = getStreamUrl(sourceType, selectedSourceId);
    if (!streamUrl) {
      alert('URL stream không hợp lệ!');
      return;
    }

    const defaultLabel = getDefaultLabel(sourceType, selectedSourceId);
    const finalLabel = customLabel.trim() || defaultLabel;

    const newTile: StreamTileConfig = {
      id: `${sourceType}_${selectedSourceId}_${Date.now()}`,
      label: finalLabel,
      sourceType,
      sourceId: selectedSourceId,
      streamUrl,
      parkingId: parkingId.trim() || undefined,
      cameraId: cameraId.trim() || undefined,
      isCheckInCamera: isCheckInCamera,
    };

    setTiles((prev) => [...prev, newTile]);
    
    // Reset form
    setCustomLabel('');
    setParkingId('');
    setCameraId('');
    setIsCheckInCamera(false);
  };

  // Handle remove tile
  const handleRemoveTile = (idToRemove: string) => {
    setTiles((prev) => prev.filter((tile) => tile.id !== idToRemove));
  };

  // Check if can add
  const canAdd = sourceType === 'mock' || (selectedSourceId !== '');

  return (
    <div className="min-h-screen bg-gradient-to-b from-strawberry-50 via-white to-matcha-50 p-6">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="mb-6">
          <h1 className="text-4xl font-bold text-strawberry-900 mb-2">
            🎬 Multi-Camera Viewer
          </h1>
          <p className="text-gray-600">
            Xem nhiều camera ESP32 hoặc video file đồng thời trên một màn hình
          </p>
        </div>

        {/* ESP32 Camera Management Panel */}
        <details className="bg-white rounded-xl shadow-lg p-6 mb-6 border border-gray-200">
          <summary className="cursor-pointer font-semibold text-strawberry-800 hover:text-strawberry-600 flex items-center gap-2 text-xl mb-4">
            <span>⚙️</span>
            <span>Quản lý ESP32 Cameras</span>
            <span className="text-sm font-normal text-gray-500 ml-auto">
              ({esp32Cameras.length} camera{esp32Cameras.length !== 1 ? 's' : ''})
            </span>
          </summary>
          
          <div className="mt-4 space-y-4">
            {/* Add/Edit Form */}
            <div className="bg-gray-50 rounded-lg p-4 border border-gray-200">
              <h3 className="font-semibold text-gray-700 mb-3">
                {editingCamera ? '✏️ Sửa Camera' : '➕ Thêm Camera Mới'}
              </h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-3">
                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">
                    Tên Camera
                  </label>
                  <input
                    type="text"
                    value={newCameraName}
                    onChange={(e) => setNewCameraName(e.target.value)}
                    placeholder="VD: ESP32-CAM 1, Entrance Gate"
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-strawberry-500 focus:border-strawberry-500 text-sm"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">
                    IP Address (Stream URL)
                  </label>
                  <input
                    type="text"
                    value={newCameraIp}
                    onChange={(e) => setNewCameraIp(e.target.value)}
                    placeholder="http://192.168.1.100:81/stream"
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-strawberry-500 focus:border-strawberry-500 text-sm font-mono"
                  />
                </div>
              </div>
              <div className="flex gap-2">
                {editingCamera ? (
                  <>
                    <button
                      onClick={handleUpdateESP32Camera}
                      className="px-4 py-2 bg-strawberry-500 text-white rounded-lg hover:bg-strawberry-600 transition font-medium text-sm"
                    >
                      💾 Lưu thay đổi
                    </button>
                    <button
                      onClick={handleCancelEdit}
                      className="px-4 py-2 bg-gray-200 text-gray-700 rounded-lg hover:bg-gray-300 transition font-medium text-sm"
                    >
                      ❌ Hủy
                    </button>
                  </>
                ) : (
                  <button
                    onClick={handleAddESP32Camera}
                    className="px-4 py-2 bg-strawberry-500 text-white rounded-lg hover:bg-strawberry-600 transition font-medium text-sm"
                  >
                    ➕ Thêm Camera
                  </button>
                )}
              </div>
              <p className="text-xs text-gray-500 mt-2">
                💡 Ví dụ IP: <code className="bg-white px-1 rounded">http://192.168.1.100:81/stream</code>
              </p>
            </div>

            {/* Camera List */}
            <div className="space-y-2">
              <h3 className="font-semibold text-gray-700">📹 Danh sách Cameras:</h3>
              {esp32Cameras.length === 0 ? (
                <div className="text-center py-4 text-gray-500 text-sm">
                  Chưa có camera nào. Hãy thêm camera mới.
                </div>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                  {esp32Cameras.map((camera) => (
                    <div
                      key={camera.id}
                      className="bg-white border border-gray-200 rounded-lg p-3 flex items-center justify-between hover:shadow-md transition"
                    >
                      <div className="flex-1 min-w-0">
                        <div className="font-semibold text-gray-800 truncate">{camera.name}</div>
                        <div className="text-xs text-gray-500 font-mono truncate" title={camera.ip}>
                          {camera.ip}
                        </div>
                      </div>
                      <div className="flex gap-1 ml-2">
                        <button
                          onClick={() => handleEditESP32Camera(camera)}
                          className="p-1.5 text-blue-600 hover:bg-blue-50 rounded transition"
                          title="Sửa"
                        >
                          ✏️
                        </button>
                        <button
                          onClick={() => handleDeleteESP32Camera(camera.id)}
                          className="p-1.5 text-red-600 hover:bg-red-50 rounded transition"
                          title="Xóa"
                        >
                          🗑️
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </details>

        {/* Add Stream Panel */}
        <div className="bg-white rounded-xl shadow-lg p-6 mb-6 border border-gray-200">
          <h2 className="text-xl font-semibold mb-4 text-strawberry-800 flex items-center gap-2">
            <span>➕</span>
            <span>Thêm Stream Mới</span>
          </h2>

          {/* Source Type Selection */}
          <div className="mb-6">
            <label className="block text-sm font-medium text-gray-700 mb-3">
              1️⃣ Chọn loại nguồn stream
            </label>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              {/* ESP32 */}
              <button
                onClick={() => {
                  setSourceType('esp32');
                  setSelectedSourceId('');
                }}
                className={`px-4 py-3 rounded-lg font-medium transition-all ${
                  sourceType === 'esp32'
                    ? 'bg-strawberry-500 text-white shadow-lg ring-2 ring-strawberry-300'
                    : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                }`}
              >
                <div className="text-3xl mb-1">📹</div>
                <div>ESP32-CAM</div>
                <div className="text-xs opacity-75">IP Camera</div>
              </button>

              {/* Video File */}
              <button
                onClick={() => {
                  setSourceType('video');
                  setSelectedSourceId('');
                }}
                className={`px-4 py-3 rounded-lg font-medium transition-all ${
                  sourceType === 'video'
                    ? 'bg-matcha-500 text-white shadow-lg ring-2 ring-matcha-300'
                    : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                }`}
              >
                <div className="text-3xl mb-1">🎬</div>
                <div>Video File</div>
                <div className="text-xs opacity-75">Test Video</div>
              </button>

              {/* Mock FFmpeg */}
              <button
                onClick={() => {
                  setSourceType('mock');
                  setSelectedSourceId('mock');
                }}
                className={`px-4 py-3 rounded-lg font-medium transition-all ${
                  sourceType === 'mock'
                    ? 'bg-purple-500 text-white shadow-lg ring-2 ring-purple-300'
                    : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                }`}
              >
                <div className="text-3xl mb-1">🧪</div>
                <div>Mock FFmpeg</div>
                <div className="text-xs opacity-75">FFmpeg Stream</div>
              </button>
            </div>
          </div>

          {/* Source Selection (ESP32 or Video) */}
          {sourceType !== 'mock' && (
            <div className="mb-6">
              <label className="block text-sm font-medium text-gray-700 mb-3">
                2️⃣ Chọn nguồn cụ thể
              </label>

              {/* ESP32 Selection */}
              {sourceType === 'esp32' && (
                <div>
                  {esp32Cameras.length === 0 ? (
                    <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4 text-center">
                      <p className="text-sm text-yellow-800 mb-2">
                        ⚠️ Chưa có ESP32 camera nào được cấu hình.
                      </p>
                      <p className="text-xs text-yellow-700">
                        Vui lòng thêm camera trong phần <strong>"Quản lý ESP32 Cameras"</strong> phía trên.
                      </p>
                    </div>
                  ) : (
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                      {esp32Cameras.map((cam) => (
                        <button
                          key={cam.id}
                          onClick={() => setSelectedSourceId(cam.id)}
                          className={`px-4 py-3 rounded-lg border-2 transition-all text-left ${
                            selectedSourceId === cam.id
                              ? 'border-strawberry-500 bg-strawberry-50 shadow-md'
                              : 'border-gray-200 bg-white hover:border-gray-300'
                          }`}
                        >
                          <div className="flex items-center gap-3">
                            <span className="text-2xl">📹</span>
                            <div className="flex-1 min-w-0">
                              <div className="font-semibold text-gray-800 truncate">{cam.name}</div>
                              <div className="text-xs text-gray-500 font-mono truncate" title={cam.ip}>
                                {cam.ip}
                              </div>
                            </div>
                            {selectedSourceId === cam.id && (
                              <span className="ml-auto text-strawberry-500 flex-shrink-0">✓</span>
                            )}
                          </div>
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {/* Video File Selection */}
              {sourceType === 'video' && (
                <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                  {VIDEO_FILES.map((video) => (
                    <button
                      key={video.id}
                      onClick={() => setSelectedSourceId(video.id)}
                      className={`px-4 py-3 rounded-lg border-2 transition-all text-left ${
                        selectedSourceId === video.id
                          ? 'border-matcha-500 bg-matcha-50 shadow-md'
                          : 'border-gray-200 bg-white hover:border-gray-300'
                      }`}
                    >
                      <div className="flex items-center gap-3">
                        <span className="text-2xl">🎬</span>
          <div>
                          <div className="font-semibold text-gray-800">{video.name}</div>
                          <div className="text-xs text-gray-500 font-mono">
                            {video.filename}
                          </div>
                        </div>
                        {selectedSourceId === video.id && (
                          <span className="ml-auto text-matcha-500">✓</span>
                        )}
                      </div>
                    </button>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Custom Label */}
          <div className="mb-6">
            <label className="block text-sm font-medium text-gray-700 mb-2">
              {sourceType === 'mock' ? '2️⃣' : '3️⃣'} Tên hiển thị (tùy chọn)
            </label>
              <input
                type="text"
              value={customLabel}
              onChange={(e) => setCustomLabel(e.target.value)}
              placeholder="Để trống để dùng tên mặc định"
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-strawberry-500 focus:border-strawberry-500"
            />
          </div>

          {/* Parking & Camera Config */}
          <div className="mb-6 space-y-4 p-4 bg-blue-50 rounded-lg border border-blue-200">
            <label className="block text-sm font-semibold text-blue-900 mb-2">
              {sourceType === 'mock' ? '3️⃣' : '4️⃣'} Cấu hình Parking & Camera
            </label>
            
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {/* Parking ID */}
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">
                  Parking Lot ID
                </label>
                <select
                  value={parkingId}
                  onChange={(e) => setParkingId(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-sm"
                >
                  <option value="">-- Chọn Parking Lot --</option>
                  {parkingLots.map((lot) => (
                    <option key={lot.id} value={lot.id}>
                      {lot.name} ({lot.id})
                    </option>
                  ))}
                </select>
              </div>

              {/* Camera ID */}
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">
                  Camera ID
                </label>
                <input
                  type="text"
                  value={cameraId}
                  onChange={(e) => setCameraId(e.target.value)}
                  placeholder="VD: CAM1, CAM2, CAM3"
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-sm"
                />
              </div>
            </div>

            {/* Check-in Camera Checkbox */}
            <div className="flex items-center gap-2 pt-2">
              <input
                type="checkbox"
                id="checkInCamera"
                checked={isCheckInCamera}
                onChange={(e) => setIsCheckInCamera(e.target.checked)}
                className="w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
              />
              <label htmlFor="checkInCamera" className="text-sm font-medium text-gray-700 cursor-pointer">
                🚗 Sử dụng camera này cho Check-in (Cam1 - trước barrier)
              </label>
            </div>
            
            <p className="text-xs text-gray-600 mt-2">
              💡 <strong>Lưu ý:</strong> Chỉ đánh dấu camera ở vị trí trước barrier (Cam1) làm Check-in camera. 
              Các camera khác (Cam2, Cam3) sẽ dùng để tracking xe vào chỗ đậu.
            </p>
          </div>

          {/* Add Button */}
          <div className="flex justify-end">
            <button
              onClick={handleAddTile}
              disabled={!canAdd}
              className={`px-6 py-3 rounded-lg font-semibold transition-all ${
                canAdd
                  ? 'bg-gradient-to-r from-strawberry-500 to-matcha-500 text-white hover:shadow-lg'
                  : 'bg-gray-200 text-gray-400 cursor-not-allowed'
              }`}
            >
              ➕ Thêm Stream
            </button>
          </div>

          {/* Info Box */}
          <div className="mt-4 p-4 bg-gradient-to-r from-blue-50 to-indigo-50 border-2 border-blue-200 rounded-lg">
            <div className="flex items-start gap-3">
              <span className="text-blue-600 text-2xl">💡</span>
              <div className="text-sm text-blue-800 flex-1">
                <p className="font-bold mb-2 text-base">📋 Workflow Mới:</p>
                <ol className="list-decimal list-inside space-y-2 text-blue-700">
                  <li className="font-semibold">
                    <strong>BƯỚC 1:</strong> Thêm nhiều stream vào (ESP32-CAM hoặc Video File)
                    <p className="ml-6 mt-1 font-normal text-xs text-blue-600">
                      → Stream sẽ ở chế độ Preview (chưa load video)
                    </p>
                  </li>
                  <li className="font-semibold">
                    <strong>BƯỚC 2:</strong> Nhấn nút <span className="px-2 py-0.5 bg-green-500 text-white rounded">▶️ START ALL STREAMS</span>
                    <p className="ml-6 mt-1 font-normal text-xs text-blue-600">
                      → Tất cả streams sẽ bắt đầu chạy cùng lúc!
                    </p>
                  </li>
                  <li className="font-semibold">
                    <strong>BƯỚC 3:</strong> Nhấn <span className="px-2 py-0.5 bg-red-500 text-white rounded">⏹ STOP</span> để dừng tất cả
                  </li>
                </ol>
                <div className="mt-3 p-2 bg-yellow-50 border border-yellow-300 rounded text-yellow-800 text-xs">
                  <strong>💪 Ưu điểm:</strong> Thêm nhiều camera trước, rồi start cùng lúc → Đồng bộ và dễ quản lý!
                </div>
              </div>
            </div>
          </div>
      </div>

        {/* Stream Grid */}
        {tiles.length === 0 ? (
          <div className="bg-white rounded-xl shadow border border-dashed border-gray-300 p-12 text-center">
            <div className="text-6xl mb-4">📺</div>
            <h3 className="text-xl font-semibold text-gray-700 mb-2">
              Chưa có stream nào
            </h3>
            <p className="text-gray-500">
              Sử dụng bảng điều khiển phía trên để thêm camera hoặc video stream
            </p>
          </div>
        ) : (
          <div>
            {/* Control Bar */}
            <div className="flex items-center justify-between mb-6 bg-white rounded-xl shadow-lg p-4 border border-gray-200">
              <div className="flex items-center gap-4">
                <h2 className="text-xl font-semibold text-gray-800">
                  📺 Streams ({tiles.length})
                </h2>
                <div className={`px-3 py-1 rounded-full text-sm font-semibold ${
                  isStreaming
                    ? 'bg-green-100 text-green-700'
                    : 'bg-gray-100 text-gray-600'
                }`}>
                  {isStreaming ? '🟢 Live' : '⚪ Standby'}
                </div>
              </div>
              
              <div className="flex items-center gap-3">
                {/* START/STOP Button */}
                <button
                  onClick={() => setIsStreaming(!isStreaming)}
                  className={`px-6 py-3 rounded-lg font-bold transition-all shadow-md ${
                    isStreaming
                      ? 'bg-red-500 text-white hover:bg-red-600 hover:shadow-lg'
                      : 'bg-gradient-to-r from-green-500 to-emerald-500 text-white hover:shadow-xl hover:scale-105'
                  }`}
                >
                  {isStreaming ? (
                    <>
                      <span className="text-lg">⏹</span>
                      <span className="ml-2">STOP</span>
                    </>
                  ) : (
                    <>
                      <span className="text-lg">▶️</span>
                      <span className="ml-2">START ALL STREAMS</span>
                    </>
                  )}
                </button>
                
                {/* Clear All Button */}
                <button
                  onClick={() => {
                    setTiles([]);
                    setIsStreaming(false);
                  }}
                  className="px-4 py-3 bg-red-100 text-red-700 rounded-lg hover:bg-red-200 transition font-medium text-sm"
                  title="Xóa tất cả streams"
                >
                  🗑️ Xóa tất cả
                </button>
              </div>
            </div>

            {/* Stream Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-5">
              {tiles.map((tile) => (
                <StreamViewerTile
                  key={tile.id}
                  {...tile}
                  onRemove={handleRemoveTile}
                  isStreaming={isStreaming}
                  ownerId={ownerId}
                />
              ))}
            </div>
          </div>
        )}

        {/* Configuration Guide */}
        <details className="mt-8 bg-white rounded-xl shadow border border-gray-200 p-6">
          <summary className="cursor-pointer font-semibold text-gray-800 hover:text-strawberry-600 flex items-center gap-2">
            <span>⚙️</span>
            <span>Cấu hình ESP32 & Video Files</span>
          </summary>
          <div className="mt-4 space-y-4 text-sm text-gray-700">
            {/* ESP32 Configuration */}
            <div className="bg-strawberry-50 rounded-lg p-4">
              <h4 className="font-semibold text-strawberry-800 mb-2">📹 Cấu hình ESP32-CAM</h4>
              <p className="mb-2">
                ✅ Bây giờ bạn có thể quản lý ESP32 cameras trực tiếp trên web!
              </p>
              <p className="mb-2 text-sm text-strawberry-700">
                Sử dụng phần <strong>"Quản lý ESP32 Cameras"</strong> ở trên để thêm, sửa, xóa cameras.
                Cấu hình sẽ được lưu tự động vào localStorage.
              </p>
              <p className="text-xs text-strawberry-600 mt-2">
                💡 Format IP: <code className="bg-white px-1 rounded">http://192.168.1.100:81/stream</code>
              </p>
            </div>

            {/* Video Files Configuration */}
            <div className="bg-matcha-50 rounded-lg p-4">
              <h4 className="font-semibold text-matcha-800 mb-2">🎬 Cấu hình Video Files</h4>
              <p className="mb-2">1. Đặt video files vào thư mục <code className="bg-white px-2 py-0.5 rounded">server/stream/</code></p>
              <p className="mb-2">2. Sửa config trong <code className="bg-white px-2 py-0.5 rounded">MultiStreamViewerPage.tsx</code>:</p>
              <pre className="bg-white p-3 rounded border border-matcha-200 text-xs overflow-x-auto">
{`const VIDEO_FILES = [
  { id: 'video_1', name: 'Video 1 - Parking A', filename: 'parking_a.mp4' },
  { id: 'video_2', name: 'Video 2 - Parking B', filename: 'parking_b.mp4' },
  { id: 'video_3', name: 'Video 3 - Parking C', filename: 'parking_c.mp4' },
];`}
              </pre>
              <p className="mt-2 text-xs text-matcha-700">
                ⚠️ FastAPI phải hỗ trợ endpoint: <code className="bg-white px-1 rounded">/stream?mode=video_file&file=filename.mp4</code>
              </p>
            </div>

            {/* Mock FFmpeg */}
            <div className="bg-purple-50 rounded-lg p-4">
              <h4 className="font-semibold text-purple-800 mb-2">🧪 Mock FFmpeg Stream</h4>
              <p className="mb-2">Chạy script FFmpeg mock (Windows):</p>
              <pre className="bg-white p-3 rounded border border-purple-200 text-xs">
cd server
.\stream_video_mock.bat
              </pre>
              <p className="mt-2 text-xs text-purple-700">
                Stream sẽ available tại: <code className="bg-white px-1 rounded">http://localhost:8081/stream</code>
              </p>
            </div>
          </div>
        </details>
      </div>
    </div>
  );
}


