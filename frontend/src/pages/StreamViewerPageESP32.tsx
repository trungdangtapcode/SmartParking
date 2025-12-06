/**
 * StreamViewerPage cho ESP32-CAM
 * Đơn giản hơn WebRTC - chỉ cần HTTP MJPEG stream
 * Hỗ trợ nhiều chế độ: ESP32, Video File, Mock FFmpeg
 */
import { useState } from 'react';
import { useAuth } from '../context/AuthContext';

// Stream URLs
const ESP32_DIRECT = 'http://192.168.33.122:81/stream'; // Direct từ ESP32
const FASTAPI_PROXY_ESP32 = 'http://localhost:8000/stream'; // FastAPI proxy ESP32
const FASTAPI_PROXY_VIDEO = 'http://localhost:8000/stream?mode=video_file'; // FastAPI video file
const FASTAPI_PROXY_MOCK = 'http://localhost:8000/stream?mode=mock'; // FastAPI mock FFmpeg

type StreamMode = 'esp32' | 'direct' | 'video_file' | 'mock';

export function StreamViewerPageESP32() {
  const { user } = useAuth();
  const [streamMode, setStreamMode] = useState<StreamMode>('esp32');
  const [error, setError] = useState<string | null>(null);

  const getStreamUrl = () => {
    switch (streamMode) {
      case 'esp32':
        return FASTAPI_PROXY_ESP32;
      case 'direct':
        return ESP32_DIRECT;
      case 'video_file':
        return FASTAPI_PROXY_VIDEO;
      case 'mock':
        return FASTAPI_PROXY_MOCK;
      default:
        return FASTAPI_PROXY_ESP32;
    }
  };

  const streamUrl = getStreamUrl();

  const handleImageError = () => {
    setError(`Không thể kết nối đến stream: ${streamUrl}
    
Kiểm tra:
1. ESP32-CAM đã bật và kết nối WiFi
2. Có thể truy cập: ${ESP32_DIRECT} từ browser
3. FastAPI server đang chạy (nếu dùng proxy)`);
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
            Chọn nguồn stream
          </h2>
          
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {/* ESP32 via FastAPI */}
            <button
              onClick={() => setStreamMode('esp32')}
              className={`px-4 py-3 rounded-lg font-medium transition-all ${
                streamMode === 'esp32'
                  ? 'bg-strawberry-500 text-white shadow-lg ring-2 ring-strawberry-300'
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
              }`}
            >
              <div className="text-2xl mb-1">🔄</div>
              <div className="text-sm">ESP32 Proxy</div>
            </button>
            
            {/* Direct ESP32 */}
            <button
              onClick={() => setStreamMode('direct')}
              className={`px-4 py-3 rounded-lg font-medium transition-all ${
                streamMode === 'direct'
                  ? 'bg-matcha-500 text-white shadow-lg ring-2 ring-matcha-300'
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
              }`}
            >
              <div className="text-2xl mb-1">⚡</div>
              <div className="text-sm">Direct ESP32</div>
            </button>
            
            {/* Video File */}
            <button
              onClick={() => setStreamMode('video_file')}
              className={`px-4 py-3 rounded-lg font-medium transition-all ${
                streamMode === 'video_file'
                  ? 'bg-blue-500 text-white shadow-lg ring-2 ring-blue-300'
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
              }`}
            >
              <div className="text-2xl mb-1">📹</div>
              <div className="text-sm">Video File</div>
            </button>
            
            {/* Mock FFmpeg */}
            <button
              onClick={() => setStreamMode('mock')}
              className={`px-4 py-3 rounded-lg font-medium transition-all ${
                streamMode === 'mock'
                  ? 'bg-purple-500 text-white shadow-lg ring-2 ring-purple-300'
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
              }`}
            >
              <div className="text-2xl mb-1">🎬</div>
              <div className="text-sm">Mock FFmpeg</div>
            </button>
          </div>

          <div className="mt-4 p-3 bg-gray-50 rounded-lg">
            <p className="text-sm text-gray-600 mb-2">
              <strong>Chế độ hiện tại:</strong>{' '}
              {streamMode === 'esp32' && '🔄 ESP32-CAM qua FastAPI Proxy (Production)'}
              {streamMode === 'direct' && '⚡ Trực tiếp từ ESP32-CAM'}
              {streamMode === 'video_file' && '📹 Video File (Testing - cần file test_video.mp4)'}
              {streamMode === 'mock' && '🎬 Mock FFmpeg Stream (Testing - cần chạy script)'}
            </p>
            <p className="text-xs text-gray-500 font-mono">
              URL: {streamUrl}
            </p>
          </div>
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
                {streamMode === 'esp32' && '🔄 ESP32 Proxy'}
                {streamMode === 'direct' && '⚡ ESP32 Direct'}
                {streamMode === 'video_file' && '📹 Video File'}
                {streamMode === 'mock' && '🎬 Mock FFmpeg'}
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
                <li>• <strong>ESP32 IP:</strong> 192.168.1.158</li>
                <li>• <strong>Port:</strong> 81</li>
                <li>• <strong>Protocol:</strong> MJPEG over HTTP</li>
                <li>• <strong>FastAPI:</strong> localhost:8000</li>
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
                  href={ESP32_DIRECT}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="block w-full px-4 py-2 bg-matcha-500 text-white rounded-lg hover:bg-matcha-600 transition text-center"
                >
                  🔗 Mở trực tiếp ESP32
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
                <li>Kiểm tra ESP32-CAM đã bật và kết nối WiFi</li>
                <li>Test trực tiếp: <a href={ESP32_DIRECT} target="_blank" rel="noopener noreferrer" className="text-blue-600 underline">{ESP32_DIRECT}</a></li>
                <li>Đảm bảo FastAPI server đang chạy: <code className="bg-gray-200 px-2 py-0.5 rounded">python main_fastapi.py</code></li>
                <li>Kiểm tra network: ESP32 và máy phải cùng mạng WiFi</li>
                <li>Check firewall không block port 81</li>
              </ol>
              
              <p className="mt-4"><strong>Test FastAPI server:</strong></p>
              <ul className="list-disc list-inside ml-2">
                <li>Health check: <a href="http://localhost:8000/health" target="_blank" rel="noopener noreferrer" className="text-blue-600 underline">http://localhost:8000/health</a></li>
                <li>Test ESP32: <a href="http://localhost:8000/test/esp32" target="_blank" rel="noopener noreferrer" className="text-blue-600 underline">http://localhost:8000/test/esp32</a></li>
              </ul>
            </div>
          </details>
        </div>
      </div>
    </div>
  );
}

