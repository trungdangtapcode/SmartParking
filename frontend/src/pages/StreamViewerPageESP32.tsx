/**
 * StreamViewerPage cho ESP32-CAM
 * Simple HTTP MJPEG stream viewer
 * All streams go through backend - frontend never talks to ESP32 directly
 * Supports per-user ESP32 configuration saved in Firebase
 */
import { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';

// Get backend URL from environment variable
const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || 'http://localhost:8069';

// Stream URLs - All through backend
const FASTAPI_PROXY_ESP32 = `${BACKEND_URL}/stream`; // Raw stream proxy
const FASTAPI_DETECT_STREAM = `${BACKEND_URL}/stream/detect`; // With object detection

type StreamMode = 'detect' | 'raw' | 'snapshot';

interface UserESP32Config {
  esp32_url: string;
  label?: string;
  created_at?: string;
  updated_at?: string;
}

export function StreamViewerPageESP32() {
  const { user } = useAuth();
  const [streamMode, setStreamMode] = useState<StreamMode>('detect');
  const [error, setError] = useState<string | null>(null);
  const [confThreshold, setConfThreshold] = useState<number>(0.25);
  const [showLabels, setShowLabels] = useState<boolean>(true);
  const [streamKey, setStreamKey] = useState<number>(0); // Force reload stream when changed
  
  // Performance settings
  const [targetFps, setTargetFps] = useState<number>(10);
  const [skipFrames, setSkipFrames] = useState<number>(2);
  const [performancePreset, setPerformancePreset] = useState<'high' | 'balanced' | 'low'>('balanced');
  
  // User ESP32 Configuration
  const [userConfig, setUserConfig] = useState<UserESP32Config | null>(null);
  const [configLoading, setConfigLoading] = useState<boolean>(false);
  const [showConfigModal, setShowConfigModal] = useState<boolean>(false);
  const [esp32UrlInput, setEsp32UrlInput] = useState<string>('');
  const [labelInput, setLabelInput] = useState<string>('');
  const [saveStatus, setSaveStatus] = useState<'idle' | 'saving' | 'success' | 'error'>('idle');

  // Fetch user's ESP32 configuration on mount
  useEffect(() => {
    if (user?.uid) {
      fetchUserConfig();
    }
  }, [user?.uid]);

  // Cleanup: Force reload stream URL when component unmounts or tab closes
  useEffect(() => {
    const handleBeforeUnload = () => {
      // Increment streamKey to force new connection on return
      setStreamKey(prev => prev + 1);
    };

    window.addEventListener('beforeunload', handleBeforeUnload);
    
    return () => {
      window.removeEventListener('beforeunload', handleBeforeUnload);
      // Cleanup on unmount: change key to abort connection
      setStreamKey(prev => prev + 1);
    };
  }, []);

  const fetchUserConfig = async () => {
    if (!user?.uid) return;
    
    setConfigLoading(true);
    try {
      const response = await fetch(`${BACKEND_URL}/api/user/esp32-config`, {
        headers: {
          'X-User-ID': user.uid
        }
      });
      
      if (response.ok) {
        const data = await response.json();
        setUserConfig(data);
        setEsp32UrlInput(data.esp32_url || '');
        setLabelInput(data.label || '');
      } else if (response.status === 404) {
        // User has no config yet
        setUserConfig(null);
      } else {
        console.error('Failed to fetch user config:', response.statusText);
      }
    } catch (err) {
      console.error('Error fetching user config:', err);
    } finally {
      setConfigLoading(false);
    }
  };

  const saveUserConfig = async () => {
    if (!user?.uid || !esp32UrlInput) return;
    
    setSaveStatus('saving');
    try {
      const response = await fetch(`${BACKEND_URL}/api/user/esp32-config`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-User-ID': user.uid
        },
        body: JSON.stringify({
          esp32_url: esp32UrlInput,
          label: labelInput || undefined
        })
      });
      
      if (response.ok) {
        const data = await response.json();
        setUserConfig(data);
        setSaveStatus('success');
        setTimeout(() => {
          setSaveStatus('idle');
          setShowConfigModal(false);
        }, 1500);
      } else {
        setSaveStatus('error');
        const errorData = await response.json();
        setError(errorData.detail || 'Failed to save configuration');
      }
    } catch (err) {
      setSaveStatus('error');
      setError('Error saving configuration: ' + err);
    }
  };

  const deleteUserConfig = async () => {
    if (!user?.uid) return;
    
    try {
      const response = await fetch(`${BACKEND_URL}/api/user/esp32-config`, {
        method: 'DELETE',
        headers: {
          'X-User-ID': user.uid
        }
      });
      
      if (response.ok) {
        setUserConfig(null);
        setEsp32UrlInput('');
        setLabelInput('');
        setShowConfigModal(false);
      } else {
        setError('Failed to delete configuration');
      }
    } catch (err) {
      setError('Error deleting configuration: ' + err);
    }
  };

  const getStreamUrl = () => {
    switch (streamMode) {
      case 'detect':
        return `${FASTAPI_DETECT_STREAM}?conf=${confThreshold}&show_labels=${showLabels}&fps=${targetFps}&skip_frames=${skipFrames}&t=${streamKey}`;
      case 'raw':
        return `${FASTAPI_PROXY_ESP32}?t=${streamKey}`;
      case 'snapshot':
        return `${FASTAPI_PROXY_ESP32}?t=${streamKey}`; // Use raw stream for snapshot mode
      default:
        return `${FASTAPI_DETECT_STREAM}?t=${streamKey}`;
    }
  };

  const streamUrl = getStreamUrl();

  // Apply performance preset
  const applyPerformancePreset = (preset: 'high' | 'balanced' | 'low') => {
    setPerformancePreset(preset);
    switch (preset) {
      case 'high':
        setTargetFps(15);
        setSkipFrames(1);
        setConfThreshold(0.25);
        break;
      case 'balanced':
        setTargetFps(10);
        setSkipFrames(2);
        setConfThreshold(0.35);
        break;
      case 'low':
        setTargetFps(5);
        setSkipFrames(5);
        setConfThreshold(0.5);
        break;
    }
    setStreamKey(prev => prev + 1); // Force reload with new settings
  };

  // Force stream reload when mode changes
  const handleModeChange = (newMode: StreamMode) => {
    setStreamMode(newMode);
    setStreamKey(prev => prev + 1); // Change key to force img reload
    setError(null);
  };

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

        {/* User ESP32 Configuration */}
        {user && (
          <div className="bg-white rounded-xl shadow-lg p-6 mb-6">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h2 className="text-xl font-semibold text-strawberry-800">
                  🎥 Your ESP32-CAM Configuration
                </h2>
                <p className="text-sm text-gray-600 mt-1">
                  {userConfig ? (
                    <>Using your configured ESP32: <code className="bg-gray-100 px-2 py-0.5 rounded text-xs">{userConfig.esp32_url}</code></>
                  ) : (
                    'Using default ESP32 (not configured yet)'
                  )}
                </p>
              </div>
              <button
                onClick={() => setShowConfigModal(true)}
                className="px-4 py-2 bg-strawberry-500 hover:bg-strawberry-600 text-white rounded-lg transition-all shadow-md hover:shadow-lg font-medium"
              >
                ⚙️ Configure
              </button>
            </div>
            
            {userConfig && (
              <div className="bg-green-50 border border-green-200 rounded-lg p-3">
                <div className="flex items-start gap-2">
                  <span className="text-green-600">✓</span>
                  <div className="flex-1">
                    <p className="text-sm text-green-800 font-medium">
                      {userConfig.label || 'Your ESP32-CAM'}
                    </p>
                    <p className="text-xs text-green-600 mt-1">
                      Configured on {new Date(userConfig.created_at || '').toLocaleString()}
                    </p>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        {/* ESP32 Configuration Modal */}
        {showConfigModal && (
          <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
            <div className="bg-white rounded-xl shadow-2xl max-w-lg w-full p-6">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-xl font-bold text-gray-800">Configure Your ESP32-CAM</h3>
                <button
                  onClick={() => setShowConfigModal(false)}
                  className="text-gray-500 hover:text-gray-700 text-2xl"
                >
                  ×
                </button>
              </div>
              
              <div className="space-y-4">
                {/* ESP32 URL Input */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    ESP32-CAM URL *
                  </label>
                  <input
                    type="text"
                    value={esp32UrlInput}
                    onChange={(e) => setEsp32UrlInput(e.target.value)}
                    placeholder="http://192.168.1.100:81 or http://localhost:5069"
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-strawberry-500 focus:border-transparent"
                  />
                  <p className="text-xs text-gray-500 mt-1">
                    Enter your ESP32-CAM IP address with port (e.g., http://192.168.1.100:81)
                  </p>
                </div>

                {/* Label Input */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Label (optional)
                  </label>
                  <input
                    type="text"
                    value={labelInput}
                    onChange={(e) => setLabelInput(e.target.value)}
                    placeholder="My Garage Camera"
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-strawberry-500 focus:border-transparent"
                  />
                  <p className="text-xs text-gray-500 mt-1">
                    Give your camera a friendly name
                  </p>
                </div>

                {/* Buttons */}
                <div className="flex gap-3 pt-4">
                  <button
                    onClick={saveUserConfig}
                    disabled={!esp32UrlInput || saveStatus === 'saving'}
                    className="flex-1 px-4 py-2 bg-green-500 hover:bg-green-600 text-white rounded-lg transition-all disabled:opacity-50 disabled:cursor-not-allowed font-medium"
                  >
                    {saveStatus === 'saving' && '⏳ Saving...'}
                    {saveStatus === 'success' && '✓ Saved!'}
                    {saveStatus === 'idle' && '💾 Save Configuration'}
                    {saveStatus === 'error' && '❌ Error - Try Again'}
                  </button>
                  
                  {userConfig && (
                    <button
                      onClick={deleteUserConfig}
                      className="px-4 py-2 bg-red-500 hover:bg-red-600 text-white rounded-lg transition-all font-medium"
                    >
                      🗑️ Delete
                    </button>
                  )}
                  
                  <button
                    onClick={() => setShowConfigModal(false)}
                    className="px-4 py-2 bg-gray-300 hover:bg-gray-400 text-gray-800 rounded-lg transition-all font-medium"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Stream Source Selection */}
        <div className="bg-white rounded-xl shadow-lg p-6 mb-6">
          <h2 className="text-xl font-semibold mb-4 text-strawberry-800">
            Chọn chế độ xem
          </h2>
          
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            {/* Object Detection Stream */}
            <button
              onClick={() => handleModeChange('detect')}
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
              onClick={() => handleModeChange('raw')}
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
              onClick={() => handleModeChange('snapshot')}
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
              
              <div className="space-y-4">
                {/* Performance Presets */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Performance Preset
                  </label>
                  <div className="grid grid-cols-3 gap-2">
                    <button
                      onClick={() => applyPerformancePreset('high')}
                      className={`px-3 py-2 rounded-lg text-sm font-medium transition-all ${
                        performancePreset === 'high'
                          ? 'bg-green-500 text-white shadow-md'
                          : 'bg-white text-gray-700 border border-gray-300 hover:bg-gray-50'
                      }`}
                    >
                      🚀 High Quality
                      <div className="text-xs opacity-80">15 FPS, All frames</div>
                    </button>
                    <button
                      onClick={() => applyPerformancePreset('balanced')}
                      className={`px-3 py-2 rounded-lg text-sm font-medium transition-all ${
                        performancePreset === 'balanced'
                          ? 'bg-blue-500 text-white shadow-md'
                          : 'bg-white text-gray-700 border border-gray-300 hover:bg-gray-50'
                      }`}
                    >
                      ⚖️ Balanced
                      <div className="text-xs opacity-80">10 FPS, Every 2nd</div>
                    </button>
                    <button
                      onClick={() => applyPerformancePreset('low')}
                      className={`px-3 py-2 rounded-lg text-sm font-medium transition-all ${
                        performancePreset === 'low'
                          ? 'bg-orange-500 text-white shadow-md'
                          : 'bg-white text-gray-700 border border-gray-300 hover:bg-gray-50'
                      }`}
                    >
                      ⚡ Fast/Low CPU
                      <div className="text-xs opacity-80">5 FPS, Every 5th</div>
                    </button>
                  </div>
                  <p className="text-xs text-gray-500 mt-2">
                    💡 Choose "Fast/Low CPU" if system is laggy
                  </p>
                </div>

                {/* Advanced Settings */}
                <details className="mt-3">
                  <summary className="cursor-pointer text-sm font-medium text-gray-700 hover:text-blue-600">
                    Advanced Settings
                  </summary>
                  <div className="mt-3 space-y-3">
                    {/* Target FPS */}
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">
                        Target FPS: {targetFps}
                      </label>
                      <input
                        type="range"
                        min="1"
                        max="30"
                        step="1"
                        value={targetFps}
                        onChange={(e) => {
                          setTargetFps(parseInt(e.target.value));
                          setStreamKey(prev => prev + 1);
                        }}
                        className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer"
                      />
                      <div className="flex justify-between text-xs text-gray-500 mt-1">
                        <span>Slower (1 FPS)</span>
                        <span>Faster (30 FPS)</span>
                      </div>
                    </div>

                    {/* Skip Frames */}
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">
                        Process Every: {skipFrames === 1 ? 'All frames' : `Every ${skipFrames} frames`}
                      </label>
                      <input
                        type="range"
                        min="1"
                        max="10"
                        step="1"
                        value={skipFrames}
                        onChange={(e) => {
                          setSkipFrames(parseInt(e.target.value));
                          setStreamKey(prev => prev + 1);
                        }}
                        className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer"
                      />
                      <div className="flex justify-between text-xs text-gray-500 mt-1">
                        <span>All frames (slowest)</span>
                        <span>Every 10th (fastest)</span>
                      </div>
                    </div>
                  </div>
                </details>

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
              key={streamKey} // Force remount when key changes
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

          {/* Connection Info & Controls */}
          <div className="mt-6 space-y-4">
            {/* Connection Info */}
            <div className="bg-gradient-to-r from-gray-50 to-blue-50 rounded-xl p-6 border border-gray-200">
              <div className="flex items-start gap-4">
                <div className="text-4xl">📡</div>
                <div className="flex-1">
                  <h3 className="font-semibold text-gray-800 mb-3 text-lg">Thông tin kết nối</h3>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <span className="text-xs font-medium text-gray-500">Backend API</span>
                      <p className="text-sm font-mono bg-white px-3 py-2 rounded border border-gray-200">{BACKEND_URL}</p>
                    </div>
                    <div className="space-y-2">
                      <span className="text-xs font-medium text-gray-500">Protocol</span>
                      <p className="text-sm font-mono bg-white px-3 py-2 rounded border border-gray-200">MJPEG over HTTP</p>
                    </div>
                    <div className="space-y-2">
                      <span className="text-xs font-medium text-gray-500">Detection Engine</span>
                      <p className="text-sm font-mono bg-white px-3 py-2 rounded border border-gray-200">YOLOv8 (real-time)</p>
                    </div>
                    <div className="space-y-2">
                      <span className="text-xs font-medium text-gray-500">Architecture</span>
                      <p className="text-sm font-mono bg-white px-3 py-2 rounded border border-gray-200">Frontend → Backend → ESP32</p>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            {/* Controls */}
            <div className="bg-white rounded-xl p-4 border border-gray-200 shadow-sm">
              <div className="flex flex-wrap gap-3">
                <button
                  onClick={() => window.location.reload()}
                  className="px-6 py-3 bg-red-500 hover:bg-red-600 text-white rounded-lg transition-all shadow-md hover:shadow-lg font-medium"
                >
                  🔄 Reload Stream
                </button>
                <a
                  href={`${BACKEND_URL}/docs`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-block px-6 py-3 bg-green-500 hover:bg-green-600 text-white rounded-lg transition-all shadow-md hover:shadow-lg font-medium"
                >
                  📖 API Documentation
                </a>
                <a
                  href={`${BACKEND_URL}/health`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-block px-6 py-3 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-all shadow-md hover:shadow-lg font-medium"
                >
                  💚 Health Check
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

