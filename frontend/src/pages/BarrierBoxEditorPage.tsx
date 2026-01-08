import { useState, useEffect, useRef } from 'react';
import { db } from '../config/firebase';
import { collection, query, where, getDocs, doc, setDoc, deleteDoc } from 'firebase/firestore';
import { useAuth } from '../context/AuthContext';
import { getUserESP32Configs } from '../services/esp32ConfigService';
import { getParkingLotsByOwner } from '../services/parkingLotService';
import type { ParkingLot } from '../types/parkingLot.types';

interface Camera {
  id: string;
  name: string;
  ip_address: string;
}

interface BarrierBox {
  id: string;
  cameraId: string;
  x: number;
  y: number;
  width: number;
  height: number;
}

export function BarrierBoxEditorPage() {
  const { user } = useAuth();
  const [parkingLots, setParkingLots] = useState<ParkingLot[]>([]);
  const [selectedParkingId, setSelectedParkingId] = useState<string>('');
  const [cameras, setCameras] = useState<Camera[]>([]);
  const [selectedCameraId, setSelectedCameraId] = useState<string>('');
  const [barrierBox, setBarrierBox] = useState<BarrierBox | null>(null);
  
  const [isDrawing, setIsDrawing] = useState(false);
  const [startPoint, setStartPoint] = useState<{ x: number; y: number } | null>(null);
  const [currentBox, setCurrentBox] = useState<{ x: number; y: number; width: number; height: number } | null>(null);
  
  const [imageLoaded, setImageLoaded] = useState(false);
  
  
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const imgRef = useRef<HTMLImageElement>(null);

  // Load parking lots (same approach as ParkingSpaceEditorPage)
  useEffect(() => {
    if (!user) return;

    const load = async () => {
      try {
        const lotsData = await getParkingLotsByOwner(user.uid);
        setParkingLots(lotsData);
        if (lotsData.length > 0 && !selectedParkingId) {
          setSelectedParkingId(lotsData[0].id);
        }
      } catch (error) {
        console.error('Error loading parking lots:', error);
      }
    };

    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user]);

  // Load cameras - SAME AS ParkingSpaceEditorPage: load ALL ESP32 configs
  useEffect(() => {
    if (!user) return;

    const load = async () => {
      try {
        const configs = await getUserESP32Configs(user.uid);

        const allCams: Camera[] = configs.map((c) => ({
          id: c.id,
          name: c.name,
          ip_address: c.ipAddress,
        }));

        setCameras(allCams);
        if (allCams.length > 0 && !selectedCameraId) {
          setSelectedCameraId(allCams[0].id);
        }
      } catch (error) {
        console.error('Error loading cameras:', error);
        setCameras([]);
      }
    };

    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user]);

  // Load barrier box for selected camera
  useEffect(() => {
    if (!selectedCameraId) return;
    
    const loadBarrierBox = async () => {
      try {
        const barrierQuery = query(
          collection(db, 'barrierBoxes'),
          where('cameraId', '==', selectedCameraId)
        );
        const snapshot = await getDocs(barrierQuery);
        
        if (!snapshot.empty) {
          const doc = snapshot.docs[0];
          setBarrierBox({
            id: doc.id,
            ...doc.data() as Omit<BarrierBox, 'id'>
          });
        } else {
          setBarrierBox(null);
        }
      } catch (error) {
        console.error('Error loading barrier box:', error);
      }
    };
    
    loadBarrierBox();
  }, [selectedCameraId]);

  // Load stream - set canvas size when image loads (SAME AS ParkingSpaceEditorPage)
  useEffect(() => {
    if (!selectedCameraId || !canvasRef.current) return;

    const camera = cameras.find(c => c.id === selectedCameraId);
    if (!camera || !camera.ip_address) return;

    const canvas = canvasRef.current;
    const streamUrl = camera.ip_address.includes('/stream')
      ? camera.ip_address
      : `${camera.ip_address}/stream`;

    console.log('Loading camera stream from:', streamUrl);

    if (imgRef.current) {
      const img = imgRef.current;

      img.onload = () => {
        console.log('Image loaded, dimensions:', img.naturalWidth, 'x', img.naturalHeight);
        if (img.naturalWidth && img.naturalHeight) {
          canvas.width = img.naturalWidth;
          canvas.height = img.naturalHeight;
          console.log('Canvas size set to:', canvas.width, 'x', canvas.height);
          setImageLoaded(true);
        }
      };

      img.onerror = (e) => {
        console.error('Stream loading error:', e);
        console.error('Failed to load stream from:', streamUrl);
        setImageLoaded(false);
      };

      img.src = streamUrl;
    }

    return () => {
      if (imgRef.current) {
        imgRef.current.src = '';
      }
    };
  }, [selectedCameraId, cameras]);

  // Draw on canvas - SAME AS ParkingSpaceEditorPage: continuous animation loop
  useEffect(() => {
    const canvas = canvasRef.current;
    const img = imgRef.current;
    if (!canvas || !img) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let animationId: number;

    const draw = () => {
      // Check if image is loaded and valid
      if (img.complete && img.naturalWidth > 0 && canvas.width > 0) {
        // Clear canvas
        ctx.clearRect(0, 0, canvas.width, canvas.height);

        try {
          // Draw live MJPEG frame (img src updates automatically)
          ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
        } catch (error) {
          console.error('Error drawing image:', error);
        }

        // Draw existing barrier box
        if (barrierBox) {
          const x = barrierBox.x * canvas.width;
          const y = barrierBox.y * canvas.height;
          const width = barrierBox.width * canvas.width;
          const height = barrierBox.height * canvas.height;

          ctx.strokeStyle = '#ef4444'; // Red
          ctx.lineWidth = 3;
          ctx.strokeRect(x, y, width, height);

          ctx.fillStyle = 'rgba(239, 68, 68, 0.2)';
          ctx.fillRect(x, y, width, height);

          // Draw label
          ctx.fillStyle = '#ef4444';
          ctx.font = 'bold 16px sans-serif';
          ctx.fillText('🚧 BARRIER', x + 5, y + 20);
        }

        // Draw current drawing box
        if (currentBox) {
          const x = currentBox.x * canvas.width;
          const y = currentBox.y * canvas.height;
          const width = currentBox.width * canvas.width;
          const height = currentBox.height * canvas.height;

          ctx.strokeStyle = '#3b82f6'; // Blue
          ctx.lineWidth = 2;
          ctx.setLineDash([5, 5]);
          ctx.strokeRect(x, y, width, height);
          ctx.setLineDash([]);

          ctx.fillStyle = 'rgba(59, 130, 246, 0.1)';
          ctx.fillRect(x, y, width, height);
        }
      }

      animationId = requestAnimationFrame(draw);
    };

    // Start animation loop
    animationId = requestAnimationFrame(draw);

    return () => {
      cancelAnimationFrame(animationId);
    };
  }, [barrierBox, currentBox, imageLoaded]);

  // Mouse handlers
  const handleMouseDown = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current;
    if (!canvas || !imageLoaded) return;
    
    const rect = canvas.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    
    setIsDrawing(true);
    setStartPoint({ x, y });
    setCurrentBox({ x, y, width: 0, height: 0 });
  };

  const handleMouseMove = (e: React.MouseEvent<HTMLCanvasElement>) => {
    if (!isDrawing || !startPoint) return;
    
    const canvas = canvasRef.current;
    if (!canvas) return;
    
    const rect = canvas.getBoundingClientRect();
    const currentX = e.clientX - rect.left;
    const currentY = e.clientY - rect.top;
    
    const width = currentX - startPoint.x;
    const height = currentY - startPoint.y;
    
    setCurrentBox({
      x: width < 0 ? currentX : startPoint.x,
      y: height < 0 ? currentY : startPoint.y,
      width: Math.abs(width),
      height: Math.abs(height)
    });
  };

  const handleMouseUp = () => {
    if (!isDrawing || !currentBox || !imgRef.current) return;
    
  const img = imgRef.current;
  const displayWidth = canvasRef.current?.width || img.getBoundingClientRect().width;
  const displayHeight = canvasRef.current?.height || img.getBoundingClientRect().height;
    
    // Convert to normalized coordinates
    const normalizedBox = {
      x: currentBox.x / displayWidth,
      y: currentBox.y / displayHeight,
      width: currentBox.width / displayWidth,
      height: currentBox.height / displayHeight
    };
    
    // Save to state
    setBarrierBox({
      id: barrierBox?.id || '',
      cameraId: selectedCameraId,
      ...normalizedBox
    });
    
    setIsDrawing(false);
    setStartPoint(null);
    setCurrentBox(null);
  };

  // Save barrier box
  const handleSave = async () => {
    if (!barrierBox || !selectedCameraId) return;
    
    try {
      const barrierRef = barrierBox.id 
        ? doc(db, 'barrierBoxes', barrierBox.id)
        : doc(collection(db, 'barrierBoxes'));
      
      await setDoc(barrierRef, {
        cameraId: selectedCameraId,
        parkingId: selectedParkingId,
        x: barrierBox.x,
        y: barrierBox.y,
        width: barrierBox.width,
        height: barrierBox.height,
        updatedAt: new Date().toISOString()
      });
      
      alert('✅ Barrier box saved successfully!');
      
      // Reload barrier box
      setBarrierBox({
        ...barrierBox,
        id: barrierRef.id
      });
    } catch (error) {
      console.error('Error saving barrier box:', error);
      alert('❌ Failed to save barrier box');
    }
  };

  // Delete barrier box
  const handleDelete = async () => {
    if (!barrierBox?.id) return;
    
    if (!confirm('Are you sure you want to delete this barrier box?')) return;
    
    try {
      await deleteDoc(doc(db, 'barrierBoxes', barrierBox.id));
      setBarrierBox(null);
      alert('✅ Barrier box deleted');
    } catch (error) {
      console.error('Error deleting barrier box:', error);
      alert('❌ Failed to delete barrier box');
    }
  };

  // Refresh image - reload stream by appending timestamp
  const handleRefreshImage = () => {
    const camera = cameras.find(c => c.id === selectedCameraId);
    if (!camera || !camera.ip_address || !imgRef.current) return;
    
    const streamUrl = camera.ip_address.includes('/stream')
      ? camera.ip_address
      : `${camera.ip_address}/stream`;
    
    imgRef.current.src = streamUrl + '?t=' + Date.now();
    setImageLoaded(false);
  };

  return (
    <div className="min-h-screen p-6">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="bg-white rounded-xl shadow-lg border border-red-200 p-6 mb-6">
          <h1 className="text-3xl font-bold text-red-900 flex items-center gap-3">
            🚧 Barrier Box Editor
          </h1>
          <p className="text-red-700 mt-2">
            Draw barrier detection zones for automatic entry/exit detection
          </p>
        </div>

        {/* Controls */}
        <div className="bg-white rounded-xl shadow-lg border border-red-200 p-6 mb-6">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {/* Parking Lot Selection */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Parking Lot
              </label>
              <select
                value={selectedParkingId}
                onChange={(e) => {
                  setSelectedParkingId(e.target.value);
                  setSelectedCameraId('');
                }}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-red-500"
              >
                <option value="">Select parking lot</option>
                {parkingLots.map(lot => (
                  <option key={lot.id} value={lot.id}>
                    {lot.name}
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
                value={selectedCameraId}
                onChange={(e) => setSelectedCameraId(e.target.value)}
                disabled={!selectedParkingId}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-red-500 disabled:bg-gray-100"
              >
                <option value="">Select camera</option>
                {cameras.map(cam => (
                  <option key={cam.id} value={cam.id}>
                    {cam.name} {cam.ip_address ? `(${cam.ip_address})` : '(no ip)'}
                  </option>
                ))}
              </select>
            </div>

            {/* Actions */}
            <div className="flex items-end gap-2">
              <button
                onClick={handleRefreshImage}
                disabled={!selectedCameraId}
                className="flex-1 px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 disabled:bg-gray-300 transition"
              >
                🔄 Refresh Image
              </button>
            </div>
          </div>
        </div>

        {/* Instructions */}
        <div className="bg-yellow-50 border border-yellow-200 rounded-xl p-4 mb-6">
          <h3 className="font-semibold text-yellow-900 mb-2">📝 Instructions:</h3>
          <ul className="text-sm text-yellow-800 space-y-1">
            <li>• Click and drag on the image to draw a barrier detection box</li>
            <li>• Only ONE barrier box per camera (existing box will be replaced)</li>
            <li>• The barrier box should cover the entry/exit gate area</li>
            <li>• Click "Save Barrier Box" to save your changes</li>
            <li>• Mark camera as "Barrier Camera" in Multi Stream Host page</li>
          </ul>
        </div>

        {/* Canvas Area */}
        {selectedCameraId && (
          <div className="bg-white rounded-xl shadow-lg border border-red-200 p-6">
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-xl font-bold text-gray-900">
                {barrierBox ? '🚧 Edit Barrier Box' : '➕ Draw Barrier Box'}
              </h2>
              
              <div className="flex gap-2">
                {barrierBox && (
                  <button
                    onClick={handleDelete}
                    className="px-4 py-2 bg-red-500 text-white rounded-lg hover:bg-red-600 transition"
                  >
                    🗑️ Delete
                  </button>
                )}
                <button
                  onClick={handleSave}
                  disabled={!barrierBox}
                  className="px-6 py-2 bg-green-500 text-white rounded-lg hover:bg-green-600 disabled:bg-gray-300 transition font-semibold"
                >
                  💾 Save Barrier Box
                </button>
              </div>
            </div>

            {/* Image and Canvas */}
            <div className="relative inline-block border-4 border-gray-300 rounded-lg overflow-hidden">
              {/* Hidden image for MJPEG stream - SAME AS ParkingSpaceEditorPage */}
              <img
                ref={imgRef}
                alt="Camera stream"
                className="hidden"
                crossOrigin="anonymous"
              />
              
              {!selectedCameraId && (
                <div className="p-4 text-sm text-red-700 bg-red-50 border-t border-red-200">
                  ⚠️ Chọn camera để bắt đầu.
                </div>
              )}
              
              {/* Canvas for drawing and display */}
              <canvas
                ref={canvasRef}
                onMouseDown={handleMouseDown}
                onMouseMove={handleMouseMove}
                onMouseUp={handleMouseUp}
                onMouseLeave={handleMouseUp}
                className="w-full h-auto cursor-crosshair bg-black"
              />
            </div>

            {/* Status */}
            <div className="mt-4 text-sm text-gray-600">
              {barrierBox && (
                <div className="bg-green-50 border border-green-200 rounded-lg p-3">
                  <p className="font-semibold text-green-900">✅ Barrier Box Defined</p>
                  <p className="text-green-700 mt-1">
                    Position: ({(barrierBox.x * 100).toFixed(1)}%, {(barrierBox.y * 100).toFixed(1)}%)
                    Size: {(barrierBox.width * 100).toFixed(1)}% × {(barrierBox.height * 100).toFixed(1)}%
                  </p>
                </div>
              )}
              {!barrierBox && imageLoaded && (
                <div className="bg-blue-50 border border-blue-200 rounded-lg p-3">
                  <p className="text-blue-900">
                    ℹ️ No barrier box defined. Click and drag to draw one.
                  </p>
                </div>
              )}
            </div>
          </div>
        )}

        {!selectedCameraId && (
          <div className="bg-white rounded-xl shadow-lg border border-gray-200 p-12 text-center">
            <p className="text-gray-500 text-lg">
              👆 Select a parking lot and camera to start editing
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
