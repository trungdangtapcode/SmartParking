import { useState, useEffect, useRef } from 'react';
import { useAuth } from '../context/AuthContext';
import { getUserESP32Configs, toggleWorkerForCamera } from '../services/esp32ConfigService';
import { getParkingLotsByOwner } from '../services/parkingLotService';

interface ESP32Config {
  id: string;
  name: string;
  ipAddress: string;
  workerEnabled?: boolean;
  isDefault?: boolean;
}

interface WorkerLog {
  timestamp: string;
  level: 'INFO' | 'DEBUG' | 'WARNING' | 'ERROR';
  cameraId: string;
  cameraName: string;
  message: string;
}

interface WorkerStatus {
  cameraId: string;
  cameraName: string;
  enabled: boolean;
  status: 'running' | 'idle' | 'error' | 'unknown';
  lastCheck?: string;
  spacesCount?: number;
  occupiedCount?: number;
  errorMessage?: string;
}

export function WorkerMonitorPage() {
  const { user, role } = useAuth();
  const isAdmin = role === 'admin';
  
  // Data states
  const [cameras, setCameras] = useState<ESP32Config[]>([]);
  const [workerStatuses, setWorkerStatuses] = useState<WorkerStatus[]>([]);
  const [logs, setLogs] = useState<WorkerLog[]>([]);
  
  // UI states
  const [isLoading, setIsLoading] = useState(true);
  const [selectedCamera, setSelectedCamera] = useState<string | null>(null);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [refreshInterval, setRefreshInterval] = useState(5); // seconds
  const [logLevel, setLogLevel] = useState<'ALL' | 'INFO' | 'WARNING' | 'ERROR'>('ALL');
  
  // Live detection stream states
  const [showDetectionStream, setShowDetectionStream] = useState(false);
  const [streamingCameraId, setStreamingCameraId] = useState<string | null>(null);
  const [streamUrl, setStreamUrl] = useState<string>('');
  
  // Refs
  const logsEndRef = useRef<HTMLDivElement>(null);
  const refreshTimerRef = useRef<number | null>(null);

  // Load initial data
  useEffect(() => {
    if (!user || !isAdmin) return;

    const loadData = async () => {
      setIsLoading(true);
      try {
        const [camsData] = await Promise.all([
          getUserESP32Configs(user.uid),
          getParkingLotsByOwner(user.uid),
        ]);

        setCameras(camsData);
        
        // Initialize worker statuses
        const statuses: WorkerStatus[] = camsData.map(cam => ({
          cameraId: cam.id,
          cameraName: cam.name,
          enabled: cam.workerEnabled ?? false,
          status: 'unknown',
        }));
        setWorkerStatuses(statuses);
        
        // Generate mock logs for demo (in production, fetch from backend)
        generateMockLogs(camsData);
      } catch (error) {
        console.error('Failed to load data:', error);
      } finally {
        setIsLoading(false);
      }
    };

    loadData();
  }, [user, isAdmin]);

  // Auto-refresh
  useEffect(() => {
    if (!autoRefresh) {
      if (refreshTimerRef.current) {
        clearInterval(refreshTimerRef.current);
        refreshTimerRef.current = null;
      }
      return;
    }

    refreshTimerRef.current = setInterval(() => {
      refreshWorkerStatus();
      addNewLogs();
    }, refreshInterval * 1000);

    return () => {
      if (refreshTimerRef.current) {
        clearInterval(refreshTimerRef.current);
      }
    };
  }, [autoRefresh, refreshInterval]);

  // Scroll to bottom when new logs arrive
  useEffect(() => {
    if (logsEndRef.current) {
      logsEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [logs]);

  // Handle ESC key to close stream modal
  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && showDetectionStream) {
        handleCloseDetectionStream();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => {
      window.removeEventListener('keydown', handleKeyDown);
    };
  }, [showDetectionStream]);

  // Generate mock logs (replace with real backend API)
  const generateMockLogs = (camsData: ESP32Config[]) => {
    const mockLogs: WorkerLog[] = [];
    const now = new Date();
    
    camsData.forEach((cam) => {
      if (cam.workerEnabled) {
        // Add some historical logs
        for (let i = 5; i >= 0; i--) {
          const timestamp = new Date(now.getTime() - i * 5000);
          mockLogs.push({
            timestamp: timestamp.toISOString(),
            level: 'INFO',
            cameraId: cam.id,
            cameraName: cam.name,
            message: `✅ Processing camera: ${cam.ipAddress}`,
          });
          
          if (i % 2 === 0) {
            mockLogs.push({
              timestamp: new Date(timestamp.getTime() + 1000).toISOString(),
              level: 'DEBUG',
              cameraId: cam.id,
              cameraName: cam.name,
              message: `Fetched frame: 640x480, 48531 bytes`,
            });
          }
          
          mockLogs.push({
            timestamp: new Date(timestamp.getTime() + 2000).toISOString(),
            level: 'INFO',
            cameraId: cam.id,
            cameraName: cam.name,
            message: `Detected ${Math.floor(Math.random() * 3)} vehicles, updated ${Math.floor(Math.random() * 5)} spaces`,
          });
        }
      }
    });
    
    setLogs(mockLogs.sort((a, b) => 
      new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()
    ));
  };

  // Add new logs (simulate real-time)
  const addNewLogs = () => {
    const enabledCameras = cameras.filter(cam => cam.workerEnabled);
    if (enabledCameras.length === 0) return;

    const newLogs: WorkerLog[] = [];
    enabledCameras.forEach(cam => {
      const timestamp = new Date().toISOString();
      
      // Random log generation
      const rand = Math.random();
      if (rand > 0.7) {
        newLogs.push({
          timestamp,
          level: 'INFO',
          cameraId: cam.id,
          cameraName: cam.name,
          message: `✅ Updated occupancy: ${Math.floor(Math.random() * 5)}/${Math.floor(Math.random() * 10) + 5} occupied`,
        });
      } else if (rand > 0.5) {
        newLogs.push({
          timestamp,
          level: 'DEBUG',
          cameraId: cam.id,
          cameraName: cam.name,
          message: `Fetched ${Math.floor(Math.random() * 50000) + 40000} bytes from camera`,
        });
      } else if (rand < 0.1) {
        newLogs.push({
          timestamp,
          level: 'WARNING',
          cameraId: cam.id,
          cameraName: cam.name,
          message: `⚠️ No vehicles detected in current frame`,
        });
      }
    });

    if (newLogs.length > 0) {
      setLogs(prev => [...prev, ...newLogs].slice(-500)); // Keep last 500 logs
    }
  };

  // Refresh worker status (simulate API call)
  const refreshWorkerStatus = () => {
    setWorkerStatuses(prev => prev.map(status => {
      if (!status.enabled) {
        return { ...status, status: 'idle' };
      }

      // Simulate random status
      const rand = Math.random();
      if (rand > 0.9) {
        return {
          ...status,
          status: 'error',
          errorMessage: 'Failed to fetch frame from camera',
          lastCheck: new Date().toISOString(),
        };
      }

      return {
        ...status,
        status: 'running',
        lastCheck: new Date().toISOString(),
        spacesCount: Math.floor(Math.random() * 10) + 5,
        occupiedCount: Math.floor(Math.random() * 5),
      };
    }));
  };

  // Toggle worker for camera
  const handleToggleWorker = async (cameraId: string, enabled: boolean) => {
    try {
      await toggleWorkerForCamera(cameraId, enabled);
      
      // Update local state
      setCameras(prev => prev.map(cam => 
        cam.id === cameraId ? { ...cam, workerEnabled: enabled } : cam
      ));
      
      setWorkerStatuses(prev => prev.map(status =>
        status.cameraId === cameraId 
          ? { ...status, enabled, status: enabled ? 'running' : 'idle' }
          : status
      ));

      // Add log
      const camera = cameras.find(c => c.id === cameraId);
      if (camera) {
        const newLog: WorkerLog = {
          timestamp: new Date().toISOString(),
          level: 'INFO',
          cameraId,
          cameraName: camera.name,
          message: `🔄 Worker ${enabled ? 'enabled' : 'disabled'} by admin`,
        };
        setLogs(prev => [...prev, newLog]);
      }
    } catch (error) {
      console.error('Failed to toggle worker:', error);
      alert('Failed to update worker status');
    }
  };

  // Clear logs
  const handleClearLogs = () => {
    if (confirm('Clear all logs?')) {
      setLogs([]);
    }
  };

  // Export logs
  const handleExportLogs = () => {
    const dataStr = JSON.stringify(logs, null, 2);
    const dataBlob = new Blob([dataStr], { type: 'application/json' });
    const url = URL.createObjectURL(dataBlob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `worker-logs-${new Date().toISOString()}.json`;
    link.click();
    URL.revokeObjectURL(url);
  };

  // Open live detection stream
  const handleViewDetectionStream = (cameraId: string) => {
    const camera = cameras.find(c => c.id === cameraId);
    if (!camera || !camera.workerEnabled) {
      alert('Worker must be enabled to view detection stream');
      return;
    }

    // Encode camera URL for query parameter
    const encodedCameraUrl = encodeURIComponent(camera.ipAddress);
    
    // Create HTTP stream URL with detection
    const url = `http://localhost:8069/stream/detect?camera_url=${encodedCameraUrl}&conf=0.25&fps=10&skip_frames=2`;
    
    setStreamUrl(url);
    setStreamingCameraId(cameraId);
    setShowDetectionStream(true);

    addNewLog({
      timestamp: new Date().toISOString(),
      level: 'INFO',
      cameraId: camera.id,
      cameraName: camera.name,
      message: '📹 Live detection stream opened',
    });
  };

  // Close detection stream
  const handleCloseDetectionStream = () => {
    const camera = cameras.find(c => c.id === streamingCameraId);
    
    if (camera) {
      addNewLog({
        timestamp: new Date().toISOString(),
        level: 'INFO',
        cameraId: camera.id,
        cameraName: camera.name,
        message: '📴 Live detection stream closed',
      });
    }
    
    setShowDetectionStream(false);
    setStreamingCameraId(null);
    setStreamUrl('');
  };

  // Helper to add a single log
  const addNewLog = (log: WorkerLog) => {
    setLogs(prev => [...prev, log].slice(-500));
  };

  // Filter logs
  const filteredLogs = logs.filter(log => {
    if (selectedCamera && log.cameraId !== selectedCamera) return false;
    if (logLevel !== 'ALL' && log.level !== logLevel) return false;
    return true;
  });

  // Calculate statistics
  const stats = {
    totalCameras: cameras.length,
    enabledWorkers: cameras.filter(c => c.workerEnabled).length,
    runningWorkers: workerStatuses.filter(s => s.status === 'running').length,
    errorWorkers: workerStatuses.filter(s => s.status === 'error').length,
    totalLogs: logs.length,
  };

  if (!user || !isAdmin) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-b from-strawberry-50 to-matcha-50">
        <div className="text-center">
          <h2 className="text-2xl font-bold text-strawberry-900 mb-4">
            🔒 Admin Access Required
          </h2>
          <p className="text-gray-600">
            Only administrators can access the worker monitor dashboard.
          </p>
        </div>
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-b from-strawberry-50 to-matcha-50">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-strawberry-500 mx-auto mb-4"></div>
          <p className="text-gray-600">Loading worker monitor...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-b from-strawberry-50 to-matcha-50 p-6">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="bg-white rounded-xl shadow-lg p-6 mb-6 border-2 border-strawberry-200">
          <h1 className="text-3xl font-bold text-strawberry-900 mb-2">
            🖥️ Worker Monitor Dashboard
          </h1>
          <p className="text-gray-600">
            Monitor and control background worker processes for parking space detection
          </p>
        </div>

        {/* Statistics Cards */}
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mb-6">
          <div className="bg-white rounded-xl shadow-lg p-4 border-2 border-blue-200">
            <div className="text-2xl mb-2">📹</div>
            <div className="text-2xl font-bold text-blue-900">{stats.totalCameras}</div>
            <div className="text-sm text-gray-600">Total Cameras</div>
          </div>
          
          <div className="bg-white rounded-xl shadow-lg p-4 border-2 border-green-200">
            <div className="text-2xl mb-2">✅</div>
            <div className="text-2xl font-bold text-green-900">{stats.enabledWorkers}</div>
            <div className="text-sm text-gray-600">Workers Enabled</div>
          </div>
          
          <div className="bg-white rounded-xl shadow-lg p-4 border-2 border-purple-200">
            <div className="text-2xl mb-2">🔄</div>
            <div className="text-2xl font-bold text-purple-900">{stats.runningWorkers}</div>
            <div className="text-sm text-gray-600">Running Now</div>
          </div>
          
          <div className="bg-white rounded-xl shadow-lg p-4 border-2 border-red-200">
            <div className="text-2xl mb-2">❌</div>
            <div className="text-2xl font-bold text-red-900">{stats.errorWorkers}</div>
            <div className="text-sm text-gray-600">Errors</div>
          </div>
          
          <div className="bg-white rounded-xl shadow-lg p-4 border-2 border-yellow-200">
            <div className="text-2xl mb-2">📝</div>
            <div className="text-2xl font-bold text-yellow-900">{stats.totalLogs}</div>
            <div className="text-sm text-gray-600">Total Logs</div>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Left Column: Camera Status & Controls */}
          <div className="lg:col-span-1 space-y-6">
            {/* Controls */}
            <div className="bg-white rounded-xl shadow-lg p-6 border-2 border-matcha-200">
              <h2 className="text-xl font-bold text-matcha-900 mb-4">⚙️ Controls</h2>
              
              <div className="space-y-4">
                {/* Auto Refresh */}
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium text-gray-700">Auto Refresh</span>
                  <button
                    onClick={() => setAutoRefresh(!autoRefresh)}
                    className={`px-4 py-2 rounded-lg font-medium transition-colors ${
                      autoRefresh
                        ? 'bg-green-500 text-white'
                        : 'bg-gray-300 text-gray-700'
                    }`}
                  >
                    {autoRefresh ? '✅ ON' : '⏸️ OFF'}
                  </button>
                </div>

                {/* Refresh Interval */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Refresh Interval: {refreshInterval}s
                  </label>
                  <input
                    type="range"
                    min="1"
                    max="30"
                    value={refreshInterval}
                    onChange={(e) => setRefreshInterval(Number(e.target.value))}
                    className="w-full"
                  />
                </div>

                {/* Manual Refresh */}
                <button
                  onClick={refreshWorkerStatus}
                  className="w-full px-4 py-2 bg-blue-500 text-white rounded-lg font-medium hover:bg-blue-600 transition-colors"
                >
                  🔄 Refresh Now
                </button>
              </div>
            </div>

            {/* Camera Status List */}
            <div className="bg-white rounded-xl shadow-lg p-6 border-2 border-purple-200">
              <h2 className="text-xl font-bold text-purple-900 mb-4">📹 Cameras ({cameras.length})</h2>
              
              <div className="space-y-3 max-h-96 overflow-y-auto">
                {cameras.map(camera => {
                  const status = workerStatuses.find(s => s.cameraId === camera.id);
                  const statusColor = 
                    status?.status === 'running' ? 'bg-green-100 border-green-400' :
                    status?.status === 'error' ? 'bg-red-100 border-red-400' :
                    status?.enabled ? 'bg-yellow-100 border-yellow-400' :
                    'bg-gray-100 border-gray-300';
                  
                  const statusIcon = 
                    status?.status === 'running' ? '🟢' :
                    status?.status === 'error' ? '🔴' :
                    status?.enabled ? '🟡' :
                    '⚪';

                  return (
                    <div
                      key={camera.id}
                      className={`p-4 rounded-lg border-2 ${statusColor} transition-all cursor-pointer ${
                        selectedCamera === camera.id ? 'ring-2 ring-purple-500' : ''
                      }`}
                      onClick={() => setSelectedCamera(selectedCamera === camera.id ? null : camera.id)}
                    >
                      <div className="flex items-start justify-between mb-2">
                        <div className="flex-1">
                          <div className="flex items-center gap-2 mb-1">
                            <span className="text-lg">{statusIcon}</span>
                            <h3 className="font-bold text-gray-900">{camera.name}</h3>
                          </div>
                          <p className="text-xs text-gray-600">{camera.ipAddress}</p>
                        </div>
                        
                        <div className="flex gap-2">
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              handleToggleWorker(camera.id, !camera.workerEnabled);
                            }}
                            className={`px-3 py-1 rounded-lg text-xs font-medium transition-colors ${
                              camera.workerEnabled
                                ? 'bg-green-500 text-white hover:bg-green-600'
                                : 'bg-gray-400 text-white hover:bg-gray-500'
                            }`}
                          >
                            {camera.workerEnabled ? 'ON' : 'OFF'}
                          </button>

                          {camera.workerEnabled && (
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                handleViewDetectionStream(camera.id);
                              }}
                              className="px-3 py-1 rounded-lg text-xs font-medium bg-blue-500 text-white hover:bg-blue-600 transition-colors"
                            >
                              📹 View Live
                            </button>
                          )}
                        </div>
                      </div>

                      {/* Status Details */}
                      {status && camera.workerEnabled && (
                        <div className="mt-2 pt-2 border-t border-gray-300">
                          <div className="grid grid-cols-2 gap-2 text-xs">
                            {status.lastCheck && (
                              <div>
                                <span className="text-gray-600">Last Check:</span>
                                <br />
                                <span className="font-medium">
                                  {new Date(status.lastCheck).toLocaleTimeString()}
                                </span>
                              </div>
                            )}
                            {status.spacesCount !== undefined && (
                              <div>
                                <span className="text-gray-600">Spaces:</span>
                                <br />
                                <span className="font-medium">
                                  {status.occupiedCount}/{status.spacesCount}
                                </span>
                              </div>
                            )}
                          </div>
                          {status.errorMessage && (
                            <div className="mt-2 text-xs text-red-600">
                              ⚠️ {status.errorMessage}
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          </div>

          {/* Right Column: Logs */}
          <div className="lg:col-span-2">
            <div className="bg-white rounded-xl shadow-lg border-2 border-yellow-200">
              {/* Logs Header */}
              <div className="p-6 border-b border-gray-200">
                <div className="flex items-center justify-between mb-4">
                  <h2 className="text-xl font-bold text-yellow-900">📝 Worker Logs</h2>
                  <div className="flex gap-2">
                    <button
                      onClick={handleExportLogs}
                      className="px-3 py-1 bg-blue-500 text-white rounded-lg text-sm font-medium hover:bg-blue-600 transition-colors"
                      disabled={logs.length === 0}
                    >
                      💾 Export
                    </button>
                    <button
                      onClick={handleClearLogs}
                      className="px-3 py-1 bg-red-500 text-white rounded-lg text-sm font-medium hover:bg-red-600 transition-colors"
                      disabled={logs.length === 0}
                    >
                      🗑️ Clear
                    </button>
                  </div>
                </div>

                {/* Filters */}
                <div className="flex gap-4">
                  <div className="flex-1">
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Filter by Camera
                    </label>
                    <select
                      value={selectedCamera || ''}
                      onChange={(e) => setSelectedCamera(e.target.value || null)}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-yellow-400"
                    >
                      <option value="">All Cameras</option>
                      {cameras.map(cam => (
                        <option key={cam.id} value={cam.id}>
                          {cam.name}
                        </option>
                      ))}
                    </select>
                  </div>

                  <div className="flex-1">
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Log Level
                    </label>
                    <select
                      value={logLevel}
                      onChange={(e) => setLogLevel(e.target.value as any)}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-yellow-400"
                    >
                      <option value="ALL">All Levels</option>
                      <option value="INFO">INFO</option>
                      <option value="WARNING">WARNING</option>
                      <option value="ERROR">ERROR</option>
                      <option value="DEBUG">DEBUG</option>
                    </select>
                  </div>
                </div>
              </div>

              {/* Logs Content */}
              <div className="p-4 bg-gray-900 font-mono text-sm h-[600px] overflow-y-auto">
                {filteredLogs.length === 0 ? (
                  <div className="text-center text-gray-500 py-8">
                    No logs to display. Enable workers to see activity.
                  </div>
                ) : (
                  <div className="space-y-1">
                    {filteredLogs.map((log, index) => {
                      const logColor = 
                        log.level === 'ERROR' ? 'text-red-400' :
                        log.level === 'WARNING' ? 'text-yellow-400' :
                        log.level === 'DEBUG' ? 'text-gray-400' :
                        'text-green-400';

                      const timestamp = new Date(log.timestamp).toLocaleTimeString('en-US', {
                        hour12: false,
                        hour: '2-digit',
                        minute: '2-digit',
                        second: '2-digit',
                      });

                      return (
                        <div key={index} className={`${logColor}`}>
                          <span className="text-gray-500">[{timestamp}]</span>
                          {' '}
                          <span className="text-blue-400">[{log.level}]</span>
                          {' '}
                          <span className="text-purple-400">[{log.cameraName}]</span>
                          {' '}
                          <span>{log.message}</span>
                        </div>
                      );
                    })}
                    <div ref={logsEndRef} />
                  </div>
                )}
              </div>

              {/* Logs Footer */}
              <div className="p-4 border-t border-gray-200 bg-gray-50">
                <div className="flex items-center justify-between text-sm text-gray-600">
                  <span>
                    Showing {filteredLogs.length} of {logs.length} logs
                  </span>
                  <span>
                    {autoRefresh && (
                      <>⏱️ Auto-refreshing every {refreshInterval}s</>
                    )}
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Live Detection Stream Modal */}
      {showDetectionStream && streamingCameraId && (
        <div className="fixed inset-0 bg-black bg-opacity-75 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-lg shadow-2xl w-full max-w-5xl max-h-[90vh] flex flex-col">
            {/* Modal Header */}
            <div className="flex items-center justify-between p-4 border-b border-gray-200">
              <h3 className="text-xl font-bold text-gray-800">
                📹 Live Detection Stream - {cameras.find(c => c.id === streamingCameraId)?.name}
              </h3>
              <button
                onClick={handleCloseDetectionStream}
                className="px-4 py-2 bg-red-500 text-white rounded-lg hover:bg-red-600 transition-colors"
              >
                ❌ Close
              </button>
            </div>

            {/* Stream Container */}
            <div className="flex-1 flex items-center justify-center p-4 bg-gray-900 overflow-auto">
              <img
                src={streamUrl}
                alt="Live Detection Stream"
                className="max-w-full max-h-full border-2 border-blue-500"
                onError={(e) => {
                  console.error('Stream error:', e);
                  const camera = cameras.find(c => c.id === streamingCameraId);
                  if (camera) {
                    addNewLog({
                      timestamp: new Date().toISOString(),
                      level: 'ERROR',
                      cameraId: camera.id,
                      cameraName: camera.name,
                      message: '❌ Failed to load detection stream',
                    });
                  }
                }}
              />
            </div>

            {/* Modal Footer */}
            <div className="p-4 border-t border-gray-200 bg-gray-50">
              <div className="flex items-center justify-between text-sm text-gray-600">
                <span>🔴 Live streaming from worker detection</span>
                <span>Press ESC or click Close to stop</span>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
