import { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import { getUserESP32Configs, type ESP32Config } from '../services/esp32ConfigService';
import { getParkingLotsByOwner, getParkingLot } from '../services/parkingLotService';
import type { ParkingLot } from '../types/parkingLot.types';

interface StreamState {
  cameraId: string;
  metadata: any;
  connectionStatus: 'connecting' | 'connected' | 'error' | 'disconnected';
}

export default function DetectionViewerPage() {
  const { user } = useAuth();
  const [parkingLots, setParkingLots] = useState<ParkingLot[]>([]);
  const [selectedLotId, setSelectedLotId] = useState<string>('');
  const [cameras, setCameras] = useState<ESP32Config[]>([]);
  const [streamStates, setStreamStates] = useState<Map<string, StreamState>>(new Map());

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
    }
  }, [selectedLotId, user]);

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
      
      // Auto-start streaming for all cameras (raw stream doesn't need worker)
      lotCameras.forEach(camera => {
        startStreamForCamera(camera);
      });
      
      console.log(`✅ Loaded ${lotCameras.length} cameras for parking lot ${lot.name}`);
    } catch (error) {
      console.error('Error loading cameras:', error);
    }
  };

  const startStreamForCamera = (camera: ESP32Config) => {
    if (!user) return;

    console.log(`🎥 Starting raw stream for camera: ${camera.name}`);

    // Initialize stream state
    setStreamStates(prev => {
      const newMap = new Map(prev);
      newMap.set(camera.id, {
        cameraId: camera.id,
        metadata: null,
        connectionStatus: 'connected' // Raw stream is always ready
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
    // Clear all stream states
    setStreamStates(new Map());
  };

  const getStreamUrl = (camera: ESP32Config) => {
    // Use raw camera stream from ipAddress (e.g., http://localhost:5069/stream)
    const baseUrl = camera.ipAddress.endsWith('/') 
      ? camera.ipAddress.slice(0, -1) 
      : camera.ipAddress;
    return `${baseUrl}/stream`;
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
          <h1 className="text-3xl font-bold text-gray-800 mb-2">
            📺 Raw Camera Viewer
          </h1>
          <p className="text-gray-600">
            Watch raw video streams from all cameras in selected parking lot
          </p>
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

        {/* Cameras Grid */}
        {selectedLotId && (
          <div className="bg-white rounded-lg shadow-md p-6">
            <h2 className="text-xl font-bold text-gray-800 mb-4">
              📹 Camera Streams ({cameras.length})
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
                      <div className="bg-gray-800 text-white p-3 flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <h3 className="text-sm font-semibold truncate">
                            📹 {camera.name}
                          </h3>
                          <div className={`w-2 h-2 rounded-full ${getStatusColor(status)} ${status === 'connected' ? 'animate-pulse' : ''}`}></div>
                        </div>
                        <span className="text-xs text-gray-400 capitalize">{status}</span>
                      </div>

                      {/* Video Stream */}
                      <div className="relative bg-black" style={{ aspectRatio: '16/9' }}>
                        <img
                          src={getStreamUrl(camera)}
                          alt={`${camera.name} raw stream`}
                          className="w-full h-full object-contain"
                          onError={() => {
                            console.error(`Stream error for ${camera.name}`);
                            updateStreamState(camera.id, { connectionStatus: 'error' });
                          }}
                          onLoad={() => {
                            updateStreamState(camera.id, { connectionStatus: 'connected' });
                          }}
                        />
                      </div>

                      {/* Camera Info Footer */}
                      <div className="bg-gray-800 text-white p-2">
                        <div className="text-xs text-gray-400">
                          <div className="flex justify-between">
                            <span>IP Address:</span>
                            <span className="font-mono text-green-400">{camera.ipAddress}</span>
                          </div>
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
