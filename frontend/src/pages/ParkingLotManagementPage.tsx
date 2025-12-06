import { useEffect, useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { ParkingLotDashboard } from '../components/ParkingLotDashboard';
import {
  createParkingLot,
  getParkingLotsByOwner,
  updateParkingLot,
  deleteParkingLot,
} from '../services/parkingLotService';
import type { ParkingLot, CreateParkingLotInput } from '../types/parkingLot.types';

export function ParkingLotManagementPage() {
  const { user, role } = useAuth();
  const [parkingLots, setParkingLots] = useState<ParkingLot[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedLot, setSelectedLot] = useState<string | null>(null);
  
  // Create/Edit Form State
  const [showForm, setShowForm] = useState(false);
  const [formMode, setFormMode] = useState<'create' | 'edit'>('create');
  const [formData, setFormData] = useState<Partial<CreateParkingLotInput>>({
    id: '',
    name: '',
    address: '',
    pricePerHour: undefined,
    openTime: '00:00',
    closeTime: '23:59',
    description: '',
  });

  useEffect(() => {
    loadParkingLots();
  }, [user]);

  const loadParkingLots = async () => {
    if (!user) {
      setLoading(false);
      return;
    }

    try {
      const lots = await getParkingLotsByOwner(user.uid);
      setParkingLots(lots);
      
      // Auto-select first lot if exists
      if (lots.length > 0 && !selectedLot) {
        setSelectedLot(lots[0].id);
      }
    } catch (error) {
      console.error('Error loading parking lots:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleCreateLot = async () => {
    if (!user || !formData.id || !formData.name || !formData.address) {
      alert('Vui lòng điền đầy đủ thông tin bắt buộc!');
      return;
    }

    const input: CreateParkingLotInput = {
      id: formData.id.toUpperCase().trim(),
      name: formData.name.trim(),
      address: formData.address.trim(),
      ownerId: user.uid,
      pricePerHour: formData.pricePerHour,
      openTime: formData.openTime,
      closeTime: formData.closeTime,
      description: formData.description,
    };

    const result = await createParkingLot(input);
    
    if (result.success) {
      alert(`✅ Đã tạo bãi đỗ xe: ${input.id}`);
      setShowForm(false);
      resetForm();
      loadParkingLots();
    } else {
      alert(`❌ Lỗi: ${result.error}`);
    }
  };

  const handleUpdateLot = async () => {
    if (!selectedLot) return;

    const result = await updateParkingLot(selectedLot, {
      name: formData.name,
      address: formData.address,
      pricePerHour: formData.pricePerHour,
      openTime: formData.openTime,
      closeTime: formData.closeTime,
      description: formData.description,
    });

    if (result.success) {
      alert(`✅ Đã cập nhật bãi đỗ xe!`);
      setShowForm(false);
      resetForm();
      loadParkingLots();
    } else {
      alert(`❌ Lỗi: ${result.error}`);
    }
  };

  const handleDeleteLot = async (lotId: string) => {
    if (!confirm(`Xác nhận xóa bãi đỗ xe "${lotId}"?\n\nChú ý: Dữ liệu cameras và spaces vẫn được giữ lại.`)) {
      return;
    }

    const result = await deleteParkingLot(lotId);
    
    if (result.success) {
      alert(`✅ Đã xóa bãi đỗ xe: ${lotId}`);
      if (selectedLot === lotId) {
        setSelectedLot(null);
      }
      loadParkingLots();
    } else {
      alert(`❌ Lỗi: ${result.error}`);
    }
  };

  const openCreateForm = () => {
    setFormMode('create');
    resetForm();
    setShowForm(true);
  };

  const openEditForm = (lot: ParkingLot) => {
    setFormMode('edit');
    setFormData({
      id: lot.id,
      name: lot.name,
      address: lot.address,
      pricePerHour: lot.pricePerHour,
      openTime: lot.openTime,
      closeTime: lot.closeTime,
      description: lot.description,
    });
    setShowForm(true);
  };

  const resetForm = () => {
    setFormData({
      id: '',
      name: '',
      address: '',
      pricePerHour: undefined,
      openTime: '00:00',
      closeTime: '23:59',
      description: '',
    });
  };

  if (!user || role !== 'admin') {
    return (
      <div className="min-h-screen bg-gradient-to-b from-strawberry-50 via-white to-matcha-50 p-6">
        <div className="max-w-4xl mx-auto">
          <div className="bg-yellow-50 border border-yellow-200 rounded-xl p-6 text-center">
            <div className="text-4xl mb-3">⚠️</div>
            <div className="text-lg font-semibold text-gray-800">Yêu cầu quyền Admin</div>
            <div className="text-sm text-gray-600 mt-2">
              Trang này chỉ dành cho quản trị viên. Role hiện tại: {role || 'none'}
            </div>
          </div>
        </div>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-b from-strawberry-50 via-white to-matcha-50 p-6 flex items-center justify-center">
        <div className="text-center">
          <div className="text-5xl mb-4">⏳</div>
          <div className="text-lg text-gray-600">Đang tải dữ liệu...</div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-b from-strawberry-50 via-white to-matcha-50 p-6">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="mb-6">
          <h1 className="text-4xl font-bold text-strawberry-900 mb-2">
            🏢 Quản lý Bãi đỗ xe
          </h1>
          <p className="text-gray-600">
            Quản lý thông tin và theo dõi trạng thái các bãi đỗ xe
          </p>
        </div>

        {/* Parking Lots List */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-6">
          {/* Left Sidebar - Parking Lots */}
          <div className="lg:col-span-1">
            <div className="bg-white rounded-xl shadow-lg border border-gray-200 p-6">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-xl font-semibold text-gray-800">
                  Danh sách bãi ({parkingLots.length})
                </h2>
                <button
                  onClick={openCreateForm}
                  className="px-3 py-2 bg-gradient-to-r from-strawberry-500 to-matcha-500 text-white rounded-lg hover:shadow-lg transition text-sm font-semibold"
                >
                  ➕ Tạo mới
                </button>
              </div>

              {parkingLots.length === 0 ? (
                <div className="text-center py-8">
                  <div className="text-4xl mb-3">🅿️</div>
                  <div className="text-gray-600 text-sm">Chưa có bãi đỗ xe nào</div>
                  <button
                    onClick={openCreateForm}
                    className="mt-4 text-strawberry-600 hover:underline text-sm font-medium"
                  >
                    Tạo bãi đầu tiên →
                  </button>
                </div>
              ) : (
                <div className="space-y-3">
                  {parkingLots.map((lot) => (
                    <div
                      key={lot.id}
                      className={`border-2 rounded-lg p-4 cursor-pointer transition ${
                        selectedLot === lot.id
                          ? 'border-strawberry-500 bg-strawberry-50'
                          : 'border-gray-200 hover:border-gray-300'
                      }`}
                      onClick={() => setSelectedLot(lot.id)}
                    >
                      <div className="flex items-start justify-between">
                        <div className="flex-1 min-w-0">
                          <div className="font-semibold text-gray-800 truncate">{lot.name}</div>
                          <div className="text-xs text-gray-500 mt-1">ID: {lot.id}</div>
                          <div className="flex items-center gap-3 mt-2 text-xs">
                            <span className="text-green-600 font-semibold">
                              ✅ {lot.availableSpaces}
                            </span>
                            <span className="text-red-600 font-semibold">
                              🚗 {lot.occupiedSpaces}
                            </span>
                            <span className="text-gray-600">
                              📹 {lot.cameras.length}
                            </span>
                          </div>
                        </div>
                        <div className="flex gap-1 ml-2">
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              openEditForm(lot);
                            }}
                            className="p-1 hover:bg-gray-200 rounded transition"
                            title="Chỉnh sửa"
                          >
                            ✏️
                          </button>
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              handleDeleteLot(lot.id);
                            }}
                            className="p-1 hover:bg-red-100 rounded transition"
                            title="Xóa"
                          >
                            🗑️
                          </button>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Right Content - Dashboard */}
          <div className="lg:col-span-2">
            {selectedLot ? (
              <ParkingLotDashboard parkingId={selectedLot} showCameras={true} ownerId={user?.uid} />
            ) : (
              <div className="bg-white rounded-xl shadow-lg border border-gray-200 p-12 text-center">
                <div className="text-6xl mb-4">🅿️</div>
                <div className="text-xl font-semibold text-gray-700 mb-2">
                  Chọn một bãi đỗ xe
                </div>
                <div className="text-gray-500">
                  Chọn bãi từ danh sách bên trái để xem chi tiết
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Create/Edit Form Modal */}
        {showForm && (
          <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
            <div className="bg-white rounded-xl shadow-2xl max-w-2xl w-full max-h-[90vh] overflow-y-auto">
              <div className="p-6 border-b border-gray-200 bg-gradient-to-r from-strawberry-50 to-matcha-50">
                <h3 className="text-2xl font-bold text-gray-900">
                  {formMode === 'create' ? '➕ Tạo bãi đỗ xe mới' : '✏️ Chỉnh sửa bãi đỗ xe'}
                </h3>
              </div>

              <div className="p-6 space-y-4">
                {/* ID (only for create) */}
                {formMode === 'create' && (
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      ID Bãi đỗ xe <span className="text-red-500">*</span>
                    </label>
                    <input
                      type="text"
                      value={formData.id}
                      onChange={(e) => setFormData({ ...formData, id: e.target.value.toUpperCase() })}
                      placeholder="VD: PARKING_A"
                      className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-strawberry-500 focus:border-strawberry-500"
                    />
                    <p className="text-xs text-gray-500 mt-1">Chỉ dùng chữ cái, số và gạch dưới</p>
                  </div>
                )}

                {/* Name */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Tên bãi đỗ <span className="text-red-500">*</span>
                  </label>
                  <input
                    type="text"
                    value={formData.name}
                    onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                    placeholder="VD: Bãi đỗ xe tòa nhà A"
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-strawberry-500 focus:border-strawberry-500"
                  />
                </div>

                {/* Address */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Địa chỉ <span className="text-red-500">*</span>
                  </label>
                  <input
                    type="text"
                    value={formData.address}
                    onChange={(e) => setFormData({ ...formData, address: e.target.value })}
                    placeholder="VD: 123 Nguyễn Văn A, Quận 1, TP.HCM"
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-strawberry-500 focus:border-strawberry-500"
                  />
                </div>

                {/* Price */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Giá đỗ xe (VND/giờ)
                  </label>
                  <input
                    type="number"
                    value={formData.pricePerHour || ''}
                    onChange={(e) => setFormData({ ...formData, pricePerHour: e.target.value ? Number(e.target.value) : undefined })}
                    placeholder="VD: 15000"
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-strawberry-500 focus:border-strawberry-500"
                  />
                </div>

                {/* Hours */}
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">Giờ mở cửa</label>
                    <input
                      type="time"
                      value={formData.openTime}
                      onChange={(e) => setFormData({ ...formData, openTime: e.target.value })}
                      className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-strawberry-500 focus:border-strawberry-500"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">Giờ đóng cửa</label>
                    <input
                      type="time"
                      value={formData.closeTime}
                      onChange={(e) => setFormData({ ...formData, closeTime: e.target.value })}
                      className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-strawberry-500 focus:border-strawberry-500"
                    />
                  </div>
                </div>

                {/* Description */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">Mô tả</label>
                  <textarea
                    value={formData.description}
                    onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                    placeholder="Mô tả thêm về bãi đỗ xe..."
                    rows={3}
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-strawberry-500 focus:border-strawberry-500"
                  />
                </div>
              </div>

              <div className="p-6 border-t border-gray-200 flex gap-3 justify-end">
                <button
                  onClick={() => {
                    setShowForm(false);
                    resetForm();
                  }}
                  className="px-6 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 transition"
                >
                  Hủy
                </button>
                <button
                  onClick={formMode === 'create' ? handleCreateLot : handleUpdateLot}
                  className="px-6 py-2 bg-gradient-to-r from-strawberry-500 to-matcha-500 text-white rounded-lg hover:shadow-lg transition font-semibold"
                >
                  {formMode === 'create' ? 'Tạo bãi đỗ xe' : 'Lưu thay đổi'}
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

