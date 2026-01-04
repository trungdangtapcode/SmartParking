import { useEffect, useState } from 'react';
import { onSnapshot, doc } from 'firebase/firestore';
import { db } from '../config/firebase';
import type { ParkingLot } from '../types/parkingLot.types';
import { CameraDetectionModal } from './CameraDetectionModal';

interface ParkingLotDashboardProps {
  parkingId: string;
  showCameras?: boolean;
  ownerId?: string; // For camera detection modal
}

export function ParkingLotDashboard({ parkingId, showCameras = true, ownerId }: ParkingLotDashboardProps) {
  const [parkingLot, setParkingLot] = useState<ParkingLot | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedCamera, setSelectedCamera] = useState<string | null>(null);

  useEffect(() => {
    if (!db || !parkingId) {
      setError('Invalid parking ID or database not initialized');
      setLoading(false);
      return;
    }

    // Real-time listener
    const unsubscribe = onSnapshot(
      doc(db, 'parkingLots', parkingId),
      (snapshot) => {
        if (snapshot.exists()) {
          setParkingLot(snapshot.data() as ParkingLot);
          setError(null);
        } else {
          setError('Parking lot not found');
        }
        setLoading(false);
      },
      (err) => {
        console.error('Error listening to parking lot:', err);
        setError(err.message);
        setLoading(false);
      }
    );

    return () => unsubscribe();
  }, [parkingId]);

  if (loading) {
    return (
      <div className="flex items-center justify-center p-8">
        <div className="text-center">
          <div className="text-4xl mb-2">⏳</div>
          <div className="text-gray-600">Loading parking lot data...</div>
        </div>
      </div>
    );
  }

  if (error || !parkingLot) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-lg p-6 text-center">
        <div className="text-4xl mb-2">⚠️</div>
        <div className="text-red-800 font-semibold">Error</div>
        <div className="text-red-600 text-sm mt-1">{error || 'Parking lot not found'}</div>
      </div>
    );
  }

  const occupancyRate = parkingLot.totalSpaces > 0
    ? (parkingLot.occupiedSpaces / parkingLot.totalSpaces) * 100
    : 0;

  const getOccupancyColor = () => {
    if (occupancyRate >= 90) return 'text-red-600';
    if (occupancyRate >= 70) return 'text-orange-600';
    if (occupancyRate >= 50) return 'text-yellow-600';
    return 'text-green-600';
  };

  const getAvailableColor = () => {
    if (parkingLot.availableSpaces === 0) return 'bg-red-100 text-red-800 border-red-300';
    if (parkingLot.availableSpaces <= 5) return 'bg-orange-100 text-orange-800 border-orange-300';
    return 'bg-green-100 text-green-800 border-green-300';
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="bg-gradient-to-r from-strawberry-50 to-matcha-50 rounded-xl p-6 border border-gray-200">
        <div className="flex items-start justify-between">
          <div className="flex-1">
            <div className="flex items-center gap-3 mb-2">
              <span className="text-4xl">🚗</span>
              <div>
                <h2 className="text-2xl font-bold text-gray-900">{parkingLot.name}</h2>
                <p className="text-sm text-gray-600">{parkingLot.address}</p>
              </div>
            </div>
            <div className="flex items-center gap-2 mt-3">
              <span className={`px-3 py-1 rounded-full text-xs font-semibold ${
                parkingLot.status === 'active'
                  ? 'bg-green-100 text-green-700'
                  : 'bg-gray-100 text-gray-600'
              }`}>
                {parkingLot.status === 'active' ? '🟢 Active' : '⚪ Inactive'}
              </span>
              <span className="text-xs text-gray-500">ID: {parkingLot.id}</span>
            </div>
          </div>
          
          {parkingLot.pricePerHour && (
            <div className="text-right">
              <div className="text-sm text-gray-600">Giá đỗ xe</div>
              <div className="text-xl font-bold text-strawberry-600">
                {parkingLot.pricePerHour.toLocaleString()}₫/h
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Total Spaces */}
        <div className="bg-white rounded-xl shadow-md border-2 border-blue-200 p-6">
          <div className="flex items-center justify-between mb-2">
            <div className="text-sm font-medium text-gray-600">Tổng số chỗ</div>
            <span className="text-2xl">🅿️</span>
          </div>
          <div className="text-3xl font-bold text-blue-600">{parkingLot.totalSpaces}</div>
          <div className="text-xs text-gray-500 mt-1">Total slots</div>
        </div>

        {/* Available Spaces */}
        <div className={`rounded-xl shadow-md border-2 p-6 ${getAvailableColor()}`}>
          <div className="flex items-center justify-between mb-2">
            <div className="text-sm font-medium">Chỗ trống</div>
            <span className="text-2xl">✅</span>
          </div>
          <div className="text-3xl font-bold">{parkingLot.availableSpaces}</div>
          <div className="text-xs mt-1 opacity-75">Available</div>
        </div>

        {/* Occupied Spaces */}
        <div className="bg-white rounded-xl shadow-md border-2 border-red-200 p-6">
          <div className="flex items-center justify-between mb-2">
            <div className="text-sm font-medium text-gray-600">Đã đỗ</div>
            <span className="text-2xl">🚗</span>
          </div>
          <div className="text-3xl font-bold text-red-600">{parkingLot.occupiedSpaces}</div>
          <div className="text-xs text-gray-500 mt-1">Occupied</div>
        </div>

        {/* Occupancy Rate */}
        <div className="bg-white rounded-xl shadow-md border-2 border-purple-200 p-6">
          <div className="flex items-center justify-between mb-2">
            <div className="text-sm font-medium text-gray-600">Tỷ lệ lấp đầy</div>
            <span className="text-2xl">📊</span>
          </div>
          <div className={`text-3xl font-bold ${getOccupancyColor()}`}>
            {occupancyRate.toFixed(1)}%
          </div>
          <div className="text-xs text-gray-500 mt-1">Occupancy</div>
        </div>
      </div>

      {/* Progress Bar */}
      <div className="bg-white rounded-xl shadow-md border border-gray-200 p-6">
        <div className="flex items-center justify-between mb-3">
          <div className="text-sm font-semibold text-gray-700">Trạng thái bãi đỗ</div>
          <div className="text-xs text-gray-500">
            {parkingLot.occupiedSpaces} / {parkingLot.totalSpaces} chỗ
          </div>
        </div>
        <div className="w-full bg-gray-200 rounded-full h-6 overflow-hidden">
          <div
            className="h-full bg-gradient-to-r from-red-500 to-red-600 transition-all duration-300 flex items-center justify-end px-2"
            style={{ width: `${occupancyRate}%` }}
          >
            {occupancyRate > 10 && (
              <span className="text-white text-xs font-bold">{occupancyRate.toFixed(0)}%</span>
            )}
          </div>
        </div>
        <div className="flex justify-between mt-2 text-xs text-gray-500">
          <span>0%</span>
          <span>50%</span>
          <span>100%</span>
        </div>
      </div>

      {/* Cameras */}
      {showCameras && parkingLot.cameras.length > 0 && (
        <div className="bg-white rounded-xl shadow-md border border-gray-200 p-6">
          <div className="flex items-center gap-2 mb-4">
            <span className="text-xl">📹</span>
            <h3 className="text-lg font-semibold text-gray-800">
              Cameras ({parkingLot.cameras.length})
            </h3>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
            {parkingLot.cameras.map((cameraId) => (
              <button
                key={cameraId}
                onClick={() => setSelectedCamera(cameraId)}
                className="bg-gradient-to-br from-blue-50 to-purple-50 border-2 border-blue-200 rounded-lg p-4 hover:border-blue-400 hover:shadow-lg transition text-left"
              >
                <div className="flex items-center gap-2 mb-2">
                  <span className="text-2xl">📹</span>
                  <div className="text-sm font-bold text-gray-800">{cameraId}</div>
                </div>
                <div className="text-xs text-green-600 font-semibold">🟢 Active</div>
                <div className="text-xs text-blue-600 mt-1">Click để xem detection →</div>
              </button>
            ))}
          </div>
          <div className="mt-4 p-3 bg-blue-50 border border-blue-200 rounded-lg text-xs text-blue-800">
            💡 <strong>Tip:</strong> Cameras này đang được host tại{' '}
            <a href="/stream/host-multi" className="underline font-semibold hover:text-blue-900">
              /stream/host-multi
            </a>
            . Xem tất cả live streams tại{' '}
            <a href="/stream/view-multi" className="underline font-semibold hover:text-blue-900">
              /stream/view-multi
            </a>
          </div>
        </div>
      )}

      {/* No Cameras Info */}
      {showCameras && parkingLot.cameras.length === 0 && (
        <div className="bg-yellow-50 border border-yellow-200 rounded-xl p-6">
          <div className="flex items-start gap-3">
            <span className="text-3xl">📹</span>
            <div>
              <h3 className="text-lg font-semibold text-gray-800 mb-2">Chưa có camera nào</h3>
              <p className="text-sm text-gray-700 mb-3">
                Bãi đỗ xe này chưa có camera được host. Để thêm camera:
              </p>
              <ol className="space-y-2 text-sm text-gray-700">
                <li className="flex items-start gap-2">
                  <span className="font-bold text-yellow-700">1.</span>
                  <div>
                    Đến{' '}
                    <a href="/stream/host-multi" className="text-blue-600 hover:underline font-semibold">
                      /stream/host-multi
                    </a>
                  </div>
                </li>
                <li className="flex items-start gap-2">
                  <span className="font-bold text-yellow-700">2.</span>
                  <div>
                    Nhập Parking Lot ID: <code className="bg-yellow-100 px-2 py-0.5 rounded font-mono">{parkingLot.id}</code>
                  </div>
                </li>
                <li className="flex items-start gap-2">
                  <span className="font-bold text-yellow-700">3.</span>
                  <div>
                    Nhập Camera ID (VD: <code className="bg-yellow-100 px-2 py-0.5 rounded font-mono">CAM1</code>,{' '}
                    <code className="bg-yellow-100 px-2 py-0.5 rounded font-mono">ENTRANCE</code>)
                  </div>
                </li>
                <li className="flex items-start gap-2">
                  <span className="font-bold text-yellow-700">4.</span>
                  <div>Click "➕ Thêm host", chọn video file, và click "📡 Start Stream"</div>
                </li>
              </ol>
            </div>
          </div>
        </div>
      )}

      {/* Camera Detection Modal */}
      {selectedCamera && ownerId && (
        <CameraDetectionModal
          cameraId={selectedCamera}
          ownerId={ownerId}
          onClose={() => setSelectedCamera(null)}
        />
      )}

      {/* Additional Info */}
      {(parkingLot.openTime || parkingLot.closeTime || parkingLot.description) && (
        <div className="bg-white rounded-xl shadow-md border border-gray-200 p-6">
          <div className="flex items-center gap-2 mb-4">
            <span className="text-xl">ℹ️</span>
            <h3 className="text-lg font-semibold text-gray-800">Thông tin</h3>
          </div>
          <div className="space-y-2 text-sm">
            {(parkingLot.openTime || parkingLot.closeTime) && (
              <div className="flex items-center gap-2">
                <span className="text-gray-600">🕐 Giờ mở cửa:</span>
                <span className="font-medium">
                  {parkingLot.openTime || '00:00'} - {parkingLot.closeTime || '23:59'}
                </span>
              </div>
            )}
            {parkingLot.description && (
              <div>
                <span className="text-gray-600">📝 Mô tả:</span>
                <p className="text-gray-800 mt-1">{parkingLot.description}</p>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Last Updated */}
      <div className="text-center text-xs text-gray-500">
        Cập nhật lần cuối: {parkingLot.updatedAt.toDate().toLocaleString('vi-VN')}
      </div>
    </div>
  );
}

