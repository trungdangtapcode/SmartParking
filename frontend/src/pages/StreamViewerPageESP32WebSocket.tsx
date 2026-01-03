/**
 * StreamViewerPage for ESP32-CAM using WebSocket
 * ✅ Proper disconnect detection (no zombie streams!)
 * ✅ Clean resource management
 * ✅ Auto-reconnect on connection loss
 * 
 * Replaces HTTP MJPEG with WebSocket streaming
 */
import { useState, useEffect, useRef } from 'react';
import { useAuth } from '../context/AuthContext';
import { WebSocketStreamManager, CanvasStreamRenderer, type StreamStats } from '../utils/websocketStream';

// Get backend URL from environment variable
const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || 'http://localhost:8069';
const WS_BACKEND_URL = BACKEND_URL.replace('http', 'ws');

// WebSocket Stream URLs
const WS_RAW_STREAM = `${WS_BACKEND_URL}/ws/stream/raw`;
const WS_DETECT_STREAM = `${WS_BACKEND_URL}/ws/stream/detect`;

type StreamMode = 'detect' | 'raw';

interface UserESP32Config {
  esp32_url: string;
  label?: string;
  created_at?: string;
  updated_at?: string;
}

export function StreamViewerPageESP32WebSocket() {
  const { user } = useAuth();
  const [streamMode, setStreamMode] = useState<StreamMode>('detect');
  const [error, setError] = useState<string | null>(null);
  const [connectionStatus, setConnectionStatus] = useState<'disconnected' | 'connecting' | 'connected'>('disconnected');
  
  // Detection settings
  const [confThreshold, setConfThreshold] = useState<number>(0.25);
  const [showLabels, setShowLabels] = useState<boolean>(true);
  
  // Performance settings
  const [targetFps, setTargetFps] = useState<number>(10);
  const [skipFrames, setSkipFrames] = useState<number>(2);
  const [performancePreset, setPerformancePreset] = useState<'high' | 'balanced' | 'low'>('balanced');
  
  // Stream stats
  const [stats, setStats] = useState<StreamStats | null>(null);
  const [framesReceived, setFramesReceived] = useState<number>(0);
  
  // User ESP32 Configuration
  const [userConfig, setUserConfig] = useState<UserESP32Config | null>(null);
  const [configLoading, setConfigLoading] = useState<boolean>(false);
  const [showConfigModal, setShowConfigModal] = useState<boolean>(false);
  const [esp32UrlInput, setEsp32UrlInput] = useState<string>('');
  const [labelInput, setLabelInput] = useState<string>('');
  const [saveStatus, setSaveStatus] = useState<'idle' | 'saving' | 'success' | 'error'>('idle');

  // Refs for WebSocket and canvas
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const streamManagerRef = useRef<WebSocketStreamManager | null>(null);
  const rendererRef = useRef<CanvasStreamRenderer | null>(null);

  // Fetch user's ESP32 configuration on mount
  useEffect(() => {
    if (user?.uid) {
      fetchUserConfig();
    }
  }, [user?.uid]);

  // Initialize canvas renderer
  useEffect(() => {
    if (canvasRef.current && !rendererRef.current) {
      rendererRef.current = new CanvasStreamRenderer(canvasRef.current);
    }
  }, []);

  // Connect to WebSocket stream
  useEffect(() => {
    if (!rendererRef.current) return;

    // Disconnect existing stream
    if (streamManagerRef.current) {
      streamManagerRef.current.disconnect();
      streamManagerRef.current = null;
    }

    // Determine WebSocket URL based on mode
    const wsUrl = streamMode === 'detect' ? WS_DETECT_STREAM : WS_RAW_STREAM;

    // Create new stream manager
    const manager = new WebSocketStreamManager({
      url: wsUrl,
      userId: user?.uid,
      conf: confThreshold,
      showLabels: showLabels,
      fps: targetFps,
      skipFrames: skipFrames,
      autoReconnect: true,
    });

    // Set up event handlers
    manager.onConnect(() => {
      console.log('✅ Stream connected');
      setConnectionStatus('connected');
      setError(null);
      setFramesReceived(0);
    });

    manager.onDisconnect(() => {
      console.log('🔴 Stream disconnected');
      setConnectionStatus('disconnected');
    });

    manager.onFrame((base64Data) => {
      // Render frame to canvas
      rendererRef.current?.renderFrame(base64Data);
      setFramesReceived(prev => prev + 1);
    });

    manager.onStats((streamStats) => {
      setStats(streamStats);
    });

    manager.onError((errorMsg) => {
      console.error('❌ Stream error:', errorMsg);
      setError(errorMsg);
      setConnectionStatus('disconnected');
    });

    // Store manager ref
    streamManagerRef.current = manager;

    // Connect to stream
    setConnectionStatus('connecting');
    manager.connect();

    // Cleanup on unmount or mode change
    return () => {
      console.log('🧹 Cleaning up WebSocket stream...');
      manager.disconnect();
      rendererRef.current?.clear();
    };
  }, [streamMode, user?.uid]);

  // Update stream config when settings change
  useEffect(() => {
    if (streamManagerRef.current && connectionStatus === 'connected') {
      streamManagerRef.current.updateConfig({
        conf: confThreshold,
        showLabels: showLabels,
        fps: targetFps,
        skipFrames: skipFrames,
      });
    }
  }, [confThreshold, showLabels, targetFps, skipFrames, connectionStatus]);

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
        setUserConfig(null);
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
        
        // Reconnect with new ESP32 URL
        if (streamManagerRef.current) {
          streamManagerRef.current.updateConfig({ userId: user.uid });
        }
        
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
        
        // Reconnect with default ESP32 URL
        if (streamManagerRef.current) {
          streamManagerRef.current.updateConfig({ userId: undefined });
        }
      } else {
        setError('Failed to delete configuration');
      }
    } catch (err) {
      setError('Error deleting configuration: ' + err);
    }
  };

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
  };

  const handleModeChange = (newMode: StreamMode) => {
    setStreamMode(newMode);
    setStats(null);
    setFramesReceived(0);
  };

  return (
    <div className="min-h-screen bg-gray-50 py-8">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Header */}
        <div className="bg-white rounded-lg shadow-sm p-6 mb-6">
          <div className="flex items-center justify-between mb-4">
            <h1 className="text-2xl font-bold text-gray-900">
              ESP32-CAM Live Stream (WebSocket)
            </h1>
            <div className="flex items-center gap-3">
              <span className={`px-3 py-1 rounded-full text-sm font-medium ${
                connectionStatus === 'connected' ? 'bg-green-100 text-green-800' :
                connectionStatus === 'connecting' ? 'bg-yellow-100 text-yellow-800' :
                'bg-gray-100 text-gray-800'
              }`}>
                {connectionStatus === 'connected' && '🟢 Connected'}
                {connectionStatus === 'connecting' && '🟡 Connecting...'}
                {connectionStatus === 'disconnected' && '🔴 Disconnected'}
              </span>
              <button
                onClick={() => setShowConfigModal(true)}
                className="px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600"
                disabled={!user}
              >
                ⚙️ Configure ESP32
              </button>
            </div>
          </div>

          {/* User Config Status */}
          {user && userConfig && (
            <div className="bg-blue-50 p-3 rounded-lg mb-4">
              <p className="text-sm text-blue-800">
                ✅ Using your custom ESP32: <strong>{userConfig.esp32_url}</strong>
                {userConfig.label && ` (${userConfig.label})`}
              </p>
            </div>
          )}

          {/* Error Display */}
          {error && (
            <div className="bg-red-50 p-3 rounded-lg mb-4">
              <p className="text-sm text-red-800">❌ {error}</p>
            </div>
          )}

          {/* Stream Stats */}
          {(stats || framesReceived > 0) && (
            <div className="bg-green-50 p-3 rounded-lg grid grid-cols-4 gap-4">
              <div>
                <p className="text-xs text-gray-600">Frames Received</p>
                <p className="text-lg font-bold text-green-800">{framesReceived}</p>
              </div>
              {stats && (
                <>
                  <div>
                    <p className="text-xs text-gray-600">Processed</p>
                    <p className="text-lg font-bold text-green-800">{stats.processed}</p>
                  </div>
                  <div>
                    <p className="text-xs text-gray-600">Skipped</p>
                    <p className="text-lg font-bold text-yellow-800">{stats.skipped}</p>
                  </div>
                  <div>
                    <p className="text-xs text-gray-600">Total</p>
                    <p className="text-lg font-bold text-blue-800">{stats.total}</p>
                  </div>
                </>
              )}
            </div>
          )}
        </div>

        {/* Controls */}
        <div className="bg-white rounded-lg shadow-sm p-6 mb-6">
          <h2 className="text-lg font-semibold mb-4">Stream Controls</h2>
          
          {/* Mode Selection */}
          <div className="mb-4">
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Stream Mode
            </label>
            <div className="flex gap-2">
              <button
                onClick={() => handleModeChange('detect')}
                className={`px-4 py-2 rounded-lg font-medium ${
                  streamMode === 'detect'
                    ? 'bg-blue-500 text-white'
                    : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                }`}
              >
                🤖 Detection
              </button>
              <button
                onClick={() => handleModeChange('raw')}
                className={`px-4 py-2 rounded-lg font-medium ${
                  streamMode === 'raw'
                    ? 'bg-blue-500 text-white'
                    : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                }`}
              >
                📹 Raw Stream
              </button>
            </div>
          </div>

          {/* Performance Presets */}
          <div className="mb-4">
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Performance Preset
            </label>
            <div className="flex gap-2">
              {(['high', 'balanced', 'low'] as const).map((preset) => (
                <button
                  key={preset}
                  onClick={() => applyPerformancePreset(preset)}
                  className={`px-4 py-2 rounded-lg font-medium capitalize ${
                    performancePreset === preset
                      ? 'bg-green-500 text-white'
                      : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                  }`}
                >
                  {preset}
                </button>
              ))}
            </div>
          </div>

          {/* Detection Settings (only for detect mode) */}
          {streamMode === 'detect' && (
            <>
              <div className="mb-4">
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Confidence Threshold: {confThreshold.toFixed(2)}
                </label>
                <input
                  type="range"
                  min="0.1"
                  max="0.9"
                  step="0.05"
                  value={confThreshold}
                  onChange={(e) => setConfThreshold(parseFloat(e.target.value))}
                  className="w-full"
                />
              </div>

              <div className="mb-4">
                <label className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={showLabels}
                    onChange={(e) => setShowLabels(e.target.checked)}
                    className="w-4 h-4"
                  />
                  <span className="text-sm font-medium text-gray-700">Show Labels</span>
                </label>
              </div>

              <div className="grid grid-cols-2 gap-4 mb-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Target FPS: {targetFps}
                  </label>
                  <input
                    type="range"
                    min="1"
                    max="30"
                    value={targetFps}
                    onChange={(e) => setTargetFps(parseInt(e.target.value))}
                    className="w-full"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Skip Frames: {skipFrames}
                  </label>
                  <input
                    type="range"
                    min="1"
                    max="10"
                    value={skipFrames}
                    onChange={(e) => setSkipFrames(parseInt(e.target.value))}
                    className="w-full"
                  />
                </div>
              </div>
            </>
          )}
        </div>

        {/* Stream Display */}
        <div className="bg-white rounded-lg shadow-sm p-6">
          <h2 className="text-lg font-semibold mb-4">Live Stream</h2>
          <div className="bg-black rounded-lg overflow-hidden flex items-center justify-center" style={{ minHeight: '400px' }}>
            <canvas
              ref={canvasRef}
              className="max-w-full h-auto"
              style={{ maxHeight: '600px' }}
            />
          </div>
        </div>

        {/* Configuration Modal */}
        {showConfigModal && (
          <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
            <div className="bg-white rounded-lg p-6 max-w-md w-full mx-4">
              <h2 className="text-xl font-bold mb-4">Configure Your ESP32-CAM</h2>
              
              <div className="mb-4">
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  ESP32 URL *
                </label>
                <input
                  type="text"
                  value={esp32UrlInput}
                  onChange={(e) => setEsp32UrlInput(e.target.value)}
                  placeholder="http://192.168.1.100:81"
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                />
              </div>

              <div className="mb-4">
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Label (optional)
                </label>
                <input
                  type="text"
                  value={labelInput}
                  onChange={(e) => setLabelInput(e.target.value)}
                  placeholder="My ESP32 Camera"
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                />
              </div>

              <div className="flex gap-2">
                <button
                  onClick={saveUserConfig}
                  disabled={!esp32UrlInput || saveStatus === 'saving'}
                  className="flex-1 px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 disabled:bg-gray-300"
                >
                  {saveStatus === 'saving' && '⏳ Saving...'}
                  {saveStatus === 'success' && '✅ Saved!'}
                  {saveStatus === 'idle' && '💾 Save'}
                  {saveStatus === 'error' && '❌ Error'}
                </button>
                
                {userConfig && (
                  <button
                    onClick={deleteUserConfig}
                    className="px-4 py-2 bg-red-500 text-white rounded-lg hover:bg-red-600"
                  >
                    🗑️ Delete
                  </button>
                )}

                <button
                  onClick={() => setShowConfigModal(false)}
                  className="px-4 py-2 bg-gray-200 text-gray-700 rounded-lg hover:bg-gray-300"
                >
                  Cancel
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
