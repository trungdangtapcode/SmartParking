import { useState, useEffect, useRef } from 'react';
import { useAuth } from '../context/AuthContext';
import { getUserESP32Configs } from '../services/esp32ConfigService';
import { getParkingLotsByOwner } from '../services/parkingLotService';
import {
  getParkingSpacesByCamera,
  deleteParkingSpace,
  batchSaveParkingSpaces,
} from '../services/parkingSpaceService';
import type { ParkingLot } from '../types/parkingLot.types';
import type { ParkingSpaceDefinition } from '../types/parkingLot.types';

interface ESP32Config {
  id: string;
  name: string;
  ipAddress: string;
}

interface ResizableSpace extends Omit<ParkingSpaceDefinition, 'createdAt' | 'updatedAt'> {
  isResizing?: boolean;
  isDragging?: boolean;
}

export function ParkingSpaceEditorPage() {
  const { user } = useAuth();
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const videoRef = useRef<HTMLVideoElement>(null);
  const imgRef = useRef<HTMLImageElement>(null);
  const [isLoading, setIsLoading] = useState(true);

  // Selection states
  const [parkingLots, setParkingLots] = useState<ParkingLot[]>([]);
  const [cameras, setCameras] = useState<ESP32Config[]>([]);
  const [selectedParkingLot, setSelectedParkingLot] = useState<string>('');
  const [selectedCamera, setSelectedCamera] = useState<string>('');

  // Parking spaces
  const [spaces, setSpaces] = useState<ResizableSpace[]>([]);
  const [selectedSpaceId, setSelectedSpaceId] = useState<string | null>(null);
  const [nextSpaceNumber, setNextSpaceNumber] = useState(1);

  // Drawing state
  const [isDrawing, setIsDrawing] = useState(false);
  const [startPoint, setStartPoint] = useState<{ x: number; y: number } | null>(null);
  const [currentBox, setCurrentBox] = useState<{ x: number; y: number; width: number; height: number } | null>(null);

  // Drag/Resize state
  const [dragStart, setDragStart] = useState<{ x: number; y: number } | null>(null);
  const [resizeHandle, setResizeHandle] = useState<string | null>(null);

  // Image dimensions
  const [imageDimensions, setImageDimensions] = useState({ width: 640, height: 480 });

  // Load parking lots and cameras
  useEffect(() => {
    const loadData = async () => {
      if (!user) return;

      setIsLoading(true);
      try {
        const [lotsData, camerasData] = await Promise.all([
          getParkingLotsByOwner(user.uid),
          getUserESP32Configs(user.uid),
        ]);

        setParkingLots(lotsData);
        setCameras(camerasData);
      } catch (error) {
        console.error('Failed to load data:', error);
      } finally {
        setIsLoading(false);
      }
    };

    loadData();
  }, [user]);

  // Load parking spaces when camera is selected
  useEffect(() => {
    const loadSpaces = async () => {
      if (!selectedCamera) {
        setSpaces([]);
        return;
      }

      try {
        const spacesData = await getParkingSpacesByCamera(selectedCamera);
        setSpaces(spacesData);
        
        // Calculate next space number
        if (spacesData.length > 0) {
          const maxNum = Math.max(...spacesData.map(s => {
            const match = s.name.match(/\d+/);
            return match ? parseInt(match[0]) : 0;
          }));
          setNextSpaceNumber(maxNum + 1);
        }
      } catch (error) {
        console.error('Failed to load parking spaces:', error);
      }
    };

    loadSpaces();
  }, [selectedCamera]);

  // Load video stream
  useEffect(() => {
    if (!selectedCamera || !canvasRef.current) return;

    const camera = cameras.find(c => c.id === selectedCamera);
    if (!camera) return;

    const canvas = canvasRef.current;
    
    // Use the correct stream endpoint
    // ESP32 cameras use /stream endpoint for MJPEG
    const streamUrl = camera.ipAddress.includes('/stream') 
      ? camera.ipAddress 
      : `${camera.ipAddress}/stream`;
    
    console.log('Loading camera stream from:', streamUrl);
    setIsLoading(true);
    
    // Try to use img for MJPEG stream first
    if (imgRef.current) {
      const img = imgRef.current;
      
      img.onload = () => {
        console.log('Image loaded, dimensions:', img.naturalWidth, 'x', img.naturalHeight);
        if (img.naturalWidth && img.naturalHeight) {
          setImageDimensions({
            width: img.naturalWidth,
            height: img.naturalHeight,
          });
          
          // Set canvas size to match image
          canvas.width = img.naturalWidth;
          canvas.height = img.naturalHeight;
          
          console.log('Canvas size set to:', canvas.width, 'x', canvas.height);
          setIsLoading(false);
        }
      };
      
      img.onerror = (e) => {
        console.error('Image loading error:', e);
        console.error('Failed to load stream from:', streamUrl);
        setIsLoading(false);
      };
      
      img.src = streamUrl;
    }

    return () => {
      if (imgRef.current) {
        imgRef.current.src = '';
      }
      if (videoRef.current) {
        videoRef.current.src = '';
      }
    };
  }, [selectedCamera, cameras]);

  // Draw on canvas
  useEffect(() => {
    const canvas = canvasRef.current;
    const img = imgRef.current;
    if (!canvas || !img) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let animationId: number;
    let frameCount = 0;
    
    const draw = () => {
      // Check if image is loaded and has valid dimensions
      if (img.complete && img.naturalWidth > 0 && canvas.width > 0) {
        // Clear canvas
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        
        try {
          // Draw image frame (MJPEG stream updates the img src automatically)
          ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
          
          // Debug log every 60 frames (about 1 second at 60fps)
          if (frameCount % 60 === 0) {
            console.log('Drawing frame, img:', img.naturalWidth, 'x', img.naturalHeight, 'canvas:', canvas.width, 'x', canvas.height);
          }
          frameCount++;
        } catch (error) {
          console.error('Error drawing image frame:', error);
        }

        // Draw existing parking spaces
        spaces.forEach(space => {
          const x = space.x * canvas.width;
          const y = space.y * canvas.height;
          const width = space.width * canvas.width;
          const height = space.height * canvas.height;

          // Draw rectangle
          ctx.strokeStyle = space.id === selectedSpaceId ? '#ef4444' : '#22c55e';
          ctx.lineWidth = 3;
          ctx.strokeRect(x, y, width, height);

          // Draw semi-transparent fill
          ctx.fillStyle = space.id === selectedSpaceId ? 'rgba(239, 68, 68, 0.2)' : 'rgba(34, 197, 94, 0.2)';
          ctx.fillRect(x, y, width, height);

          // Draw label with background
          ctx.fillStyle = '#fff';
          ctx.font = 'bold 16px Arial';
          ctx.strokeStyle = '#000';
          ctx.lineWidth = 4;
          ctx.strokeText(space.name, x + 5, y + 20);
          ctx.fillText(space.name, x + 5, y + 20);

          // Draw resize handles if selected
          if (space.id === selectedSpaceId) {
            const handleSize = 8;
            ctx.fillStyle = '#ef4444';
            // Top-left
            ctx.fillRect(x - handleSize / 2, y - handleSize / 2, handleSize, handleSize);
            // Top-right
            ctx.fillRect(x + width - handleSize / 2, y - handleSize / 2, handleSize, handleSize);
            // Bottom-left
            ctx.fillRect(x - handleSize / 2, y + height - handleSize / 2, handleSize, handleSize);
            // Bottom-right
            ctx.fillRect(x + width - handleSize / 2, y + height - handleSize / 2, handleSize, handleSize);
          }
        });

        // Draw current drawing box
        if (currentBox) {
          const x = currentBox.x * canvas.width;
          const y = currentBox.y * canvas.height;
          const width = currentBox.width * canvas.width;
          const height = currentBox.height * canvas.height;

          ctx.strokeStyle = '#3b82f6';
          ctx.lineWidth = 3;
          ctx.setLineDash([5, 5]);
          ctx.strokeRect(x, y, width, height);
          ctx.setLineDash([]);
          
          // Draw semi-transparent fill for drawing box
          ctx.fillStyle = 'rgba(59, 130, 246, 0.1)';
          ctx.fillRect(x, y, width, height);
        }
      }

      animationId = requestAnimationFrame(draw);
    };

    // Start drawing loop
    animationId = requestAnimationFrame(draw);

    return () => {
      cancelAnimationFrame(animationId);
    };
  }, [spaces, selectedSpaceId, currentBox]);

  // Mouse down handler
  const handleMouseDown = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current;
    if (!canvas || !selectedCamera) return;

    const rect = canvas.getBoundingClientRect();
    const x = (e.clientX - rect.left) / rect.width;
    const y = (e.clientY - rect.top) / rect.height;

    // Check if clicking on a resize handle
    const selectedSpace = spaces.find(s => s.id === selectedSpaceId);
    if (selectedSpace) {
      const handle = getResizeHandle(x, y, selectedSpace, rect);
      if (handle) {
        setResizeHandle(handle);
        setDragStart({ x, y });
        return;
      }
    }

    // Check if clicking on an existing space
    const clickedSpace = spaces.find(space => {
      return (
        x >= space.x &&
        x <= space.x + space.width &&
        y >= space.y &&
        y <= space.y + space.height
      );
    });

    if (clickedSpace) {
      setSelectedSpaceId(clickedSpace.id);
      setDragStart({ x, y });
      return;
    }

    // Start drawing new space
    setSelectedSpaceId(null);
    setIsDrawing(true);
    setStartPoint({ x, y });
    setCurrentBox({ x, y, width: 0, height: 0 });
  };

  // Mouse move handler
  const handleMouseMove = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const rect = canvas.getBoundingClientRect();
    const x = (e.clientX - rect.left) / rect.width;
    const y = (e.clientY - rect.top) / rect.height;

    // Update cursor
    if (selectedSpaceId && !dragStart && !resizeHandle) {
      const selectedSpace = spaces.find(s => s.id === selectedSpaceId);
      if (selectedSpace) {
        const handle = getResizeHandle(x, y, selectedSpace, rect);
        canvas.style.cursor = handle ? 'nwse-resize' : 'move';
      }
    } else if (isDrawing) {
      canvas.style.cursor = 'crosshair';
    } else {
      canvas.style.cursor = 'default';
    }

    // Handle drawing
    if (isDrawing && startPoint) {
      const width = x - startPoint.x;
      const height = y - startPoint.y;
      setCurrentBox({ x: startPoint.x, y: startPoint.y, width, height });
    }

    // Handle dragging
    if (dragStart && selectedSpaceId && !resizeHandle) {
      const dx = x - dragStart.x;
      const dy = y - dragStart.y;

      setSpaces(prev =>
        prev.map(space =>
          space.id === selectedSpaceId
            ? { ...space, x: space.x + dx, y: space.y + dy }
            : space
        )
      );
      setDragStart({ x, y });
    }

    // Handle resizing
    if (dragStart && selectedSpaceId && resizeHandle) {
      const dx = x - dragStart.x;
      const dy = y - dragStart.y;

      setSpaces(prev =>
        prev.map(space => {
          if (space.id !== selectedSpaceId) return space;

          const updated = { ...space };
          
          if (resizeHandle.includes('left')) {
            updated.x += dx;
            updated.width -= dx;
          }
          if (resizeHandle.includes('right')) {
            updated.width += dx;
          }
          if (resizeHandle.includes('top')) {
            updated.y += dy;
            updated.height -= dy;
          }
          if (resizeHandle.includes('bottom')) {
            updated.height += dy;
          }

          return updated;
        })
      );
      setDragStart({ x, y });
    }
  };

  // Mouse up handler
  const handleMouseUp = () => {
    if (isDrawing && currentBox && startPoint) {
      // Create new parking space
      const newSpace: ResizableSpace = {
        id: `${selectedCamera}_space_${Date.now()}`,
        parkingId: selectedParkingLot,
        cameraId: selectedCamera,
        name: `P${nextSpaceNumber}`,
        x: Math.min(startPoint.x, startPoint.x + currentBox.width),
        y: Math.min(startPoint.y, startPoint.y + currentBox.height),
        width: Math.abs(currentBox.width),
        height: Math.abs(currentBox.height),
        createdBy: user?.uid || '',
      };

      setSpaces(prev => [...prev, newSpace]);
      setNextSpaceNumber(prev => prev + 1);
      setSelectedSpaceId(newSpace.id);
    }

    setIsDrawing(false);
    setStartPoint(null);
    setCurrentBox(null);
    setDragStart(null);
    setResizeHandle(null);
  };

  // Get resize handle
  const getResizeHandle = (
    x: number,
    y: number,
    space: ResizableSpace,
    rect: DOMRect
  ): string | null => {
    const handleSize = 8 / rect.width; // Normalized handle size

    const handles = [
      { name: 'top-left', x: space.x, y: space.y },
      { name: 'top-right', x: space.x + space.width, y: space.y },
      { name: 'bottom-left', x: space.x, y: space.y + space.height },
      { name: 'bottom-right', x: space.x + space.width, y: space.y + space.height },
    ];

    for (const handle of handles) {
      if (
        Math.abs(x - handle.x) < handleSize &&
        Math.abs(y - handle.y) < handleSize
      ) {
        return handle.name;
      }
    }

    return null;
  };

  // Save spaces
  const handleSave = async () => {
    if (spaces.length === 0) {
      alert('Không có parking space nào để lưu!');
      return;
    }

    try {
      const result = await batchSaveParkingSpaces(spaces);
      if (result.success) {
        alert(`✅ Đã lưu ${result.savedCount} parking spaces!`);
      } else {
        alert(`❌ Lỗi: ${result.error}`);
      }
    } catch (error) {
      console.error('Failed to save spaces:', error);
      alert('❌ Không thể lưu parking spaces!');
    }
  };

  // Delete selected space
  const handleDeleteSelected = async () => {
    if (!selectedSpaceId) {
      alert('Chọn một parking space để xóa!');
      return;
    }

    if (!confirm('Bạn có chắc muốn xóa parking space này?')) {
      return;
    }

    try {
      await deleteParkingSpace(selectedSpaceId);
      setSpaces(prev => prev.filter(s => s.id !== selectedSpaceId));
      setSelectedSpaceId(null);
      alert('✅ Đã xóa parking space!');
    } catch (error) {
      console.error('Failed to delete space:', error);
      alert('❌ Không thể xóa parking space!');
    }
  };

  // Clear all spaces
  const handleClearAll = () => {
    if (!confirm('Bạn có chắc muốn xóa TẤT CẢ parking spaces?')) {
      return;
    }

    setSpaces([]);
    setSelectedSpaceId(null);
    setNextSpaceNumber(1);
  };

  // Update space name
  const handleUpdateSpaceName = (spaceId: string, newName: string) => {
    setSpaces(prev =>
      prev.map(space =>
        space.id === spaceId ? { ...space, name: newName } : space
      )
    );
  };

  if (!user) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <h2 className="text-2xl font-bold text-strawberry-900 mb-4">
            🔒 Vui lòng đăng nhập
          </h2>
          <p className="text-gray-600">Bạn cần đăng nhập để sử dụng tính năng này.</p>
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
            📐 Parking Space Editor
          </h1>
          <p className="text-gray-600">
            Định nghĩa vị trí các chỗ đỗ xe trên camera bằng cách kéo thả và điều chỉnh các khung
          </p>
        </div>

        {/* Configuration */}
        <div className="bg-white rounded-xl shadow-lg p-6 mb-6 border-2 border-matcha-200">
          <h2 className="text-xl font-bold text-matcha-900 mb-4">⚙️ Cấu hình</h2>
          
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Parking Lot Selection */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Bãi đỗ xe
              </label>
              <select
                value={selectedParkingLot}
                onChange={(e) => setSelectedParkingLot(e.target.value)}
                className="w-full px-4 py-2 border-2 border-matcha-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-matcha-400"
                disabled={isLoading}
              >
                <option value="">-- Chọn bãi đỗ xe --</option>
                {parkingLots.map(lot => (
                  <option key={lot.id} value={lot.id}>
                    🅿️ {lot.name}
                  </option>
                ))}
              </select>
            </div>

            {/* Camera Selection */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Camera
              </label>
              <select
                value={selectedCamera}
                onChange={(e) => setSelectedCamera(e.target.value)}
                className="w-full px-4 py-2 border-2 border-strawberry-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-strawberry-400"
                disabled={!selectedParkingLot || isLoading}
              >
                <option value="">-- Chọn camera --</option>
                {cameras.map(camera => (
                  <option key={camera.id} value={camera.id}>
                    📹 {camera.name} ({camera.ipAddress})
                  </option>
                ))}
              </select>
            </div>
          </div>
        </div>

        {/* Editor */}
        {selectedCamera && (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Canvas */}
            <div className="lg:col-span-2">
              <div className="bg-white rounded-xl shadow-lg p-6 border-2 border-blue-200">
                <h2 className="text-xl font-bold text-blue-900 mb-4">🎨 Canvas</h2>
                
                <div className="relative bg-black rounded-lg overflow-hidden">
                  {/* Hidden image for MJPEG stream */}
                  <img
                    ref={imgRef}
                    alt="Camera stream"
                    className="hidden"
                    crossOrigin="anonymous"
                  />
                  {/* Hidden video for fallback */}
                  <video
                    ref={videoRef}
                    autoPlay
                    muted
                    playsInline
                    className="hidden"
                  />
                  
                  {/* Loading overlay */}
                  {isLoading && (
                    <div className="absolute inset-0 flex items-center justify-center bg-gray-900 text-white z-10">
                      <div className="text-center">
                        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-white mx-auto mb-4"></div>
                        <p>Đang tải camera stream...</p>
                      </div>
                    </div>
                  )}
                  
                  {/* Canvas for drawing */}
                  <canvas
                    ref={canvasRef}
                    width={imageDimensions.width}
                    height={imageDimensions.height}
                    onMouseDown={handleMouseDown}
                    onMouseMove={handleMouseMove}
                    onMouseUp={handleMouseUp}
                    onMouseLeave={handleMouseUp}
                    className="w-full h-auto cursor-crosshair"
                  />
                </div>

                <div className="mt-4 p-4 bg-blue-50 rounded-lg border border-blue-200">
                  <h3 className="font-bold text-blue-900 mb-2">📝 Hướng dẫn:</h3>
                  <ul className="text-sm text-blue-800 space-y-1">
                    <li>• <strong>Vẽ mới:</strong> Click và kéo trên canvas để tạo parking space mới</li>
                    <li>• <strong>Di chuyển:</strong> Click vào parking space và kéo để di chuyển</li>
                    <li>• <strong>Resize:</strong> Click vào các góc của parking space để thay đổi kích thước</li>
                    <li>• <strong>Xóa:</strong> Chọn parking space và click nút "Xóa đã chọn"</li>
                    <li>• <strong>Lưu:</strong> Nhớ click "Lưu tất cả" để lưu thay đổi vào database</li>
                  </ul>
                </div>
              </div>
            </div>

            {/* Sidebar */}
            <div className="space-y-6">
              {/* Actions */}
              <div className="bg-white rounded-xl shadow-lg p-6 border-2 border-green-200">
                <h2 className="text-xl font-bold text-green-900 mb-4">🎮 Actions</h2>
                
                <div className="space-y-3">
                  <button
                    onClick={handleSave}
                    className="w-full px-4 py-3 bg-green-500 text-white rounded-lg font-medium hover:bg-green-600 transition-colors"
                    disabled={spaces.length === 0}
                  >
                    💾 Lưu tất cả ({spaces.length})
                  </button>
                  
                  <button
                    onClick={handleDeleteSelected}
                    className="w-full px-4 py-3 bg-red-500 text-white rounded-lg font-medium hover:bg-red-600 transition-colors"
                    disabled={!selectedSpaceId}
                  >
                    🗑️ Xóa đã chọn
                  </button>
                  
                  <button
                    onClick={handleClearAll}
                    className="w-full px-4 py-3 bg-gray-500 text-white rounded-lg font-medium hover:bg-gray-600 transition-colors"
                    disabled={spaces.length === 0}
                  >
                    🧹 Xóa tất cả
                  </button>
                </div>
              </div>

              {/* Spaces List */}
              <div className="bg-white rounded-xl shadow-lg p-6 border-2 border-purple-200">
                <h2 className="text-xl font-bold text-purple-900 mb-4">
                  📋 Parking Spaces ({spaces.length})
                </h2>
                
                <div className="space-y-2 max-h-96 overflow-y-auto">
                  {spaces.length === 0 ? (
                    <p className="text-gray-500 text-sm text-center py-4">
                      Chưa có parking space nào
                    </p>
                  ) : (
                    spaces.map(space => (
                      <div
                        key={space.id}
                        onClick={() => setSelectedSpaceId(space.id)}
                        className={`p-3 rounded-lg border-2 cursor-pointer transition-all ${
                          space.id === selectedSpaceId
                            ? 'bg-purple-50 border-purple-400'
                            : 'bg-gray-50 border-gray-200 hover:border-purple-300'
                        }`}
                      >
                        <input
                          type="text"
                          value={space.name}
                          onChange={(e) => handleUpdateSpaceName(space.id, e.target.value)}
                          onClick={(e) => e.stopPropagation()}
                          className="w-full px-2 py-1 text-sm font-bold bg-transparent border-b border-transparent hover:border-purple-300 focus:outline-none focus:border-purple-500"
                        />
                        <div className="text-xs text-gray-500 mt-1">
                          📍 {(space.x * 100).toFixed(1)}%, {(space.y * 100).toFixed(1)}%
                          <br />
                          📏 {(space.width * 100).toFixed(1)}% × {(space.height * 100).toFixed(1)}%
                        </div>
                      </div>
                    ))
                  )}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Empty state */}
        {!selectedCamera && (
          <div className="bg-white rounded-xl shadow-lg p-12 text-center border-2 border-gray-200">
            <div className="text-6xl mb-4">🎯</div>
            <h2 className="text-2xl font-bold text-gray-900 mb-2">
              Chọn bãi đỗ xe và camera
            </h2>
            <p className="text-gray-600">
              Vui lòng chọn bãi đỗ xe và camera để bắt đầu định nghĩa parking spaces
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
