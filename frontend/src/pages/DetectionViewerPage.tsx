import { useState, useEffect, useRef } from 'react';
import { useAuth } from '../context/AuthContext';
import { getUserESP32Configs, type ESP32Config } from '../services/esp32ConfigService';
import { getParkingLotsByOwner, getParkingLot } from '../services/parkingLotService';
import type { ParkingLot } from '../types/parkingLot.types';

interface DetectionMetadata {
  vehicle_count: number;
  occupied_spaces: number;
  total_spaces: number;
  timestamp: string;
}

interface StreamState {
  cameraId: string;
  metadata: DetectionMetadata | null;
  connectionStatus: 'connecting' | 'connected' | 'error' | 'disconnected';
  workerActive: boolean;
  lastFrameTime: number;
}

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8069';

export default function DetectionViewerPage() {
  const { user } = useAuth();
  const [parkingLots, setParkingLots] = useState<ParkingLot[]>([]);
  const [selectedLotId, setSelectedLotId] = useState<string>('');
  const [cameras, setCameras] = useState<ESP32Config[]>([]);
  const [streamStates, setStreamStates] = useState<Map<string, StreamState>>(new Map());
  const [viewMode, setViewMode] = useState<'detection' | 'raw'>('detection');
  const wsRefs = useRef<Map<string, WebSocket>>(new Map());

  // Load parking lots on mount
  useEffect(() => {
    if (user) {
      loadParkingLots();
    }
  }, [user]);

  // Load cameras when parking lot changes
  useEffect(() => {
    if (selectedLotId && user) {
      loadCameras();
    } else {
      setCameras([]);
      stopAllStreams();
    }
  }, [selectedLotId, user]);

  // Restart streams when view mode changes
  useEffect(() => {
    if (cameras.length > 0) {
      stopAllStreams();
      cameras.forEach(camera => {
        if (viewMode === 'detection') {
          startDetectionStreamForCamera(camera);
        } else {
          startRawStreamForCamera(camera);
        }
      });
    }
  }, [viewMode]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      stopAllStreams();
    };
  }, []);

  const loadParkingLots = async () => {
    try {
      if (!user) return;
      const lots = await getParkingLotsByOwner(user.uid);
      setParkingLots(lots);
      
      if (lots.length > 0 && !selectedLotId) {
        setSelectedLotId(lots[0].id);
      }
    } catch (error) {
      console.error('Error loading parking lots:', error);
    }
  };

  const loadCameras = async () => {
    try {
      if (!user || !selectedLotId) return;
      
      // Get the selected parking lot details
      const lot = await getParkingLot(selectedLotId);
      
      if (!lot || !lot.cameras || lot.cameras.length === 0) {
        setCameras([]);
        return;
      }
      
      // Get all user's camera configs
      const allConfigs = await getUserESP32Configs(user.uid);
      
      // Filter cameras that belong to this parking lot
      const lotCameras = allConfigs.filter(config => 
        lot.cameras.includes(config.id)
      );
      
      setCameras(lotCameras);
      
      // Auto-start streaming for all cameras
      lotCameras.forEach(camera => {
        if (viewMode === 'detection') {
          startDetectionStreamForCamera(camera);
        } else {
          startRawStreamForCamera(camera);
        }
      });
      
      console.log(`✅ Loaded ${lotCameras.length} cameras for parking lot ${lot.name}`);
    } catch (error) {
      console.error('Error loading cameras:', error);
    }
  };

  const startDetectionStreamForCamera = (camera: ESP32Config) => {
    if (!user) return;

    // Check if worker is active for this camera
    const hasWorker = camera.workerActive === true;
    const lastUpdate = camera.lastWorkerUpdate ? new Date(camera.lastWorkerUpdate) : null;
    const isStale = lastUpdate ? (Date.now() - lastUpdate.getTime() > 30000) : true; // 30 seconds

    console.log(`🎥 Starting detection stream for camera: ${camera.name}, workerActive: ${hasWorker}, stale: ${isStale}`);

    // Initialize stream state
    setStreamStates(prev => {
      const newMap = new Map(prev);
      newMap.set(camera.id, {
        cameraId: camera.id,
        metadata: null,
        connectionStatus: hasWorker && !isStale ? 'connecting' : 'disconnected',
        workerActive: hasWorker && !isStale,
        lastFrameTime: Date.now()
      });
      return newMap;
    });

    // If no worker is active, don't try to connect
    if (!hasWorker || isStale) {
      console.warn(`⚠️ No active worker for camera ${camera.name} - skipping WebSocket connection`);
      updateStreamState(camera.id, { 
        connectionStatus: 'error', 
        workerActive: false 
      });
      return;
    }

    // Connect to WebSocket for metadata updates
    const wsUrl = `${API_BASE_URL.replace('http', 'ws')}/ws/viewer/detection?camera_id=${camera.id}&user_id=${user.uid}`;
    const ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      console.log(`✅ WebSocket connected for ${camera.name}`);
      updateStreamState(camera.id, { connectionStatus: 'connected' });
    };

    ws.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data);
        
        if (message.type === 'frame') {
          // Update metadata from frame
          updateStreamState(camera.id, {
            metadata: message.metadata,
            workerActive: true,
            lastFrameTime: Date.now(),
            connectionStatus: 'connected'
          });
        } else if (message.type === 'info') {
          console.log(`ℹ️ ${message.message}`);
        } else if (message.type === 'error') {
          console.error(`❌ Error: ${message.message}`);
          updateStreamState(camera.id, { connectionStatus: 'error', workerActive: false });
        }
      } catch (error) {
        console.error('Error parsing WebSocket message:', error);
      }
    };

    ws.onerror = (error) => {
      console.error(`WebSocket error for ${camera.name}:`, error);
      updateStreamState(camera.id, { connectionStatus: 'error', workerActive: false });
    };

    ws.onclose = () => {
      console.log(`WebSocket closed for ${camera.name}`);
      updateStreamState(camera.id, { connectionStatus: 'disconnected', workerActive: false });
    };

    wsRefs.current.set(camera.id, ws);
  };

  const startRawStreamForCamera = (camera: ESP32Config) => {
    if (!user) return;

    console.log(`🎥 Starting raw stream for camera: ${camera.name}`);

    // Close any existing WebSocket
    const existingWs = wsRefs.current.get(camera.id);
    if (existingWs) {
      existingWs.close();
      wsRefs.current.delete(camera.id);
    }

    // Initialize stream state
    setStreamStates(prev => {
      const newMap = new Map(prev);
      newMap.set(camera.id, {
        cameraId: camera.id,
        metadata: null,
        connectionStatus: 'connected',
        workerActive: false,
        lastFrameTime: Date.now()
      });
      return newMap;
    });
  };

  const updateStreamState = (cameraId: string, updates: Partial<StreamState>) => {
    setStreamStates(prev => {
      const newMap = new Map(prev);
      const current = newMap.get(cameraId);
      if (current) {
        newMap.set(cameraId, { ...current, ...updates });
      }
      return newMap;
    });
  };

  const stopAllStreams = () => {
    // Close all WebSocket connections
    wsRefs.current.forEach((ws, cameraId) => {
      try {
        ws.close();
      } catch (error) {
        console.error(`Error closing WebSocket for ${cameraId}:`, error);
      }
    });
    wsRefs.current.clear();
    
    // Clear all stream states
    setStreamStates(new Map());
  };

  const getStreamUrl = (camera: ESP32Config) => {
    if (viewMode === 'detection') {
      // Use worker detection stream with bounding boxes
      return `${API_BASE_URL}/stream/worker-detection?camera_id=${camera.id}&fps=10`;
    } else {
      // Use raw camera stream from ipAddress (e.g., http://localhost:5069/stream)
      const baseUrl = camera.ipAddress.endsWith('/') 
        ? camera.ipAddress.slice(0, -1) 
        : camera.ipAddress;
      return `${baseUrl}/stream`;
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'connected':
        return 'bg-green-500';
      case 'connecting':
        return 'bg-yellow-500';
      case 'error':
        return 'bg-red-500';
      default:
        return 'bg-gray-500';
    }
  };

  return (
    <div className="min-h-screen bg-gray-100 p-6">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="bg-white rounded-lg shadow-md p-6 mb-6">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-3xl font-bold text-gray-800 mb-2">
                📺 Detection Viewer
              </h1>
              <p className="text-gray-600">
                Watch worker detection results with bounding boxes and occupancy info
              </p>
            </div>
            
            {/* View Mode Toggle */}
            <div className="flex items-center gap-2 bg-gray-100 rounded-lg p-1">
              <button
                onClick={() => setViewMode('detection')}
                className={`px-4 py-2 rounded-md font-medium transition-all ${
                  viewMode === 'detection'
                    ? 'bg-blue-500 text-white shadow-md'
                    : 'bg-transparent text-gray-600 hover:bg-gray-200'
                }`}
              >
                🎯 Detection View
              </button>
              <button
                onClick={() => setViewMode('raw')}
                className={`px-4 py-2 rounded-md font-medium transition-all ${
                  viewMode === 'raw'
                    ? 'bg-blue-500 text-white shadow-md'
                    : 'bg-transparent text-gray-600 hover:bg-gray-200'
                }`}
              >
                📹 Raw Stream
              </button>
            </div>
          </div>
        </div>

        {/* Parking Lot Selector */}
        <div className="bg-white rounded-lg shadow-md p-6 mb-6">
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Select Parking Lot:
          </label>
          <select
            value={selectedLotId}
            onChange={(e) => {
              stopAllStreams(); // Stop all streams when changing parking lot
              setSelectedLotId(e.target.value);
            }}
            className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          >
            <option value="">-- Choose a parking lot --</option>
            {parkingLots.map((lot) => (
              <option key={lot.id} value={lot.id}>
                {lot.name} - {lot.address}
              </option>
            ))}
          </select>
        </div>

        {/* Info Banner for Detection Mode */}
        {selectedLotId && viewMode === 'detection' && (
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-6">
            <div className="flex items-start gap-3">
              <span className="text-2xl">💡</span>
              <div>
                <h3 className="font-semibold text-blue-900 mb-1">Worker Detection Stream</h3>
                <p className="text-sm text-blue-800">
                  This view shows real-time detection results from the parking monitor worker.
                  All viewers share the same detection stream - adding more viewers doesn't increase GPU load!
                </p>
                <div className="mt-2 flex items-center gap-4 text-xs text-blue-700">
                  <span>✅ Bounding boxes around vehicles</span>
                  <span>✅ Parking space boundaries</span>
                  <span>✅ Real-time occupancy status</span>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Cameras Grid */}
        {selectedLotId && (
          <div className="bg-white rounded-lg shadow-md p-6">
            <h2 className="text-xl font-bold text-gray-800 mb-4">
              {viewMode === 'detection' ? '🎯 Detection Streams' : '📹 Raw Camera Streams'} ({cameras.length})
            </h2>

            {cameras.length === 0 ? (
              <div className="text-center py-12 text-gray-500">
                <p className="text-lg">No cameras found for this parking lot</p>
                <p className="text-sm mt-2">Please add cameras to this parking lot first</p>
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-2 xl:grid-cols-3 gap-6">
                {cameras.map((camera) => {
                  const streamState = streamStates.get(camera.id);
                  const status = streamState?.connectionStatus || 'disconnected';
                  
                  return (
                    <div
                      key={camera.id}
                      className="border-2 border-gray-200 rounded-lg overflow-hidden bg-gray-900 shadow-lg"
                    >
                      {/* Camera Header */}
                      <div className="bg-gray-800 text-white p-3">
                        <div className="flex items-center justify-between mb-2">
                          <div className="flex items-center gap-2">
                            <h3 className="text-sm font-semibold truncate">
                              {viewMode === 'detection' ? '🎯' : '📹'} {camera.name}
                            </h3>
                            <div className={`w-2 h-2 rounded-full ${getStatusColor(status)} ${status === 'connected' ? 'animate-pulse' : ''}`}></div>
                          </div>
                          <span className="text-xs text-gray-400 capitalize">{status}</span>
                        </div>
                        
                        {/* Detection Metadata - Only show in detection mode */}
                        {viewMode === 'detection' && streamState?.metadata && (
                          <div className="grid grid-cols-3 gap-2 text-xs">
                            <div className="bg-blue-900/50 rounded px-2 py-1">
                              <div className="text-gray-400">Vehicles</div>
                              <div className="font-bold text-blue-300">{streamState.metadata.vehicle_count}</div>
                            </div>
                            <div className="bg-red-900/50 rounded px-2 py-1">
                              <div className="text-gray-400">Occupied</div>
                              <div className="font-bold text-red-300">{streamState.metadata.occupied_spaces}</div>
                            </div>
                            <div className="bg-green-900/50 rounded px-2 py-1">
                              <div className="text-gray-400">Available</div>
                              <div className="font-bold text-green-300">
                                {streamState.metadata.total_spaces - streamState.metadata.occupied_spaces}
                              </div>
                            </div>
                          </div>
                        )}
                        
                        {/* Worker Status - Only show in detection mode */}
                        {viewMode === 'detection' && (
                          <div className="mt-2 text-xs">
                            {streamState?.workerActive ? (
                              <span className="text-green-400">✅ Worker Active</span>
                            ) : status === 'connected' ? (
                              <span className="text-yellow-400">⏳ Waiting for detection data...</span>
                            ) : status === 'connecting' ? (
                              <span className="text-yellow-400">⏳ Connecting to worker...</span>
                            ) : (
                              <span className="text-gray-400">⚠️ Worker not responding</span>
                            )}
                          </div>
                        )}
                      </div>

                      {/* Video Stream */}
                      <div className="relative bg-black" style={{ aspectRatio: '16/9' }}>
                        <img
                          key={`${camera.id}-${viewMode}`} // Force reload when switching modes
                          src={getStreamUrl(camera)}
                          alt={`${camera.name} ${viewMode} stream`}
                          className="w-full h-full object-contain"
                          onError={() => {
                            console.error(`Stream error for ${camera.name}`);
                            updateStreamState(camera.id, { connectionStatus: 'error' });
                          }}
                          onLoad={() => {
                            updateStreamState(camera.id, { connectionStatus: 'connected' });
                          }}
                        />
                        
                        {/* Overlay for disconnected state */}
                        {status !== 'connected' && (
                          <div className="absolute inset-0 flex items-center justify-center bg-black/80">
                            <div className="text-center text-white">
                              {status === 'connecting' && (
                                <>
                                  <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-white mx-auto mb-3"></div>
                                  <p>Connecting...</p>
                                </>
                              )}
                              {status === 'error' && (
                                <>
                                  <span className="text-4xl mb-3 block">⚠️</span>
                                  {viewMode === 'detection' ? (
                                    <>
                                      <p>No Worker Available</p>
                                      <p className="text-sm text-gray-400 mt-1">
                                        {camera.workerActive 
                                          ? 'Worker is not processing this camera' 
                                          : 'No worker assigned to this camera'}
                                      </p>
                                      <p className="text-xs text-blue-400 mt-2">
                                        💡 Switch to Raw Stream to view camera feed
                                      </p>
                                    </>
                                  ) : (
                                    <>
                                      <p>Camera Offline</p>
                                      <p className="text-sm text-gray-400 mt-1">
                                        Unable to connect to camera
                                      </p>
                                    </>
                                  )}
                                </>
                              )}
                              {status === 'disconnected' && (
                                <>
                                  <span className="text-4xl mb-3 block">🔌</span>
                                  <p>Disconnected</p>
                                </>
                              )}
                            </div>
                          </div>
                        )}
                      </div>

                      {/* Camera Info Footer */}
                      <div className="bg-gray-800 text-white p-2">
                        <div className="text-xs text-gray-400">
                          <div className="flex justify-between items-center">
                            <span>IP Address:</span>
                            <span className="font-mono text-green-400">{camera.ipAddress}</span>
                          </div>
                          {viewMode === 'detection' && streamState?.metadata && (
                            <div className="flex justify-between items-center mt-1 pt-1 border-t border-gray-700">
                              <span>Last Update:</span>
                              <span className="text-blue-400">
                                {new Date(streamState.metadata.timestamp).toLocaleTimeString()}
                              </span>
                            </div>
                          )}
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
