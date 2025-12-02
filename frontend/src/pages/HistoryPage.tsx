import { useEffect, useState, useRef, useMemo } from 'react';
import { format } from 'date-fns';
import { fetchLatestDetections, updateDetectionRecord, deleteDetection } from '../services/detectionService';
import { ParkingMap2D } from '../components/ParkingMap2D';
import { aiDetection } from '../services/ai/aiDetection';
import { useAuth } from '../context/AuthContext';

interface ParkingSpace {
  id: string;
  bbox: [number, number, number, number];
  confidence: number;
}

interface DetectionRecord {
  id: string; // cameraId
  timestamp: Date;
  vehicleCount: number;
  cameraId: string;
  parking?: string;
  parkingId?: string;
  ownerId?: string;
  inputImageUrl?: string;
  spaces?: ParkingSpace[];
  vehicles?: Array<{
    type?: string;
    class?: string;
    confidence?: number;
    score?: number;
    bbox?: [number, number, number, number];
  }>;
  updateCount?: number;
}

export function HistoryPage() {
  const { user } = useAuth();
  const ownerId = user?.uid ?? null;
  const [records, setRecords] = useState<DetectionRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [editingCameraId, setEditingCameraId] = useState<string | null>(null);
  const [editingDocId, setEditingDocId] = useState<string | null>(null);
  const [editingSpaces, setEditingSpaces] = useState<ParkingSpace[]>([]);
  const [editingImageUrl, setEditingImageUrl] = useState<string | undefined>(undefined);
  const [isSaving, setIsSaving] = useState(false);
  const [zoom, setZoom] = useState(1);
  const [selectedSpaceId, setSelectedSpaceId] = useState<string | null>(null);
  const imageRef = useRef<HTMLImageElement | null>(null);
  const [imageDimensions, setImageDimensions] = useState<{ [key: string]: { width: number; height: number } }>({});
  
  // Sort state
  const [sortBy, setSortBy] = useState<'time' | 'parkingId' | 'cameraId' | 'vehicleCount' | 'updateCount'>('time');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc');

  useEffect(() => {
    const fetchHistory = async () => {
      if (!ownerId) {
        setRecords([]);
        setLoading(false);
        return;
      }
      try {
        setLoading(true);
        const result = await fetchLatestDetections({ ownerId });
        if (result.success && result.data) {
          try {
            const data = result.data.map(record => {
              try {
                // Convert vehicles to spaces if spaces not available (for old data)
                const spaces = record.spaces || (record.vehicles?.map((v, i) => ({
                  id: `space-${i}`,
                  bbox: (v as any).bbox || [0, 0, 0, 0],
                  confidence: (v as any).confidence || (v as any).score || 0
                })) || []);
                
                // Handle timestamp conversion
                let timestamp: Date;
                const ts = record.timestamp as any;
                if (ts && typeof ts === 'object' && typeof ts.toDate === 'function') {
                  timestamp = ts.toDate();
                } else if (ts instanceof Date) {
                  timestamp = ts;
                } else {
                  timestamp = new Date();
                }
                
                // Nếu URL là blob:... (tạo tạm từ upload), sau khi reload sẽ không còn tồn tại
                // → bỏ qua để tránh lỗi load ảnh
                const safeInputUrl =
                  record.inputImageUrl && record.inputImageUrl.startsWith('blob:')
                    ? undefined
                    : record.inputImageUrl || undefined;

                const processedRecord = {
                  ...record,
                  timestamp,
                  spaces,
                  inputImageUrl: safeInputUrl,
                  vehicles: record.vehicles || [],
                  parking: record.parkingId || undefined,
                  parkingId: record.parkingId,
                } as DetectionRecord;
                
                console.log(`📊 Record ${record.cameraId}:`, {
                  hasInputImage: !!processedRecord.inputImageUrl,
                  inputImageUrl: processedRecord.inputImageUrl,
                  spacesCount: processedRecord.spaces?.length || 0,
                  vehiclesCount: processedRecord.vehicles?.length || 0,
                  parking: processedRecord.parking,
                  rawRecord: record
                });
                
                return processedRecord;
              } catch (recordError) {
                console.error(`Error processing record ${record.cameraId}:`, recordError);
                return null;
              }
            }).filter((r): r is DetectionRecord => r !== null);
            
            // Don't sort here - let useMemo handle it
            setRecords(data);
            console.log(`✅ Loaded ${data.length} camera records`);
          } catch (mapError) {
            console.error('Error mapping records:', mapError);
            setRecords([]);
          }
        } else {
          console.warn('Failed to fetch detections:', result.error);
          setRecords([]);
        }
      } catch (error) {
        console.error('Error fetching history:', error);
        setRecords([]);
      } finally {
        setLoading(false);
      }
    };
    
    fetchHistory();
  }, [ownerId]);

  const handleEdit = (record: DetectionRecord) => {
    setEditingDocId(record.id);
    setEditingCameraId(record.cameraId);
    setEditingSpaces(record.spaces || []);
    setEditingImageUrl(record.inputImageUrl);
    setSelectedSpaceId(null);
    setZoom(1);
    
    // Load image for dimensions
    if (record.inputImageUrl) {
      const img = new Image();
      img.src = record.inputImageUrl;
      img.onload = () => {
        imageRef.current = img;
      };
    }
  };

  const handleCancelEdit = () => {
    setEditingDocId(null);
    setEditingCameraId(null);
    setEditingSpaces([]);
    setEditingImageUrl(undefined);
    setSelectedSpaceId(null);
    setZoom(1);
  };

  const handleSaveEdit = async () => {
    if (!editingDocId) return;
    
    setIsSaving(true);
    try {
      const result = await updateDetectionRecord(editingDocId, editingSpaces, editingImageUrl);
      if (result.success) {
        // Refresh records
        const fetchResult = await fetchLatestDetections({ ownerId: ownerId ?? undefined });
        if (fetchResult.success && fetchResult.data) {
          const data = fetchResult.data.map(record => ({
            ...record,
            timestamp: record.timestamp.toDate(),
            parking: record.parkingId || undefined,
            parkingId: record.parkingId,
          })) as DetectionRecord[];
          
          // Don't sort here - let useMemo handle it
          setRecords(data);
        }
        setEditingDocId(null);
        setEditingCameraId(null);
        setEditingSpaces([]);
        setEditingImageUrl(undefined);
        alert(`✅ Updated ${editingSpaces.length} parking spaces for ${editingCameraId}!`);
      } else {
        alert(`❌ Failed to update: ${result.error || 'Unknown error'}`);
      }
    } catch (error) {
      console.error('Error updating:', error);
      alert('Failed to update. Check console for details.');
    } finally {
      setIsSaving(false);
    }
  };

  const handleDeleteCamera = async (docId: string) => {
    // Find the camera ID for display
    const record = records.find(r => r.id === docId || r.cameraId === docId);
    const cameraId = record?.cameraId || docId;
    
    if (!confirm(`Are you sure you want to delete camera ${cameraId} and all its data?`)) {
      return;
    }
    
    try {
      console.log(`🗑️ Attempting to delete camera: ${cameraId} (docId: ${docId})`);
      // Use docId (record.id) which is the actual Firestore document ID
      const result = await deleteDetection(docId);
      console.log('Delete result:', result);
      
      if (result.success) {
        // Immediately remove from local state using docId
        setRecords(prev => prev.filter(r => r.id !== docId && r.cameraId !== cameraId));
        
        // Then refresh from server to ensure consistency
        const fetchResult = await fetchLatestDetections({ ownerId: ownerId ?? undefined });
        if (fetchResult.success) {
          if (fetchResult.data && fetchResult.data.length > 0) {
            const data = fetchResult.data.map(record => {
              try {
                const spaces = record.spaces || (record.vehicles?.map((v, i) => ({
                  id: `space-${i}`,
                  bbox: (v as any).bbox || [0, 0, 0, 0],
                  confidence: (v as any).confidence || (v as any).score || 0
                })) || []);
                
                let timestamp: Date;
                const ts = record.timestamp as any;
                if (ts && typeof ts === 'object' && typeof ts.toDate === 'function') {
                  timestamp = ts.toDate();
                } else if (ts instanceof Date) {
                  timestamp = ts;
                } else {
                  timestamp = new Date();
                }
                
                return {
                  ...record,
                  timestamp: timestamp,
                  spaces: spaces,
                  inputImageUrl: record.inputImageUrl || undefined,
                  vehicles: record.vehicles || [],
                  parking: record.parkingId || undefined,
                  parkingId: record.parkingId,
                } as DetectionRecord;
              } catch (recordError) {
                console.error(`Error processing record ${record.cameraId}:`, recordError);
                return null;
              }
            }).filter((r): r is DetectionRecord => r !== null);
            
            // Don't sort here - let useMemo handle it
            setRecords(data);
          } else {
            // No records left, set empty array
            setRecords([]);
          }
        }
        alert(`✅ Deleted camera ${cameraId} and all its data!`);
      } else {
        alert(`❌ Failed to delete: ${result.error || 'Unknown error'}`);
      }
    } catch (error) {
      console.error('Error deleting camera:', error);
      alert(`Failed to delete camera. Error: ${error instanceof Error ? error.message : 'Unknown error'}`);
    }
  };

  // Filtered and sorted records
  const filteredRecords = useMemo(() => {
    // Apply sorting
    return [...records].sort((a, b) => {
      let comparison = 0;
      
      switch (sortBy) {
        case 'time':
          comparison = a.timestamp.getTime() - b.timestamp.getTime();
          break;
        case 'parkingId':
          comparison = (a.parkingId || a.parking || '').localeCompare(b.parkingId || b.parking || '');
          break;
        case 'cameraId':
          comparison = a.cameraId.localeCompare(b.cameraId);
          break;
        case 'vehicleCount':
          comparison = a.vehicleCount - b.vehicleCount;
          break;
        case 'updateCount':
          comparison = (a.updateCount || 0) - (b.updateCount || 0);
          break;
      }
      
      return sortOrder === 'asc' ? comparison : -comparison;
    });
  }, [records, sortBy, sortOrder]);

  const handleDetectMore = async () => {
    if (!editingImageUrl) {
      alert('No input image available for detection');
      return;
    }

    try {
      const img = new Image();
      img.src = editingImageUrl;
      await new Promise((resolve, reject) => {
        img.onload = resolve;
        img.onerror = reject;
      });

      const detections = await aiDetection.detectVehicles(img);
      const newSpaces: ParkingSpace[] = detections.map((d, i) => ({
        id: `space-${Date.now()}-${i}`,
        bbox: d.bbox,
        confidence: d.score
      }));

      // Merge with existing spaces (avoid duplicates)
      const existingBboxes = new Set(
        editingSpaces.map(s => `${s.bbox[0]},${s.bbox[1]},${s.bbox[2]},${s.bbox[3]}`)
      );
      const uniqueNewSpaces = newSpaces.filter(s => {
        const key = `${s.bbox[0]},${s.bbox[1]},${s.bbox[2]},${s.bbox[3]}`;
        return !existingBboxes.has(key);
      });

      setEditingSpaces([...editingSpaces, ...uniqueNewSpaces]);
      alert(`✅ Detected ${uniqueNewSpaces.length} new parking spaces!`);
    } catch (error) {
      console.error('Detection error:', error);
      alert('Failed to detect. Check console for details.');
    }
  };

  if (loading) {
    return (
      <div className="p-8 flex items-center justify-center min-h-screen bg-gray-50">
        <div className="text-center">
          <div className="text-4xl mb-4">⏳</div>
          <div className="text-lg text-gray-600">Loading detection history...</div>
        </div>
      </div>
    );
  }

  if (records.length === 0) {
    return (
      <div className="p-8 bg-gray-50 min-h-screen">
        <h1 className="text-3xl font-bold mb-6 text-gray-800">
          📊 Detection History
        </h1>
        <div className="text-center py-12 bg-white rounded-lg border border-gray-200">
          <div className="text-5xl mb-4">📭</div>
          <div className="text-lg text-gray-600">No detection records found</div>
          <div className="text-sm text-gray-500 mt-2">
            Go to Live View to detect and save parking spaces
          </div>
        </div>
      </div>
    );
  }

  // Check if any records have inputImageUrl
  const recordsWithoutImages = records.filter(r => !r.inputImageUrl);
  
  if (recordsWithoutImages.length > 0) {
    console.warn(`⚠️ ${recordsWithoutImages.length} records missing inputImageUrl. Please save again from Live View.`);
  }

  return (
    <div className="p-6 max-w-7xl mx-auto bg-gray-50 min-h-screen">
      <div className="flex justify-between items-center flex-wrap gap-3 mb-6">
        <div>
          <h1 className="text-3xl font-bold text-gray-800">
            📊 Detection History
          </h1>
          <p className="text-sm text-gray-500 mt-1">
            Danh sách các lần phát hiện đã lưu vào hệ thống.
          </p>
        </div>
        <div className="flex gap-2 items-center">
          <span className="text-sm text-gray-600">Sort:</span>
          <select
            value={sortBy}
            onChange={(e) => {
              const newSortBy = e.target.value as typeof sortBy;
              setSortBy(newSortBy);
              // Set default sort order based on field
              if (newSortBy === 'time' || newSortBy === 'vehicleCount' || newSortBy === 'updateCount') {
                setSortOrder('desc');
              } else {
                setSortOrder('asc');
              }
            }}
            className="border border-gray-300 rounded-lg px-3 py-2 text-sm"
          >
            <option value="time">Thời gian</option>
            <option value="parkingId">ID Bãi</option>
            <option value="cameraId">ID Cam</option>
            <option value="vehicleCount">Số lượng</option>
            <option value="updateCount">Số lần cập nhật</option>
          </select>
          <button
            onClick={() => setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc')}
            className="px-3 py-2 border border-gray-300 rounded-lg text-sm hover:bg-gray-50"
            title={`Sort ${sortOrder === 'asc' ? 'Tăng dần' : 'Giảm dần'}`}
          >
            {sortOrder === 'asc' ? '↑' : '↓'}
          </button>
        </div>
      </div>
      
      {/* Warning if records missing images */}
      {recordsWithoutImages.length > 0 && (
        <div className="mb-4 p-4 bg-yellow-50 border border-yellow-200 rounded-lg">
          <div className="flex items-center gap-2">
            <span className="text-xl">⚠️</span>
            <div>
              <div className="font-semibold text-yellow-800">
                Some records are missing images
              </div>
              <div className="text-sm text-yellow-700">
                {recordsWithoutImages.length} record(s) were saved before images were supported. 
                Please go to Live View and save again to see input/output images.
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Edit Mode */}
      {editingCameraId && (
        <div className="mb-6 p-6 bg-blue-50 border-2 border-blue-300 rounded-lg">
          <div className="flex justify-between items-center mb-4">
            <h2 className="text-xl font-bold text-blue-800">
              ✏️ Editing: {editingCameraId}
            </h2>
            <div className="flex gap-2">
              <button
                onClick={handleDetectMore}
                className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition"
              >
                🔍 Detect More Spaces
              </button>
              <button
                onClick={handleSaveEdit}
                disabled={isSaving}
                className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition disabled:bg-gray-400"
              >
                {isSaving ? '⏳ Saving...' : '💾 Save Changes'}
              </button>
              <button
                onClick={handleCancelEdit}
                className="px-4 py-2 bg-gray-600 text-white rounded-lg hover:bg-gray-700 transition"
              >
                ✕ Cancel
              </button>
            </div>
          </div>
          
          {/* Edit View - Similar to Live View */}
          <div className="grid grid-cols-2 gap-4">
            {/* Input Image */}
            <div className="flex flex-col space-y-2">
              <div className="bg-white p-2 shadow-sm border border-gray-200 text-center rounded-lg">
                <div className="text-xs text-gray-600">Input</div>
              </div>
              <div className="border-2 border-gray-300 rounded-lg overflow-hidden bg-white flex items-center justify-center" style={{ minHeight: '400px' }}>
                {editingImageUrl ? (
                  <img
                    src={editingImageUrl}
                    alt="Input"
                    className="max-w-full max-h-full object-contain"
                  />
                ) : (
                  <div className="text-gray-400">No image</div>
                )}
              </div>
            </div>

            {/* Output 2D Map */}
            <div className="flex flex-col space-y-2">
              <div className="bg-white p-2 shadow-sm border border-gray-200 text-center rounded-lg">
                <div className="text-xs text-gray-600">Output</div>
              </div>
              <div className="border-2 border-gray-300 rounded-lg overflow-hidden bg-white relative flex flex-col" style={{ minHeight: '400px' }}>
                {editingSpaces.length > 0 ? (
                  <ParkingMap2D
                    spaces={editingSpaces}
                    selectedSpaceId={selectedSpaceId}
                    onSpaceSelect={setSelectedSpaceId}
                    onSpaceDelete={(spaceId) => {
                      setEditingSpaces(editingSpaces.filter(s => s.id !== spaceId));
                      setSelectedSpaceId(null);
                    }}
                    onSpaceAdd={(bbox) => {
                      const newSpace: ParkingSpace = {
                        id: `space-manual-${Date.now()}`,
                        bbox: bbox,
                        confidence: 1.0
                      };
                      setEditingSpaces([...editingSpaces, newSpace]);
                    }}
                    imageWidth={imageRef.current ? imageRef.current.width : undefined}
                    imageHeight={imageRef.current ? imageRef.current.height : undefined}
                    sourceImageUrl={editingImageUrl}
                    zoom={zoom}
                    onZoomChange={setZoom}
                  />
                ) : (
                  <div className="flex items-center justify-center flex-1 text-gray-500">
                    <div className="text-center">
                      <div className="text-5xl mb-2">🤖</div>
                      <p>No spaces detected yet</p>
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Table Container - Hide when editing */}
      {!editingCameraId && (
        <>
          <div className="hidden lg:block">
            <div className="bg-white border-2 border-gray-200 rounded-xl overflow-hidden shadow-lg">
              <div className="bg-gray-100 border-b border-gray-200">
                <div
                  className="grid text-xs font-semibold text-gray-700 uppercase tracking-wide"
                  style={{ gridTemplateColumns: '150px 150px 180px 120px 1fr 1fr 120px 130px' }}
                >
                  <div className="px-3 py-3 text-center border-r border-gray-200">Parking</div>
                  <div className="px-3 py-3 text-center border-r border-gray-200">Camera</div>
                  <div className="px-3 py-3 text-center border-r border-gray-200">Date & Time</div>
                  <div className="px-3 py-3 text-center border-r border-gray-200">Count</div>
                  <div className="px-3 py-3 text-center border-r border-gray-200">Input</div>
                  <div className="px-3 py-3 text-center border-r border-gray-200">Output</div>
                  <div className="px-3 py-3 text-center border-r border-gray-200">Updates</div>
                  <div className="px-3 py-3 text-center">Actions</div>
                </div>
              </div>
              <div>
                {filteredRecords.map((record) => (
                  <div
                    key={record.id}
                    className="grid border-b border-gray-200 hover:bg-gray-50 transition-colors"
                    style={{ gridTemplateColumns: '150px 150px 180px 120px 1fr 1fr 120px 130px' }}
                  >
                    <div className="px-3 py-4 border-r border-gray-200 text-center">
                      <div className="font-semibold text-gray-800">{record.parkingId || 'N/A'}</div>
                    </div>
                    <div className="px-3 py-4 border-r border-gray-200 text-center">
                      <div className="text-gray-800 font-bold">{record.cameraId}</div>
                      <div className="text-xs text-gray-500 break-all leading-snug">{record.id}</div>
                    </div>
                    <div className="px-3 py-4 border-r border-gray-200 text-center text-xs text-gray-600">
                      <div className="font-semibold text-gray-800">{format(record.timestamp, 'dd/MM/yyyy')}</div>
                      <div>{format(record.timestamp, 'HH:mm:ss')}</div>
                    </div>
                    <div className="px-3 py-4 border-r border-gray-200 text-center">
                      <div className="text-2xl font-bold text-blue-600">
                        {record.vehicleCount}
                      </div>
                      <div className="text-xs text-gray-500">
                        {record.vehicleCount === 1 ? 'space' : 'spaces'}
                      </div>
                    </div>
                    <div className="px-3 py-4 border-r border-gray-200">
                      {record.inputImageUrl ? (
                        <div className="w-full h-64 flex items-center justify-center bg-gray-100 rounded border border-gray-200 overflow-hidden">
                          <img
                            src={record.inputImageUrl}
                            alt="Input"
                            className="max-w-full max-h-full object-contain"
                          />
                        </div>
                      ) : (
                        <div className="w-full h-64 bg-gray-100 border border-gray-200 rounded flex items-center justify-center text-xs text-gray-500">
                          📷 No image
                        </div>
                      )}
                    </div>
                    <div className="px-3 py-4 border-r border-gray-200">
                      {(() => {
                        const displaySpaces =
                          record.spaces ||
                          record.vehicles?.map((v, i) => ({
                            id: `space-${i}`,
                            bbox: (v as any).bbox || [0, 0, 0, 0],
                            confidence: (v as any).confidence || (v as any).score || 0,
                          })) ||
                          [];

                        if (displaySpaces.length > 0 && record.inputImageUrl) {
                          const dims = imageDimensions[record.inputImageUrl];
                          if (!dims) {
                            const img = new Image();
                            img.onload = () => {
                              setImageDimensions((prev) => ({
                                ...prev,
                                [record.inputImageUrl!]: { width: img.width, height: img.height },
                              }));
                            };
                            img.src = record.inputImageUrl;
                          }
                          return (
                            <div className="w-full h-64 flex items-center justify-center bg-gray-100 border border-gray-200 rounded overflow-hidden">
                              <ParkingMap2D
                                spaces={displaySpaces}
                                selectedSpaceId={null}
                                imageWidth={dims?.width || 800}
                                imageHeight={dims?.height || 600}
                                sourceImageUrl={record.inputImageUrl}
                                zoom={1}
                                onZoomChange={() => {}}
                                previewMode
                              />
                            </div>
                          );
                        }

                        if (displaySpaces.length > 0) {
                          return (
                            <div className="w-full h-64 bg-gray-100 border border-gray-200 rounded overflow-hidden flex items-center justify-center">
                              <ParkingMap2D
                                spaces={displaySpaces}
                                selectedSpaceId={null}
                                imageWidth={800}
                                imageHeight={600}
                                sourceImageUrl={undefined}
                                zoom={1}
                                onZoomChange={() => {}}
                                previewMode
                              />
                            </div>
                          );
                        }

                        return (
                          <div className="w-full h-64 bg-gray-100 border border-gray-200 rounded flex items-center justify-center text-xs text-gray-500">
                            🗺️ No map
                          </div>
                        );
                      })()}
                    </div>
                    <div className="px-3 py-4 border-r border-gray-200 text-center">
                      <div className="text-xl font-bold text-purple-600">{record.updateCount || 0}</div>
                      <div className="text-xs text-gray-500">times</div>
                    </div>
                    <div className="px-3 py-4 flex flex-col items-center justify-center gap-2">
                      <button
                        onClick={() => handleEdit(record)}
                        className="w-full px-3 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 transition text-xs font-semibold"
                      >
                        ✏️ Edit
                      </button>
                      <button
                        onClick={() => handleDeleteCamera(record.id)}
                        className="w-full px-3 py-2 bg-red-600 text-white rounded hover:bg-red-700 transition text-xs font-semibold"
                      >
                        🗑️ Delete
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Mobile friendly cards */}
          <div className="lg:hidden space-y-4">
            {filteredRecords.map((record) => (
              <div key={record.id} className="bg-white border border-gray-200 rounded-2xl shadow p-4 space-y-3">
                <div className="flex items-center justify-between">
                  <div>
                    <div className="text-xs uppercase text-gray-500">{record.parkingId || 'N/A'}</div>
                    <div className="text-lg font-semibold text-gray-900">{record.parkingId || 'Parking'}</div>
                    <div className="text-sm text-gray-600">{record.cameraId}</div>
                  </div>
                  <div className="text-right text-xs text-gray-500">
                    <div>{format(record.timestamp, 'dd/MM/yyyy')}</div>
                    <div>{format(record.timestamp, 'HH:mm:ss')}</div>
                  </div>
                </div>
                <div className="flex items-center gap-4">
                  <div className="text-center flex-1">
                    <div className="text-3xl font-bold text-blue-600">{record.vehicleCount}</div>
                    <div className="text-xs text-gray-500">spaces</div>
                  </div>
                  <div className="flex gap-2">
                    <button
                      onClick={() => handleEdit(record)}
                      className="px-3 py-2 bg-blue-600 text-white rounded-lg text-xs font-semibold"
                    >
                      ✏️ Edit
                    </button>
                    <button
                      onClick={() => handleDeleteCamera(record.id)}
                      className="px-3 py-2 bg-red-600 text-white rounded-lg text-xs font-semibold"
                    >
                      🗑️ Delete
                    </button>
                  </div>
                </div>
                {record.inputImageUrl && (
                  <div className="rounded-lg border border-gray-200 overflow-hidden">
                    <img src={record.inputImageUrl} alt="Input" className="w-full h-48 object-contain bg-gray-50" />
                  </div>
                )}
                {(record.spaces?.length || 0) > 0 && (
                  <div className="rounded-lg border border-gray-200 overflow-hidden">
                    <ParkingMap2D
                      spaces={record.spaces || []}
                      selectedSpaceId={null}
                      imageWidth={800}
                      imageHeight={600}
                      sourceImageUrl={record.inputImageUrl}
                      zoom={1}
                      onZoomChange={() => {}}
                      previewMode
                    />
                  </div>
                )}
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
