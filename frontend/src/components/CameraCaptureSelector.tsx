import { useState, useEffect } from 'react';
import { getParkingLotsByOwner } from '../services/parkingLotService';
import { getUserESP32Configs } from '../services/esp32ConfigService';
import type { ParkingLot } from '../types/parkingLot.types';
import type { ESP32Config } from '../services/esp32ConfigService';

interface CameraCaptureSelectorProps {
  userId: string;
  onCapture: (imageUrl: string) => void;
}

export function CameraCaptureSelector({ userId, onCapture }: CameraCaptureSelectorProps) {
  const [parkingLots, setParkingLots] = useState<ParkingLot[]>([]);
  const [cameras, setCameras] = useState<ESP32Config[]>([]);
  const [selectedParkingLot, setSelectedParkingLot] = useState<string>('');
  const [selectedCamera, setSelectedCamera] = useState<string>('');
  const [isCapturing, setIsCapturing] = useState(false);
  const [error, setError] = useState<string>('');

  // Load parking lots
  useEffect(() => {
    const loadParkingLots = async () => {
      try {
        const lots = await getParkingLotsByOwner(userId);
        setParkingLots(lots);
        if (lots.length > 0) {
          setSelectedParkingLot(lots[0].id);
        }
      } catch (err) {
        console.error('Failed to load parking lots:', err);
        setError('Failed to load parking lots');
      }
    };

    loadParkingLots();
  }, [userId]);

  // Load cameras when parking lot changes
  useEffect(() => {
    const loadCameras = async () => {
      if (!selectedParkingLot) {
        setCameras([]);
        return;
      }

      try {
        const allCameras = await getUserESP32Configs(userId);
        const parkingLot = parkingLots.find(lot => lot.id === selectedParkingLot);
        
        if (parkingLot?.cameras) {
          // Filter cameras that belong to this parking lot
          const lotCameras = allCameras.filter(camera => 
            parkingLot.cameras.includes(camera.id)
          );
          setCameras(lotCameras);
          if (lotCameras.length > 0) {
            setSelectedCamera(lotCameras[0].id);
          }
        } else {
          setCameras([]);
        }
      } catch (err) {
        console.error('Failed to load cameras:', err);
        setError('Failed to load cameras');
      }
    };

    loadCameras();
  }, [selectedParkingLot, userId, parkingLots]);

  const handleCapture = async () => {
    if (!selectedCamera) {
      setError('Please select a camera first');
      return;
    }

    const camera = cameras.find(c => c.id === selectedCamera);
    if (!camera) {
      setError('Selected camera not found');
      return;
    }

    setIsCapturing(true);
    setError('');

    try {
      // Fetch image from /capture endpoint
      const captureUrl = `${camera.ipAddress}/capture`;
      console.log('📸 Capturing from:', captureUrl);

      const response = await fetch(captureUrl);
      if (!response.ok) {
        throw new Error(`Failed to capture: ${response.statusText}`);
      }

      // Get the image blob
      const blob = await response.blob();
      const imageUrl = URL.createObjectURL(blob);
      
      console.log('✅ Image captured successfully');
      onCapture(imageUrl);
    } catch (err) {
      console.error('Capture error:', err);
      setError(err instanceof Error ? err.message : 'Failed to capture image');
    } finally {
      setIsCapturing(false);
    }
  };

  return (
    <div className="bg-white p-4 rounded-lg shadow border border-gray-200 mb-4">
      <div className="space-y-4">
        {/* Header */}
        <div className="flex items-center gap-2">
          <span className="text-lg font-bold text-gray-800">📸 Camera Capture</span>
        </div>

        {/* Parking Lot Selector */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Parking Lot
          </label>
          <select
            value={selectedParkingLot}
            onChange={(e) => setSelectedParkingLot(e.target.value)}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          >
            <option value="">Select parking lot</option>
            {parkingLots.map(lot => (
              <option key={lot.id} value={lot.id}>
                {lot.name}
              </option>
            ))}
          </select>
        </div>

        {/* Camera Selector */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Camera
          </label>
          <select
            value={selectedCamera}
            onChange={(e) => setSelectedCamera(e.target.value)}
            disabled={cameras.length === 0}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent disabled:bg-gray-100 disabled:cursor-not-allowed"
          >
            <option value="">Select camera</option>
            {cameras.map(camera => (
              <option key={camera.id} value={camera.id}>
                {camera.name} ({camera.ipAddress})
              </option>
            ))}
          </select>
        </div>

        {/* Capture Button */}
        <button
          onClick={handleCapture}
          disabled={!selectedCamera || isCapturing}
          className="w-full px-4 py-3 bg-blue-600 text-white rounded-lg font-medium hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors flex items-center justify-center gap-2"
        >
          {isCapturing ? (
            <>
              <span className="animate-spin">⏳</span>
              Capturing...
            </>
          ) : (
            <>
              📸 Capture Image
            </>
          )}
        </button>

        {/* Error Message */}
        {error && (
          <div className="p-3 bg-red-50 text-red-700 rounded-lg text-sm">
            ❌ {error}
          </div>
        )}

        {/* Info Message */}
        {cameras.length === 0 && selectedParkingLot && (
          <div className="p-3 bg-yellow-50 text-yellow-700 rounded-lg text-sm">
            ℹ️ No cameras found for this parking lot. Please add cameras first.
          </div>
        )}
      </div>
    </div>
  );
}
