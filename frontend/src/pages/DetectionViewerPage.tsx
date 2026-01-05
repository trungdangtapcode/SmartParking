import { useState, useEffect, useRef } from 'react';
import { useAuth } from '../context/AuthContext';
import { getUserESP32Configs, type ESP32Config } from '../services/esp32ConfigService';
import { getParkingLotsByOwner } from '../services/parkingLotService';

interface ParkingLot {
  id: string;
  name: string;
  address: string;
}

export default function DetectionViewerPage() {
  const { user } = useAuth();
  const [parkingLots, setParkingLots] = useState<ParkingLot[]>([]);
  const [selectedLotId, setSelectedLotId] = useState<string>('');
  const [cameras, setCameras] = useState<ESP32Config[]>([]);
  const [selectedCamera, setSelectedCamera] = useState<ESP32Config | null>(null);
  const [isStreaming, setIsStreaming] = useState(false);
  const [streamMetadata, setStreamMetadata] = useState<any>(null);
  const [connectionStatus, setConnectionStatus] = useState<string>('disconnected');
  
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimerRef = useRef<number | null>(null);

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
    }
  }, [selectedLotId, user]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      stopStreaming();
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
      if (!user) return;
      const configs = await getUserESP32Configs(user.uid);
      
      // Show all cameras for now (parkingLotId mapping not implemented yet)
      setCameras(configs);
    } catch (error) {
      console.error('Error loading cameras:', error);
    }
  };

  const startStreaming = (camera: ESP32Config) => {
    if (!camera.workerEnabled) {
      alert('Worker must be enabled for this camera to view detection stream');
      return;
    }

    setSelectedCamera(camera);
    setIsStreaming(true);
    setConnectionStatus('connecting');

    // Wait for modal to render
    setTimeout(() => {
      connectWebSocket(camera);
    }, 100);
  };

  const connectWebSocket = (camera: ESP32Config) => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    // Close existing connection
    if (wsRef.current) {
      wsRef.current.close();
    }

    // Create WebSocket connection to viewer endpoint
    const wsUrl = `ws://localhost:8069/ws/viewer/detection?camera_id=${encodeURIComponent(camera.id)}&user_id=${encodeURIComponent(user?.uid || '')}`;
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      console.log('✅ Connected to detection viewer');
      setConnectionStatus('connected');
    };

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        
        if (msg.type === 'frame') {
          // Draw frame to canvas
          const img = new Image();
          img.onload = () => {
            canvas.width = img.width;
            canvas.height = img.height;
            ctx.drawImage(img, 0, 0);
          };
          img.src = `data:image/jpeg;base64,${msg.data}`;
          
          // Update metadata
          if (msg.metadata) {
            setStreamMetadata(msg.metadata);
          }
        } else if (msg.type === 'info') {
          console.log('ℹ️', msg.message);
        } else if (msg.type === 'error') {
          console.error('❌ Stream error:', msg.message);
          setConnectionStatus('error');
        }
      } catch (error) {
        console.error('Error parsing WebSocket message:', error);
      }
    };

    ws.onerror = (error) => {
      console.error('WebSocket error:', error);
      setConnectionStatus('error');
    };

    ws.onclose = () => {
      console.log('🔌 Disconnected from detection viewer');
      setConnectionStatus('disconnected');
      
      // Auto-reconnect if streaming is still active
      if (isStreaming) {
        reconnectTimerRef.current = setTimeout(() => {
          console.log('🔄 Attempting to reconnect...');
          connectWebSocket(camera);
        }, 3000);
      }
    };
  };

  const stopStreaming = () => {
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    
    if (reconnectTimerRef.current) {
      clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = null;
    }
    
    setIsStreaming(false);
    setSelectedCamera(null);
    setStreamMetadata(null);
    setConnectionStatus('disconnected');
  };

  const getStatusColor = () => {
    switch (connectionStatus) {
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
          <h1 className="text-3xl font-bold text-gray-800 mb-2">
            📺 Live Detection Viewer
          </h1>
          <p className="text-gray-600">
            Watch real-time detection from active workers (GPU-efficient streaming)
          </p>
        </div>

        {/* Parking Lot Selector */}
        <div className="bg-white rounded-lg shadow-md p-6 mb-6">
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Select Parking Lot:
          </label>
          <select
            value={selectedLotId}
            onChange={(e) => setSelectedLotId(e.target.value)}
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

        {/* Cameras Grid */}
        {selectedLotId && (
          <div className="bg-white rounded-lg shadow-md p-6">
            <h2 className="text-xl font-bold text-gray-800 mb-4">
              Cameras ({cameras.length})
            </h2>

            {cameras.length === 0 ? (
              <div className="text-center py-12 text-gray-500">
                <p className="text-lg">No cameras found for this parking lot</p>
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {cameras.map((camera) => (
                  <div
                    key={camera.id}
                    className="border border-gray-200 rounded-lg p-4 hover:shadow-lg transition-shadow"
                  >
                    <div className="flex items-center justify-between mb-3">
                      <h3 className="text-lg font-semibold text-gray-800">
                        📹 {camera.name}
                      </h3>
                      <span
                        className={`px-2 py-1 rounded text-xs font-medium ${
                          camera.workerEnabled
                            ? 'bg-green-100 text-green-800'
                            : 'bg-gray-100 text-gray-800'
                        }`}
                      >
                        {camera.workerEnabled ? 'Worker ON' : 'Worker OFF'}
                      </span>
                    </div>

                    <div className="text-sm text-gray-600 mb-4">
                      <p>IP: {camera.ipAddress}</p>
                    </div>

                    <button
                      onClick={() => startStreaming(camera)}
                      disabled={!camera.workerEnabled}
                      className={`w-full px-4 py-2 rounded-lg font-medium transition-colors ${
                        camera.workerEnabled
                          ? 'bg-blue-500 text-white hover:bg-blue-600'
                          : 'bg-gray-300 text-gray-500 cursor-not-allowed'
                      }`}
                    >
                      {camera.workerEnabled ? '▶️ Watch Live Detection' : '⏸️ Worker Disabled'}
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Streaming Modal */}
      {isStreaming && selectedCamera && (
        <div className="fixed inset-0 bg-black bg-opacity-90 z-50 flex items-center justify-center p-4">
          <div className="w-full max-w-6xl max-h-[95vh] flex flex-col">
            {/* Header */}
            <div className="bg-gray-800 text-white p-4 rounded-t-lg flex items-center justify-between">
              <div className="flex items-center gap-4">
                <h3 className="text-xl font-bold">
                  📹 {selectedCamera.name}
                </h3>
                <div className="flex items-center gap-2">
                  <div className={`w-3 h-3 rounded-full ${getStatusColor()} animate-pulse`}></div>
                  <span className="text-sm capitalize">{connectionStatus}</span>
                </div>
              </div>
              <button
                onClick={stopStreaming}
                className="px-4 py-2 bg-red-500 text-white rounded-lg hover:bg-red-600 transition-colors"
              >
                ❌ Close
              </button>
            </div>

            {/* Stream Display */}
            <div className="flex-1 bg-gray-900 flex items-center justify-center p-4">
              <canvas
                ref={canvasRef}
                className="max-w-full max-h-full border-2 border-blue-500"
              />
            </div>

            {/* Metadata Footer */}
            {streamMetadata && (
              <div className="bg-gray-800 text-white p-4 rounded-b-lg">
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                  <div>
                    <span className="text-gray-400">Vehicles Detected:</span>
                    <span className="ml-2 font-bold text-yellow-400">
                      {streamMetadata.vehicle_count || 0}
                    </span>
                  </div>
                  <div>
                    <span className="text-gray-400">Occupied:</span>
                    <span className="ml-2 font-bold text-red-400">
                      {streamMetadata.occupied_spaces || 0}
                    </span>
                  </div>
                  <div>
                    <span className="text-gray-400">Total Spaces:</span>
                    <span className="ml-2 font-bold text-blue-400">
                      {streamMetadata.total_spaces || 0}
                    </span>
                  </div>
                  <div>
                    <span className="text-gray-400">Last Updated:</span>
                    <span className="ml-2 font-bold text-green-400">
                      {streamMetadata.timestamp
                        ? new Date(streamMetadata.timestamp).toLocaleTimeString()
                        : 'N/A'}
                    </span>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
