/**
 * StreamViewerPage cho ESP32-CAM
 * Simple HTTP MJPEG stream viewer
 * All streams go through backend - frontend never talks to ESP32 directly
 */
import { useState } from 'react';
import { useAuth } from '../context/AuthContext';

// Get backend URL from environment variable
const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || 'http://localhost:8069';

// Stream URLs - All through backend
const FASTAPI_PROXY_ESP32 = `${BACKEND_URL}/stream`; // Raw stream proxy
const FASTAPI_DETECT_STREAM = `${BACKEND_URL}/stream/detect`; // With object detection

type StreamMode = 'detect' | 'raw' | 'snapshot';

export function StreamViewerPageESP32() {
  const { user } = useAuth();
  const [streamMode, setStreamMode] = useState<StreamMode>('detect');
  const [error, setError] = useState<string | null>(null);
  const [confThreshold, setConfThreshold] = useState<number>(0.25);
  const [showLabels, setShowLabels] = useState<boolean>(true);

  const getStreamUrl = () => {
    switch (streamMode) {
      case 'detect':
        return `${FASTAPI_DETECT_STREAM}?conf=${confThreshold}&show_labels=${showLabels}`;
      case 'raw':
        return FASTAPI_PROXY_ESP32;
      case 'snapshot':
        return FASTAPI_PROXY_ESP32; // Use raw stream for snapshot mode
      default:
        return FASTAPI_DETECT_STREAM;
    }
  };

  const streamUrl = getStreamUrl();

  const handleImageError = () => {
    setError(`Không thể kết nối đến stream: ${streamUrl}
    
Kiểm tra:
1. Backend server đang chạy: ${BACKEND_URL}
2. ESP32 server đã kết nối với backend
3. Network connection is stable`);
  };

  const handleImageLoad = () => {
    setError(null);
  };

  return (
    <div className="min-h-screen bg-gradient-to-b from-strawberry-50 via-white to-matcha-50 p-6">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="mb-6">
          <h1 className="text-3xl font-bold text-strawberry-900 mb-2">
            📹 ESP32-CAM Live Stream
          </h1>
          <p className="text-gray-600">
            Xem trực tiếp từ camera ESP32
          </p>
        </div>

        {/* Stream Source Selection */}
        <div className="bg-white rounded-xl shadow-lg p-6 mb-6">
          <h2 className="text-xl font-semibold mb-4 text-strawberry-800">
            Chọn chế độ xem
          </h2>
          
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            {/* Object Detection Stream */}
            <button
              onClick={() => setStreamMode('detect')}
              className={`px-4 py-3 rounded-lg font-medium transition-all ${
                streamMode === 'detect'
                  ? 'bg-strawberry-500 text-white shadow-lg ring-2 ring-strawberry-300'
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
              }`}
            >
              <div className="text-2xl mb-1">🎯</div>
              <div className="text-sm">Object Detection</div>
            </button>
            
            {/* Raw Stream */}
            <button
              onClick={() => setStreamMode('raw')}
              className={`px-4 py-3 rounded-lg font-medium transition-all ${
                streamMode === 'raw'
                  ? 'bg-blue-500 text-white shadow-lg ring-2 ring-blue-300'
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
              }`}
            >
              <div className="text-2xl mb-1">📹</div>
              <div className="text-sm">Raw Stream</div>
            </button>
            
            {/* Snapshot Mode */}
            <button
              onClick={() => setStreamMode('snapshot')}
              className={`px-4 py-3 rounded-lg font-medium transition-all ${
                streamMode === 'snapshot'
                  ? 'bg-matcha-500 text-white shadow-lg ring-2 ring-matcha-300'
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
              }`}
            >
              <div className="text-2xl mb-1">📸</div>
              <div className="text-sm">Snapshot Mode</div>
            </button>
          </div>

          <div className="mt-4 p-3 bg-gray-50 rounded-lg">
            <p className="text-sm text-gray-600 mb-2">
              <strong>Chế độ hiện tại:</strong>{' '}
              {streamMode === 'detect' && '🎯 Object Detection + Tracking (YOLO)'}
              {streamMode === 'raw' && '📹 Raw Stream (via backend proxy)'}
              {streamMode === 'snapshot' && '📸 Snapshot Mode (capture frames)'}
            </p>
            <p className="text-xs text-gray-500 font-mono">
              URL: {streamUrl}
            </p>
            <p className="text-xs text-gray-500 mt-1">
              ℹ️ All streams go through backend (port {BACKEND_URL})
            </p>
          </div>

          {/* Detection Settings (show only when detect mode) */}
          {streamMode === 'detect' && (
            <div className="mt-4 p-4 bg-blue-50 rounded-lg border border-blue-200">
              <h3 className="font-semibold text-blue-800 mb-3">⚙️ Detection Settings</h3>
              
              <div className="space-y-3">
                {/* Confidence Threshold */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Confidence Threshold: {confThreshold.toFixed(2)}
                  </label>
                  <input
                    type="range"
                    min="0.1"
                    max="0.9"
                    step="0.05"
                    value={confThreshold}
                    onChange={(e) => setConfThreshold(parseFloat(e.target.value))}
                    className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer"
                  />
                  <div className="flex justify-between text-xs text-gray-500 mt-1">
                    <span>More detections (0.1)</span>
                    <span>More accurate (0.9)</span>
                  </div>
                </div>

                {/* Show Labels Toggle */}
                <div className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    id="showLabels"
                    checked={showLabels}
                    onChange={(e) => setShowLabels(e.target.checked)}
                    className="w-4 h-4 text-strawberry-500 rounded"
                  />
                  <label htmlFor="showLabels" className="text-sm font-medium text-gray-700">
                    Show detection labels
                  </label>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Stream Display */}
        <div className="bg-white rounded-xl shadow-lg p-6">
          <div className="aspect-video bg-black rounded-lg overflow-hidden relative">
            {/* MJPEG Stream */}
            <img
              src={streamUrl}
              alt="ESP32-CAM Stream"
              className="w-full h-full object-contain"
              onError={handleImageError}
              onLoad={handleImageLoad}
            />

            {/* Overlay: Status */}
            <div className="absolute top-4 left-4 bg-black/70 text-white px-4 py-2 rounded-lg backdrop-blur-sm">
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 bg-green-500 rounded-full animate-pulse"></div>
                <span className="font-medium">LIVE</span>
              </div>
            </div>

            {/* Overlay: Stream Info */}
            <div className="absolute top-4 right-4 bg-black/70 text-white px-4 py-2 rounded-lg backdrop-blur-sm">
              <p className="text-sm">
                {streamMode === 'detect' && '🎯 YOLO Detection'}
                {streamMode === 'raw' && '📹 Raw Stream'}
                {streamMode === 'snapshot' && '📸 Snapshot'}
              </p>
            </div>
          </div>

          {/* Error Message */}
          {error && (
            <div className="mt-4 bg-red-50 border border-red-200 rounded-lg p-4">
              <div className="flex items-start gap-3">
                <span className="text-2xl">❌</span>
                <div>
                  <h3 className="font-semibold text-red-800 mb-1">Lỗi kết nối</h3>
                  <pre className="text-sm text-red-700 whitespace-pre-wrap">{error}</pre>
                </div>
              </div>
            </div>
          )}

          {/* Info Cards */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-6">
            {/* Connection Info */}
            <div className="bg-gray-50 rounded-lg p-4">
              <h3 className="font-semibold text-gray-800 mb-2">📡 Thông tin kết nối</h3>
              <ul className="text-sm text-gray-600 space-y-1">
                <li>• <strong>Backend API:</strong> {BACKEND_URL}</li>
                <li>• <strong>Protocol:</strong> MJPEG over HTTP</li>
                <li>• <strong>Detection:</strong> YOLOv8 (real-time)</li>
                <li className="text-xs text-gray-500 mt-2">
                  ℹ️ Frontend → Backend → ESP32 (indirect connection)
                </li>
              </ul>
            </div>

            {/* Controls */}
            <div className="bg-gray-50 rounded-lg p-4">
              <h3 className="font-semibold text-gray-800 mb-2">🎛️ Điều khiển</h3>
              <div className="space-y-2">
                <button
                  onClick={() => window.location.reload()}
                  className="w-full px-4 py-2 bg-strawberry-500 text-white rounded-lg hover:bg-strawberry-600 transition"
                >
                  🔄 Reload Stream
                </button>
                <a
                  href={`${BACKEND_URL}/docs`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="block w-full px-4 py-2 bg-matcha-500 text-white rounded-lg hover:bg-matcha-600 transition text-center"
                >
                  � API Documentation
                </a>
              </div>
            </div>
          </div>

          {/* Troubleshooting */}
          <details className="mt-6">
            <summary className="cursor-pointer font-semibold text-gray-800 hover:text-strawberry-600">
              🔧 Troubleshooting
            </summary>
            <div className="mt-4 bg-gray-50 rounded-lg p-4 text-sm text-gray-700 space-y-2">
              <p><strong>Nếu không thấy stream:</strong></p>
              <ol className="list-decimal list-inside space-y-1 ml-2">
                <li>Đảm bảo backend đang chạy: <code className="bg-gray-200 px-2 py-0.5 rounded">cd server && python main_fastapi.py</code></li>
                <li>Kiểm tra ESP32-CAM đang streaming: <code className="bg-gray-200 px-2 py-0.5 rounded">cd ESP32 && python start_mock.py --port 5069</code></li>
                <li>Test backend health: <a href={`${BACKEND_URL}/health`} target="_blank" rel="noopener noreferrer" className="text-blue-600 underline">{BACKEND_URL}/health</a></li>
                <li>Test backend stream: <code className="bg-gray-200 px-2 py-0.5 rounded">curl {BACKEND_URL}/stream | head -c 1000</code></li>
              </ol>
              
              <p className="mt-4"><strong>Để bật Object Detection:</strong></p>
              <ul className="list-disc list-inside ml-2">
                <li>Chọn chế độ "Object Detection" ở trên</li>
                <li>Điều chỉnh Confidence Threshold để thay đổi độ nhạy</li>
                <li>Stream sẽ hiển thị bounding boxes và labels cho các objects được phát hiện</li>
              </ul>
            </div>
          </details>
        </div>
      </div>
    </div>
  );
}

