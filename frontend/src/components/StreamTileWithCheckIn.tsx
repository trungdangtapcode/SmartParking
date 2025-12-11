import { useEffect, useRef, useState } from 'react';
import { API_CONFIG } from '../config/api';
import { performVehicleCheckIn, performVehicleCheckInFromVideoFile } from '../services/checkInService';

const API_BASE = API_CONFIG.baseURL;

interface StreamTileWithCheckInProps {
  streamUrl: string;
  label: string;
  sourceType: 'esp32' | 'video' | 'mock';
  isStreaming: boolean;
  parkingId?: string;
  cameraId?: string;
  ownerId?: string;
  onCheckInSuccess?: (vehicleId: string, licensePlate: string) => void;
}

/**
 * Get snapshot from video file stream
 */
async function getSnapshotFromStream(
  streamUrl: string,
  sourceType: 'esp32' | 'video' | 'mock'
): Promise<string | null> {
  try {
    if (sourceType === 'video') {
      // Extract filename from streamUrl
      const urlParams = new URLSearchParams(streamUrl.split('?')[1] || '');
      const file = urlParams.get('file');
      
      if (!file) {
        throw new Error('Cannot extract filename from stream URL');
      }
      
      // Get snapshot from backend
      const response = await fetch(
        `${API_BASE}${API_CONFIG.endpoints.streamSnapshot}?mode=video_file&file=${encodeURIComponent(file)}`
      );
      
      if (!response.ok) {
        throw new Error(`Snapshot failed: ${response.status}`);
      }
      
      const data = await response.json();
      return data.imageData || null;
    }
    
    // For ESP32 or mock, try to fetch current frame
    const response = await fetch(streamUrl, { cache: 'no-cache' });
    if (!response.ok) {
      return null;
    }
    
    const blob = await response.blob();
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onloadend = () => resolve(reader.result as string);
      reader.onerror = reject;
      reader.readAsDataURL(blob);
    });
  } catch (error) {
    console.error('Error getting snapshot:', error);
    return null;
  }
}

export function StreamTileWithCheckIn({
  streamUrl,
  label,
  sourceType,
  isStreaming,
  parkingId,
  cameraId,
  ownerId,
  onCheckInSuccess,
}: StreamTileWithCheckInProps) {
  const [isCheckingIn, setIsCheckingIn] = useState(false);
  const [checkInResult, setCheckInResult] = useState<{
    vehicleId?: string;
    licensePlate?: string;
    error?: string;
  } | null>(null);
  const streamStartRef = useRef<number | null>(null);

  useEffect(() => {
    if (isStreaming && streamStartRef.current === null) {
      streamStartRef.current = Date.now();
    }
    if (!isStreaming) {
      streamStartRef.current = null;
    }
  }, [isStreaming]);

  const handleCheckIn = async () => {
    if (!parkingId || !cameraId || !ownerId) {
      alert('Vui lòng nhập Parking ID và Camera ID trước khi check-in');
      return;
    }

    if (!isStreaming) {
      alert('Vui lòng bắt đầu stream trước khi check-in');
      return;
    }

    setIsCheckingIn(true);
    setCheckInResult(null);

    try {
      // Nếu là video file: dùng backend lấy frame theo timestamp (tạm thời không gửi timeMs)
      if (sourceType === 'video') {
        console.log('🎞️ Video mode: calling backend plate-detect from video file...');
        // Extract filename
        const urlParams = new URLSearchParams(streamUrl.split('?')[1] || '');
        const file = urlParams.get('file');
        if (!file) {
          throw new Error('Không tìm thấy file trong stream URL');
        }
        // Ước lượng thời gian phát dựa trên thời điểm start stream (đơn giản)
        const timeMs = streamStartRef.current ? Date.now() - streamStartRef.current : undefined;
        const result = await performVehicleCheckInFromVideoFile(
          file,
          parkingId,
          cameraId,
          ownerId,
          timeMs
        );
        if (result.success && result.vehicleId && result.licensePlate) {
          setCheckInResult({
            vehicleId: result.vehicleId,
            licensePlate: result.licensePlate,
          });
          
          if (onCheckInSuccess) {
            onCheckInSuccess(result.vehicleId, result.licensePlate);
          }
          
          alert(`✅ Check-in thành công!\nBiển số: ${result.licensePlate}\nVehicle ID: ${result.vehicleId}`);
        } else {
          setCheckInResult({ error: result.error || 'Check-in failed' });
          alert(`❌ Check-in thất bại: ${result.error || 'Unknown error'}`);
        }
        return;
      }

      // Mặc định: ESP32/mock → lấy snapshot rồi gửi ảnh
      console.log('📸 Getting snapshot from stream...');
      const imageData = await getSnapshotFromStream(streamUrl, sourceType);

      if (!imageData) {
        throw new Error('Không thể capture frame từ stream. Vui lòng thử lại.');
      }

      console.log('🔍 Starting check-in with OCR...');
      
      const result = await performVehicleCheckIn(
        imageData,
        parkingId,
        cameraId,
        ownerId
      );

      if (result.success && result.vehicleId && result.licensePlate) {
        setCheckInResult({
          vehicleId: result.vehicleId,
          licensePlate: result.licensePlate,
        });
        
        if (onCheckInSuccess) {
          onCheckInSuccess(result.vehicleId, result.licensePlate);
        }
        
        alert(`✅ Check-in thành công!\nBiển số: ${result.licensePlate}\nVehicle ID: ${result.vehicleId}`);
      } else {
        setCheckInResult({ error: result.error || 'Check-in failed' });
        alert(`❌ Check-in thất bại: ${result.error || 'Unknown error'}`);
      }
    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : 'Unknown error';
      setCheckInResult({ error: errorMsg });
      alert(`❌ Lỗi: ${errorMsg}`);
    } finally {
      setIsCheckingIn(false);
    }
  };

  return (
    <div className="space-y-2">
      {/* Check-in Button */}
      <button
        onClick={handleCheckIn}
        disabled={isCheckingIn || !isStreaming || !parkingId || !cameraId}
        className={`w-full px-4 py-2 rounded-lg font-semibold transition-all ${
          isCheckingIn || !isStreaming || !parkingId || !cameraId
            ? 'bg-gray-300 text-gray-500 cursor-not-allowed'
            : 'bg-gradient-to-r from-blue-500 to-indigo-600 text-white hover:shadow-lg hover:scale-105'
        }`}
        title={
          !parkingId || !cameraId
            ? 'Vui lòng nhập Parking ID và Camera ID'
            : !isStreaming
            ? 'Vui lòng bắt đầu stream trước'
            : 'Check-in xe và OCR biển số'
        }
      >
        {isCheckingIn ? (
          <>
            <span className="inline-block animate-spin mr-2">⏳</span>
            Đang check-in...
          </>
        ) : (
          <>
            <span className="mr-2">🚗</span>
            Check-in
          </>
        )}
      </button>

      {/* Check-in Result */}
      {checkInResult && (
        <div
          className={`p-3 rounded-lg text-sm ${
            checkInResult.error
              ? 'bg-red-50 text-red-700 border border-red-200'
              : 'bg-green-50 text-green-700 border border-green-200'
          }`}
        >
          {checkInResult.error ? (
            <div>
              <div className="font-semibold mb-1">❌ Lỗi:</div>
              <div className="text-xs">{checkInResult.error}</div>
            </div>
          ) : (
            <div>
              <div className="font-semibold mb-1">✅ Check-in thành công!</div>
              <div className="text-xs space-y-1">
                <div>Biển số: <strong>{checkInResult.licensePlate}</strong></div>
                <div>Vehicle ID: <strong className="font-mono text-xs">{checkInResult.vehicleId}</strong></div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

