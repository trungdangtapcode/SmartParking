// API Configuration - Using environment variables
const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || 'http://localhost:8069';

export const API_CONFIG = {
    // FastAPI backend
    baseURL: BACKEND_URL,
    
    // ESP32 stream endpoint (via FastAPI proxy)
    streamURL: `${BACKEND_URL}/stream`,
    
    // API endpoints
    endpoints: {
      health: '/health',
      plateDetect: '/api/plate-detect',
      objectTracking: '/api/object-tracking',
      esp32Snapshot: '/api/esp32/snapshot',
      testESP32: '/test/esp32',
      vehicleCheckIn: '/api/vehicle/checkin',
      trackingLive: '/api/tracking/live',
      parkingSpaceUpdate: '/api/parking-space/update',
      streamSnapshot: '/api/stream/snapshot',
    }
  };