import { useState, useRef, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import { performVehicleCheckIn } from '../services/checkInService';
import { getParkingLotsByOwner } from '../services/parkingLotService';
import { 
  getUserESP32Configs, 
  saveESP32Config, 
  deleteESP32Config, 
  setDefaultESP32,
  type ESP32Config 
} from '../services/esp32ConfigService';
import { saveCameraConfig } from '../services/cameraConfigService';
import type { ParkingLot } from '../types/parkingLot.types';

// ============================================
// STREAM SOURCE CONFIGURATION
// ============================================

// Get backend URL from environment variable
const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || 'http://localhost:8069';

// ESP32-CAM IP Addresses (Predefined options)
const ESP32_CAMERAS = [
  { id: 'esp32_custom', name: '✏️ Custom ESP32 IP', ip: 'custom' }, // NEW: Custom option
];

// Video Files (Cấu hình 3 video files)
const VIDEO_FILES = [
  { id: 'video_1', name: 'Video 1 - Parking A', filename: 'parking_a.mp4' },
  { id: 'video_2', name: 'Video 2 - Parking B', filename: 'parking_b.mp4' },
  { id: 'video_3', name: 'Video 3 - Parking C', filename: 'parking_c.mp4' },
];

type SourceType = 'esp32' | 'video';
type TileStatus = 'idle' | 'connected' | 'error';

interface StreamTileConfig {
  id: string;
  label: string;
  sourceType: SourceType;
  sourceId: string; // esp32_1, video_1, etc.
  streamUrl: string;
  parkingId?: string; // NEW: Parking Lot ID
  cameraId?: string; // NEW: Camera ID
  isCheckInCamera?: boolean; // NEW: Is this the check-in camera (Cam1)?
  showDetection?: boolean; // NEW: Show detection stream
}

interface StreamTileProps extends StreamTileConfig {
  onRemove: (id: string) => void;
  onToggleDetection: (id: string) => void; // NEW: Toggle detection
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
  onToggleDetection,
  isStreaming,
  parkingId,
  cameraId,
  isCheckInCamera,
  ownerId,
  showDetection = false,
}: StreamTileProps) {
  const [status, setStatus] = useState<TileStatus>('idle');
  const [error, setError] = useState<string | null>(null);
  const [isCheckingIn, setIsCheckingIn] = useState(false);
  const [checkInResult, setCheckInResult] = useState<{ vehicleId?: string; licensePlate?: string; error?: string } | null>(null);
  const [isTestingCapture, setIsTestingCapture] = useState(false);
  const [testCaptureImage, setTestCaptureImage] = useState<string | null>(null);
  const [progress, setProgress] = useState<{ stage: string; percentage: number } | null>(null);
  const imgRef = useRef<HTMLImageElement>(null);

  // Get detection stream URL
  const getDetectionStreamUrl = (rawStreamUrl: string): string => {
    try {
      // If it's a proxy URL, convert to detection proxy
      if (rawStreamUrl.includes('/stream/proxy')) {
        const url = new URL(rawStreamUrl, window.location.origin);
        const esp32Url = url.searchParams.get('esp32_url');
        if (esp32Url) {
          return `${BACKEND_URL}/stream/detect?user_esp32=${encodeURIComponent(esp32Url)}`;
        }
      }
      
      // If it's a video file stream
      if (rawStreamUrl.includes('mode=video_file')) {
        // Replace /stream with /stream/detect
        return rawStreamUrl.replace('/stream?', '/stream/detect?');
      }
      
      // Default raw stream from backend
      if (rawStreamUrl.includes('/stream') && !rawStreamUrl.includes('/stream/detect')) {
        return rawStreamUrl.replace('/stream', '/stream/detect');
      }
      
      return rawStreamUrl;
    } catch (error) {
      console.error('Error generating detection URL:', error);
      return rawStreamUrl;
    }
  };

  // Use detection URL if showDetection is true
  const actualStreamUrl = showDetection ? getDetectionStreamUrl(streamUrl) : streamUrl;

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
            const imageData = canvas.toDataURL('image/jpeg', 0.85);
            console.log('✅ Captured frame from <img> element (current frame)');
            return imageData;
          }
        } catch (canvasError) {
          console.warn('⚠️ Canvas capture failed (CORS?), trying snapshot endpoint...', canvasError);
        }
      }
      
      // Option 2: Video file - dùng snapshot endpoint (fallback nếu canvas không được)
      if (sourceType === 'video') {
        const urlParams = new URLSearchParams(streamUrl.split('?')[1] || '');
        const file = urlParams.get('file');
        
        if (file) {
          console.log('📸 Getting snapshot from video file via backend (fallback)...');
          
          // Fetch với timeout
          const controller = new AbortController();
          const timeoutId = setTimeout(() => controller.abort(), 5000); // 5s timeout
          
          try {
            const response = await fetch(
              `${BACKEND_URL}/api/stream/snapshot?mode=video_file&file=${encodeURIComponent(file)}`,
              { signal: controller.signal }
            );
            clearTimeout(timeoutId);
            
            if (!response.ok) {
              throw new Error(`Snapshot failed: ${response.status}`);
            }
            
            const data = await response.json();
            if (data.success && data.imageData) {
              console.log('✅ Got snapshot from backend (may not be current frame)');
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
          {/* Detection Toggle Button */}
          <button
            onClick={() => onToggleDetection(id)}
            className={`text-xs font-semibold px-3 py-1 rounded-full transition-all ${
              showDetection
                ? 'bg-blue-600 text-white hover:bg-blue-700'
                : 'bg-gray-200 text-gray-600 hover:bg-gray-300'
            }`}
            title={showDetection ? 'Tắt detection' : 'Bật detection'}
          >
            {showDetection ? '🔍 ON' : '📹 RAW'}
          </button>
          
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
              src={actualStreamUrl}
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

            {/* Detection Mode Indicator */}
            {status === 'connected' && showDetection && (
              <div className="absolute top-3 right-3 bg-blue-600 text-white px-3 py-1 rounded-full text-xs font-semibold flex items-center gap-2">
                <span>🔍</span>
                DETECTION
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
  const [customESP32IP, setCustomESP32IP] = useState<string>(''); // NEW: Custom ESP32 IP input
  
  // NEW: Parking and camera config
  const [parkingId, setParkingId] = useState<string>('');
  const [isCheckInCamera, setIsCheckInCamera] = useState<boolean>(false);
  const [parkingLots, setParkingLots] = useState<ParkingLot[]>([]);
  
  // NEW: Streaming control state
  const [isStreaming, setIsStreaming] = useState<boolean>(false);
  
  // NEW: Saved ESP32 configs
  const [savedESP32Configs, setSavedESP32Configs] = useState<ESP32Config[]>([]);
  const [showSaveDialog, setShowSaveDialog] = useState<boolean>(false);
  const [saveConfigName, setSaveConfigName] = useState<string>('');
  const [isSavingConfig, setIsSavingConfig] = useState<boolean>(false);
  
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

  // Load saved ESP32 configs
  useEffect(() => {
    if (!ownerId) return;
    const loadESP32Configs = async () => {
      try {
        const configs = await getUserESP32Configs(ownerId);
        setSavedESP32Configs(configs);
        console.log(`✅ Loaded ${configs.length} saved ESP32 configs`);
      } catch (error) {
        console.error('Error loading ESP32 configs:', error);
      }
    };
    loadESP32Configs();
  }, [ownerId]);

  // Handle save ESP32 config
  const handleSaveESP32Config = async () => {
    if (!ownerId || !customESP32IP.trim() || !saveConfigName.trim()) {
      alert('Vui lòng nhập đầy đủ tên và IP address!');
      return;
    }

    setIsSavingConfig(true);
    try {
      await saveESP32Config(ownerId, saveConfigName.trim(), customESP32IP.trim(), false);
      
      // Reload configs
      const configs = await getUserESP32Configs(ownerId);
      setSavedESP32Configs(configs);
      
      alert(`✅ Đã lưu ESP32 config: ${saveConfigName}`);
      setShowSaveDialog(false);
      setSaveConfigName('');
    } catch (error) {
      console.error('Error saving ESP32 config:', error);
      alert('❌ Lỗi khi lưu config. Vui lòng thử lại.');
    } finally {
      setIsSavingConfig(false);
    }
  };

  // Handle delete ESP32 config
  const handleDeleteESP32Config = async (configId: string, configName: string) => {
    if (!confirm(`Xóa ESP32 config "${configName}"?`)) {
      return;
    }

    try {
      await deleteESP32Config(configId);
      
      // Reload configs
      const configs = await getUserESP32Configs(ownerId);
      setSavedESP32Configs(configs);
      
      alert(`✅ Đã xóa config: ${configName}`);
    } catch (error) {
      console.error('Error deleting ESP32 config:', error);
      alert('❌ Lỗi khi xóa config. Vui lòng thử lại.');
    }
  };

  // Handle set default ESP32
  const handleSetDefaultESP32 = async (configId: string) => {
    try {
      await setDefaultESP32(ownerId, configId);
      
      // Reload configs
      const configs = await getUserESP32Configs(ownerId);
      setSavedESP32Configs(configs);
      
      alert('✅ Đã đặt làm ESP32 mặc định');
    } catch (error) {
      console.error('Error setting default ESP32:', error);
      alert('❌ Lỗi khi đặt ESP32 mặc định. Vui lòng thử lại.');
    }
  };

  // Get stream URL based on source type and ID
  const getStreamUrl = (type: SourceType, sourceId: string, customIP?: string): string => {
    switch (type) {
      case 'esp32': {
        // If custom ESP32 or saved ESP32 with customIP provided
        if ((sourceId === 'esp32_custom' || sourceId === 'esp32_saved') && customIP) {
          // Ensure IP has protocol
          const ip = customIP.startsWith('http') ? customIP : `http://${customIP}`;
          // Proxy through backend
          return `${BACKEND_URL}/stream/proxy?esp32_url=${encodeURIComponent(ip)}`;
        }
        
        // Predefined ESP32
        const esp32 = ESP32_CAMERAS.find((cam) => cam.id === sourceId);
        if (esp32 && esp32.ip !== 'custom') {
          // Proxy through backend
          return `${BACKEND_URL}/stream/proxy?esp32_url=${encodeURIComponent(esp32.ip)}`;
        }
        return '';
      }
      case 'video': {
        const video = VIDEO_FILES.find((vid) => vid.id === sourceId);
        return video ? `${BACKEND_URL}/stream?mode=video_file&file=${video.filename}` : '';
      }
      default:
        return '';
    }
  };

  // Get default label based on source
  const getDefaultLabel = (type: SourceType, sourceId: string, customIP?: string): string => {
    switch (type) {
      case 'esp32': {
        if ((sourceId === 'esp32_custom' || sourceId === 'esp32_saved') && customIP) {
          return `ESP32 (${customIP})`;
        }
        const esp32 = ESP32_CAMERAS.find((cam) => cam.id === sourceId);
        return esp32 ? esp32.name : 'ESP32 Camera';
      }
      case 'video': {
        const video = VIDEO_FILES.find((vid) => vid.id === sourceId);
        return video ? video.name : 'Video Stream';
    }
      default:
        return 'Camera Stream';
    }
  };

  // Handle add tile
  const handleAddTile = async () => {
    if (!selectedSourceId) {
      alert('Vui lòng chọn nguồn stream!');
      return;
    }

    // Validate custom ESP32 IP
    if (sourceType === 'esp32' && (selectedSourceId === 'esp32_custom' || selectedSourceId === 'esp32_saved')) {
      if (!customESP32IP.trim()) {
        alert('Vui lòng nhập IP address của ESP32-CAM!');
        return;
      }
    }

    const streamUrl = getStreamUrl(sourceType, selectedSourceId, customESP32IP.trim());
    if (!streamUrl) {
      console.error('Invalid stream URL:', streamUrl);
      alert('URL stream không hợp lệ! ');
      return;
    }

    const defaultLabel = getDefaultLabel(sourceType, selectedSourceId, customESP32IP.trim());
    const finalLabel = customLabel.trim() || defaultLabel;

    // Auto-generate Camera ID from source
    let autoCameraId = '';
    if (sourceType === 'esp32') {
      // Use ESP32 IP or name as camera ID
      autoCameraId = customESP32IP.trim() || selectedSourceId;
    } else if (sourceType === 'video') {
      // Use video filename as camera ID
      const video = VIDEO_FILES.find(v => v.id === selectedSourceId);
      autoCameraId = video?.filename.replace('.mp4', '') || selectedSourceId;
    }

    const newTile: StreamTileConfig = {
      id: `${sourceType}_${selectedSourceId}_${Date.now()}`,
      label: finalLabel,
      sourceType,
      sourceId: selectedSourceId,
      streamUrl,
      parkingId: parkingId.trim() || undefined,
      cameraId: autoCameraId || undefined,
      isCheckInCamera: isCheckInCamera,
    };

    setTiles((prev) => [...prev, newTile]);
    
    // Save camera configuration if parking lot is provided
    if (ownerId && parkingId.trim() && autoCameraId) {
      console.log('[MultiStreamViewer] 💾 Attempting to save camera config:', {
        ownerId,
        parkingLotId: parkingId.trim(),
        cameraId: autoCameraId,
        sourceType,
        selectedSourceId,
        customESP32IP: customESP32IP.trim()
      });
      
      try {
        let sourceUrl = '';
        if (sourceType === 'esp32') {
          sourceUrl = customESP32IP.trim() || selectedSourceId;
        } else if (sourceType === 'video') {
          const video = VIDEO_FILES.find(v => v.id === selectedSourceId);
          sourceUrl = video?.filename || selectedSourceId;
        }
        
        console.log('[MultiStreamViewer] 📤 Calling saveCameraConfig with sourceUrl:', sourceUrl);
        
        await saveCameraConfig({
          ownerId,
          parkingLotId: parkingId.trim(),
          cameraId: autoCameraId,
          sourceType: sourceType === 'esp32' ? 'esp32' : 'video',
          sourceUrl,
          label: finalLabel,
        });
        console.log(`[MultiStreamViewer] ✅ Camera config saved successfully: ${parkingId.trim()}/${autoCameraId}`);
      } catch (error) {
        console.error('[MultiStreamViewer] ❌ Failed to save camera config:', error);
        // Don't show error to user, just log it
      }
    } else {
      console.log('[MultiStreamViewer] ⏭️ Skipping camera config save - missing required fields:', {
        hasOwnerId: !!ownerId,
        hasParkingId: !!parkingId.trim(),
        hasAutoCameraId: !!autoCameraId
      });
    }
    
    // Reset form
    setCustomLabel('');
    setCustomESP32IP('');
    setParkingId('');
    setIsCheckInCamera(false);
  };

  // Handle remove tile
  const handleRemoveTile = (idToRemove: string) => {
    setTiles((prev) => prev.filter((tile) => tile.id !== idToRemove));
  };

  // Handle toggle detection
  const handleToggleDetection = (idToToggle: string) => {
    setTiles((prev) =>
      prev.map((tile) =>
        tile.id === idToToggle
          ? { ...tile, showDetection: !tile.showDetection }
          : tile
      )
    );
  };

  // Check if can add
  const canAdd = selectedSourceId !== '' && 
    (sourceType !== 'esp32' || 
     (selectedSourceId !== 'esp32_custom' && selectedSourceId !== 'esp32_saved') || 
     customESP32IP.trim() !== '');

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

        {/* Add Stream Panel */}
        <div className="bg-white rounded-xl shadow-lg p-6 mb-6 border border-gray-200">
          <h2 className="text-xl font-semibold mb-4 text-strawberry-800 flex items-center gap-2">
            <span>➕</span>
            <span>Thêm Stream Mới</span>
          </h2>

          {/* CRITICAL WARNING - HOW TO SAVE CAMERAS */}
          <div className="mb-6 p-4 bg-gradient-to-r from-blue-50 to-indigo-50 border-2 border-blue-400 rounded-xl shadow-md">
            <div className="flex items-start gap-3">
              <span className="text-4xl">💡</span>
              <div className="flex-1">
                <h3 className="font-bold text-lg text-blue-900 mb-2">
                  🎯 Cách lưu camera để sử dụng lại
                </h3>
                <div className="space-y-2 text-sm text-blue-800">
                  <p className="font-semibold">
                    📝 Để camera được lưu vào Firebase và xuất hiện trong <code className="bg-blue-100 px-2 py-1 rounded">/stream/host-multi</code>:
                  </p>
                  <div className="ml-4 space-y-1">
                    <p>✅ <strong>Chọn Parking Lot ID</strong> từ dropdown bên dưới</p>
                    <p>✅ <strong>Camera ID sẽ tự động tạo</strong> từ tên nguồn stream (ESP32 IP hoặc tên video)</p>
                  </div>
                  <p className="mt-3 p-3 bg-green-100 border border-green-400 rounded">
                    <strong>🎉 ĐƠN GIẢN:</strong> Chỉ cần chọn Parking Lot → Camera tự động lưu → Sử dụng lại ở /stream/host-multi!
                  </p>
                </div>
              </div>
            </div>
          </div>

          {/* Source Type Selection */}
          <div className="mb-6">
            <label className="block text-sm font-medium text-gray-700 mb-3">
              1️⃣ Chọn loại nguồn stream
            </label>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {/* ESP32 */}
              <button
                onClick={() => {
                  setSourceType('esp32');
                  setSelectedSourceId('');
                  setCustomESP32IP('');
                }}
                className={`px-4 py-3 rounded-lg font-medium transition-all ${
                  sourceType === 'esp32'
                    ? 'bg-strawberry-500 text-white shadow-lg ring-2 ring-strawberry-300'
                    : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                }`}
              >
                <div className="text-3xl mb-1">📹</div>
                <div>ESP32-CAM</div>
                <div className="text-xs opacity-75">IP Camera (via Backend)</div>
              </button>

              {/* Video File */}
              <button
                onClick={() => {
                  setSourceType('video');
                  setSelectedSourceId('');
                  setCustomESP32IP('');
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
            </div>
            
            <div className="mt-3 p-3 bg-blue-50 border border-blue-200 rounded-lg text-sm text-blue-800">
              <strong>💡 Lưu ý:</strong> Tất cả streams đều đi qua backend (<code className="bg-blue-100 px-1 rounded">{BACKEND_URL}</code>)
            </div>
          </div>

          {/* Source Selection (ESP32 or Video) */}
          <div className="mb-6">
            <label className="block text-sm font-medium text-gray-700 mb-3">
              2️⃣ Chọn nguồn cụ thể
            </label>

            {/* ESP32 Selection */}
            {sourceType === 'esp32' && (
              <div className="space-y-4">
                {/* Saved ESP32 Configs */}
                {savedESP32Configs.length > 0 && (
                  <div>
                    <label className="block text-xs font-medium text-gray-600 mb-2">
                      💾 Saved ESP32 Cameras:
                    </label>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                      {savedESP32Configs.map((config) => (
                        <button
                          key={config.id}
                          onClick={() => {
                            setSelectedSourceId('esp32_saved');
                            setCustomESP32IP(config.ipAddress);
                            setCustomLabel(config.name);
                          }}
                          className={`px-4 py-3 rounded-lg border-2 transition-all text-left relative ${
                            selectedSourceId === 'esp32_saved' && customESP32IP === config.ipAddress
                              ? 'border-strawberry-500 bg-strawberry-50 shadow-md'
                              : 'border-gray-200 bg-white hover:border-gray-300'
                          }`}
                        >
                          <div className="flex items-center gap-3">
                            <span className="text-2xl">{config.isDefault ? '⭐' : '📹'}</span>
                            <div className="flex-1 min-w-0">
                              <div className="font-semibold text-gray-800 flex items-center gap-2">
                                {config.name}
                                {config.isDefault && (
                                  <span className="text-xs bg-yellow-100 text-yellow-700 px-2 py-0.5 rounded">
                                    Default
                                  </span>
                                )}
                              </div>
                              <div className="text-xs text-gray-500 font-mono truncate">
                                {config.ipAddress}
                              </div>
                            </div>
                            {selectedSourceId === 'esp32_saved' && customESP32IP === config.ipAddress && (
                              <span className="text-strawberry-500">✓</span>
                            )}
                          </div>
                          {/* Action buttons */}
                          <div className="absolute top-2 right-2 flex gap-1">
                            {!config.isDefault && (
                              <button
                                onClick={(e) => {
                                  e.stopPropagation();
                                  handleSetDefaultESP32(config.id);
                                }}
                                className="p-1 bg-yellow-100 hover:bg-yellow-200 text-yellow-700 rounded text-xs"
                                title="Đặt làm mặc định"
                              >
                                ⭐
                              </button>
                            )}
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                handleDeleteESP32Config(config.id, config.name);
                              }}
                              className="p-1 bg-red-100 hover:bg-red-200 text-red-700 rounded text-xs"
                              title="Xóa config"
                            >
                              🗑️
                            </button>
                          </div>
                        </button>
                      ))}
                    </div>
                  </div>
                )}
                
                {/* Custom ESP32 Button */}
                <div>
                  {savedESP32Configs.length > 0 && (
                    <label className="block text-xs font-medium text-gray-600 mb-2 mt-4">
                      Or add new ESP32:
                    </label>
                  )}
                  <div className="grid grid-cols-1 gap-3">
                    {ESP32_CAMERAS.map((cam) => (
                      <button
                        key={cam.id}
                        onClick={() => {
                          setSelectedSourceId(cam.id);
                          if (cam.id === 'esp32_custom') {
                            setCustomESP32IP('');
                            setCustomLabel('');
                          }
                        }}
                        className={`px-4 py-3 rounded-lg border-2 transition-all text-left ${
                          selectedSourceId === cam.id && selectedSourceId !== 'esp32_saved'
                            ? 'border-strawberry-500 bg-strawberry-50 shadow-md'
                            : 'border-gray-200 bg-white hover:border-gray-300'
                        }`}
                      >
                        <div className="flex items-center gap-3">
                          <span className="text-2xl">✏️</span>
                          <div className="flex-1">
                            <div className="font-semibold text-gray-800">{cam.name}</div>
                            <div className="text-xs text-gray-500">Enter new IP address</div>
                          </div>
                          {selectedSourceId === cam.id && selectedSourceId !== 'esp32_saved' && (
                            <span className="ml-auto text-strawberry-500">✓</span>
                          )}
                        </div>
                      </button>
                    ))}
                  </div>
                </div>
                
                {/* Custom ESP32 IP Input */}
                {selectedSourceId === 'esp32_custom' && (
                  <div className="p-4 bg-yellow-50 border-2 border-yellow-300 rounded-lg space-y-4">
                    {/* IP Input */}
                    <label className="block text-sm font-semibold text-yellow-900 mb-2">
                      ✏️ Nhập IP address của ESP32-CAM:
                    </label>
                    <div className="flex gap-2">
                      <input
                        type="text"
                        value={customESP32IP}
                        onChange={(e) => setCustomESP32IP(e.target.value)}
                        placeholder="VD: 192.168.1.100:81 hoặc http://192.168.1.100:81"
                        className="flex-1 px-4 py-2 border-2 border-yellow-400 rounded-lg focus:ring-2 focus:ring-yellow-500 focus:border-yellow-500 font-mono text-sm"
                      />
                      <button
                        onClick={() => setShowSaveDialog(true)}
                        disabled={!customESP32IP.trim()}
                        className={`px-4 py-2 rounded-lg font-semibold transition ${
                          customESP32IP.trim()
                            ? 'bg-green-500 text-white hover:bg-green-600'
                            : 'bg-gray-300 text-gray-500 cursor-not-allowed'
                        }`}
                        title="Lưu config này"
                      >
                        💾 Save
                      </button>
                    </div>
                    
                    {/* Save Dialog */}
                    {showSaveDialog && (
                      <div className="mt-3 p-4 bg-green-50 border-2 border-green-300 rounded-lg">
                        <label className="block text-sm font-semibold text-green-900 mb-2">
                          💾 Đặt tên cho ESP32 config:
                        </label>
                        <input
                          type="text"
                          value={saveConfigName}
                          onChange={(e) => setSaveConfigName(e.target.value)}
                          placeholder="VD: ESP32 Cam1, Camera Bãi Xe"
                          className="w-full px-4 py-2 border-2 border-green-400 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-green-500 mb-3"
                          autoFocus
                        />
                        <div className="flex gap-2">
                          <button
                            onClick={handleSaveESP32Config}
                            disabled={isSavingConfig || !saveConfigName.trim()}
                            className={`flex-1 px-4 py-2 rounded-lg font-semibold transition ${
                              isSavingConfig || !saveConfigName.trim()
                                ? 'bg-gray-300 text-gray-500 cursor-not-allowed'
                                : 'bg-green-600 text-white hover:bg-green-700'
                            }`}
                          >
                            {isSavingConfig ? '⏳ Đang lưu...' : '✅ Lưu'}
                          </button>
                          <button
                            onClick={() => {
                              setShowSaveDialog(false);
                              setSaveConfigName('');
                            }}
                            className="px-4 py-2 bg-gray-200 text-gray-700 rounded-lg hover:bg-gray-300"
                          >
                            Hủy
                          </button>
                        </div>
                      </div>
                    )}
                    
                    <p className="mt-2 text-xs text-yellow-700">
                      💡 <strong>Lưu ý:</strong> Nhập IP:Port hoặc URL đầy đủ. Stream sẽ được proxy qua backend {BACKEND_URL}
                    </p>
                    <p className="mt-1 text-xs text-yellow-600">
                      Ví dụ: <code className="bg-yellow-100 px-1 rounded">192.168.1.100:81</code> hoặc <code className="bg-yellow-100 px-1 rounded">http://192.168.1.100:81</code>
                    </p>
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

          {/* Custom Label */}
          <div className="mb-6">
            <label className="block text-sm font-medium text-gray-700 mb-2">
              3️⃣ Tên hiển thị (tùy chọn)
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
          <div className="mb-6 space-y-4 p-5 bg-gradient-to-br from-blue-50 to-indigo-100 rounded-xl border-2 border-blue-400 shadow-md">
            <div className="flex items-center gap-2 mb-3">
              <span className="text-2xl">�</span>
              <label className="block text-base font-bold text-blue-900">
                4️⃣ Chọn Parking Lot (Tùy chọn - để lưu camera)
              </label>
            </div>
            
            <div className="p-3 bg-blue-50 border-2 border-blue-300 rounded-lg mb-3">
              <p className="text-sm font-semibold text-blue-900">
                💡 <strong>Tùy chọn:</strong> Nếu chọn Parking Lot, camera sẽ tự động được lưu vào Firebase để dùng lại sau!
              </p>
            </div>
            
            <div>
              {/* Parking ID */}
              <div>
                <label className="block text-sm font-bold text-gray-900 mb-2">
                  Parking Lot ID
                </label>
                <select
                  value={parkingId}
                  onChange={(e) => setParkingId(e.target.value)}
                  className={`w-full px-3 py-2.5 border-2 rounded-lg focus:ring-2 focus:ring-blue-500 text-sm font-medium ${
                    parkingId ? 'border-green-400 bg-green-50' : 'border-gray-300 bg-white'
                  }`}
                >
                  <option value="">-- Không chọn (camera không được lưu) --</option>
                  {parkingLots.map((lot) => (
                    <option key={lot.id} value={lot.id}>
                      ✅ {lot.name} ({lot.id})
                    </option>
                  ))}
                </select>
                {!parkingId && (
                  <p className="text-xs text-gray-600 mt-1">
                    ℹ️ Camera ID sẽ tự động tạo từ tên nguồn stream
                  </p>
                )}
                {parkingId && (
                  <p className="text-xs text-green-600 mt-1 font-semibold">
                    ✅ Camera sẽ được lưu vào Parking Lot này!
                  </p>
                )}
                {parkingLots.length === 0 && (
                  <p className="text-xs text-orange-600 mt-1">
                    💡 Chưa có parking lot? <a href="/parking-lots" className="underline font-bold">Tạo ở đây</a>
                  </p>
                )}
              </div>
            </div>

            {/* Status Indicator */}
            {parkingId ? (
              <div className="p-3 bg-green-100 border-2 border-green-500 rounded-lg">
                <p className="text-sm font-bold text-green-900 flex items-center gap-2">
                  <span className="text-xl">✅</span>
                  Camera sẽ được lưu tự động vào <code className="bg-green-200 px-2 py-1 rounded">{parkingId}</code>
                </p>
              </div>
            ) : (
              <div className="p-3 bg-gray-100 border-2 border-gray-300 rounded-lg">
                <p className="text-sm font-bold text-gray-700 flex items-center gap-2">
                  <span className="text-xl">ℹ️</span>
                  Camera sẽ không được lưu (chỉ xem tạm thời)
                </p>
              </div>
            )}

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
          <div className="space-y-3">
            {/* Info if camera will be saved or not */}
            {canAdd && !parkingId && (
              <div className="p-4 bg-blue-100 border-2 border-blue-400 rounded-lg">
                <div className="flex items-start gap-3">
                  <span className="text-2xl">ℹ️</span>
                  <div className="flex-1">
                    <p className="font-bold text-blue-900 mb-1">
                      Camera sẽ được thêm vào grid NHƯNG không được lưu
                    </p>
                    <p className="text-sm text-blue-800">
                      Để lưu camera (xuất hiện trong /stream/host-multi), chọn <strong>Parking Lot</strong> ở trên.
                    </p>
                  </div>
                </div>
              </div>
            )}
            
            <div className="flex justify-end">
              <button
                onClick={handleAddTile}
                disabled={!canAdd}
                className={`px-6 py-3 rounded-lg font-semibold transition-all ${
                  canAdd
                    ? 'bg-gradient-to-r from-strawberry-500 to-matcha-500 text-white hover:shadow-lg'
                    : 'bg-gray-200 text-gray-400 cursor-not-allowed'
                }`}
                title={!canAdd ? 'Vui lòng chọn nguồn stream' : 'Thêm camera vào grid'}
              >
                ➕ Thêm Stream
              </button>
            </div>
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
                {/* Global Detection Toggle */}
                <button
                  onClick={() => {
                    const anyDetectionOn = tiles.some(t => t.showDetection);
                    setTiles(prev => prev.map(tile => ({ ...tile, showDetection: !anyDetectionOn })));
                  }}
                  disabled={tiles.length === 0}
                  className={`px-4 py-3 rounded-lg font-medium transition-all shadow-md ${
                    tiles.length === 0
                      ? 'bg-gray-200 text-gray-400 cursor-not-allowed'
                      : tiles.some(t => t.showDetection)
                      ? 'bg-blue-600 text-white hover:bg-blue-700'
                      : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
                  }`}
                  title={tiles.some(t => t.showDetection) ? 'Tắt detection tất cả' : 'Bật detection tất cả'}
                >
                  {tiles.some(t => t.showDetection) ? (
                    <>
                      <span className="text-lg">🔍</span>
                      <span className="ml-2 text-sm">Detection ON</span>
                    </>
                  ) : (
                    <>
                      <span className="text-lg">📹</span>
                      <span className="ml-2 text-sm">Raw Mode</span>
                    </>
                  )}
                </button>
                
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
                  onToggleDetection={handleToggleDetection}
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
              <p className="mb-2">Sửa IP addresses trong file <code className="bg-white px-2 py-0.5 rounded">MultiStreamViewerPage.tsx</code>:</p>
              <pre className="bg-white p-3 rounded border border-strawberry-200 text-xs overflow-x-auto">
{`const ESP32_CAMERAS = [
  { id: 'esp32_1', name: 'ESP32-CAM 1', ip: 'http://192.168.1.100:81/stream' },
  { id: 'esp32_2', name: 'ESP32-CAM 2', ip: 'http://192.168.1.101:81/stream' },
  { id: 'esp32_3', name: 'ESP32-CAM 3', ip: 'http://192.168.1.102:81/stream' },
];`}
              </pre>
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
            <a
              href="/stream/host-multi"
              className="px-4 py-2 bg-white border-2 border-gray-300 rounded-lg hover:border-blue-500 hover:shadow-md transition flex items-center gap-2 whitespace-nowrap"
            >
              <span className="text-xl">📹</span>
              <div className="text-left">
                <div className="text-xs text-gray-500">Bước 2</div>
                <div className="font-semibold text-sm">Host Camera Streams</div>
              </div>
            </a>
            <div className="px-4 py-2 bg-gradient-to-r from-blue-500 to-green-500 text-white border-2 border-blue-600 rounded-lg shadow-lg flex items-center gap-2 whitespace-nowrap">
              <span className="text-xl">👁️</span>
              <div className="text-left">
                <div className="text-xs opacity-90">Bước 3 (Đang ở đây)</div>
                <div className="font-bold text-sm">Xem Live Streams</div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}


