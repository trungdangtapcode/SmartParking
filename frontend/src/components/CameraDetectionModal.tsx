import { useEffect, useState, useRef } from 'react';
import { doc, getDoc } from 'firebase/firestore';
import { db } from '../config/firebase';
import type { DetectionRecord } from '../services/detectionService';

interface CameraDetectionModalProps {
  cameraId: string;
  ownerId: string;
  onClose: () => void;
}

export function CameraDetectionModal({ cameraId, ownerId, onClose }: CameraDetectionModalProps) {
  const [detection, setDetection] = useState<DetectionRecord | null>(null);
  const [loading, setLoading] = useState(true);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const imageRef = useRef<HTMLImageElement>(null);

  useEffect(() => {
    loadDetection();
  }, [cameraId, ownerId]);

  useEffect(() => {
    if (detection && detection.inputImageUrl) {
      drawCanvas();
    }
  }, [detection]);

  const loadDetection = async () => {
    try {
      if (!db) return;
      
      const docId = `${ownerId}__${cameraId}`;
      const docRef = doc(db, 'detections', docId);
      const docSnap = await getDoc(docRef);

      if (docSnap.exists()) {
        const data = docSnap.data();
        setDetection({
          id: docId,
          ...data,
        } as DetectionRecord);
      }
    } catch (error) {
      console.error('Error loading detection:', error);
    } finally {
      setLoading(false);
    }
  };

  const drawCanvas = () => {
    if (!detection || !detection.inputImageUrl || !detection.spaces) return;

    const img = new Image();
    img.crossOrigin = 'anonymous';
    img.onload = () => {
      if (!canvasRef.current) return;

      const canvas = canvasRef.current;
      const ctx = canvas.getContext('2d');
      if (!ctx) return;

      // Set canvas size to match image
      canvas.width = img.naturalWidth;
      canvas.height = img.naturalHeight;

      // Draw image
      ctx.drawImage(img, 0, 0);

      // Draw bounding boxes
      detection.spaces.forEach((space, index) => {
        const [x, y, width, height] = space.bbox;

        // Draw box
        ctx.strokeStyle = '#10b981'; // green-500
        ctx.lineWidth = 3;
        ctx.strokeRect(x, y, width, height);

        // Draw label background
        ctx.fillStyle = '#10b981';
        ctx.fillRect(x, y - 30, 100, 30);

        // Draw label text
        ctx.fillStyle = '#ffffff';
        ctx.font = 'bold 14px Arial';
        ctx.fillText(`Space #${index + 1}`, x + 5, y - 10);

        // Draw confidence
        ctx.font = '12px Arial';
        const confidence = Math.round(space.confidence * 100);
        ctx.fillText(`${confidence}%`, x + 5, y + 20);
      });
    };
    img.src = detection.inputImageUrl;
  };

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4" onClick={onClose}>
      <div 
        className="bg-white rounded-2xl shadow-2xl max-w-5xl w-full max-h-[90vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="sticky top-0 bg-gradient-to-r from-blue-50 to-purple-50 p-6 border-b border-gray-200 flex items-center justify-between z-10">
          <div className="flex items-center gap-3">
            <span className="text-3xl">📹</span>
            <div>
              <h2 className="text-2xl font-bold text-gray-900">{cameraId}</h2>
              <p className="text-sm text-gray-600">Parking Spaces Detection</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 hover:bg-gray-200 rounded-full transition"
            title="Close"
          >
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Content */}
        <div className="p-6">
          {loading ? (
            <div className="text-center py-12">
              <div className="text-5xl mb-4">⏳</div>
              <div className="text-gray-600">Loading detection data...</div>
            </div>
          ) : !detection ? (
            <div className="text-center py-12">
              <div className="text-5xl mb-4">❌</div>
              <div className="text-gray-700 font-semibold mb-2">No detection found</div>
              <div className="text-sm text-gray-500">
                Camera {cameraId} chưa có dữ liệu parking spaces
              </div>
            </div>
          ) : (
            <div className="space-y-6">
              {/* Stats */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="bg-blue-50 rounded-xl p-4 border border-blue-200">
                  <div className="text-sm text-blue-600 font-medium mb-1">Parking Spaces</div>
                  <div className="text-3xl font-bold text-blue-700">
                    {detection.spaces?.length || 0}
                  </div>
                </div>
                <div className="bg-green-50 rounded-xl p-4 border border-green-200">
                  <div className="text-sm text-green-600 font-medium mb-1">Parking ID</div>
                  <div className="text-xl font-bold text-green-700">
                    {detection.parkingId || 'N/A'}
                  </div>
                </div>
                <div className="bg-purple-50 rounded-xl p-4 border border-purple-200">
                  <div className="text-sm text-purple-600 font-medium mb-1">Last Update</div>
                  <div className="text-sm font-semibold text-purple-700">
                    {detection.timestamp?.toDate().toLocaleString('vi-VN') || 'N/A'}
                  </div>
                </div>
              </div>

              {/* Detection Image with Bounding Boxes */}
              {detection.inputImageUrl ? (
                <div className="bg-gray-50 rounded-xl p-4 border-2 border-gray-200">
                  <h3 className="text-lg font-semibold text-gray-800 mb-3 flex items-center gap-2">
                    <span>🖼️</span>
                    <span>Detection Preview</span>
                  </h3>
                  <div className="relative bg-black rounded-lg overflow-hidden">
                    <canvas
                      ref={canvasRef}
                      className="w-full h-auto"
                      style={{ maxHeight: '600px', objectFit: 'contain' }}
                    />
                    {/* Hidden image for loading */}
                    <img
                      ref={imageRef}
                      src={detection.inputImageUrl}
                      alt={`Detection for ${cameraId}`}
                      className="hidden"
                    />
                    {/* Overlay with space count */}
                    <div className="absolute top-4 right-4 bg-green-600 text-white px-4 py-2 rounded-full shadow-lg">
                      <span className="font-bold">{detection.spaces?.length || 0}</span> spaces
                    </div>
                  </div>
                  <p className="text-xs text-gray-500 mt-2">
                    💡 Green boxes indicate detected parking spaces
                  </p>
                </div>
              ) : (
                <div className="bg-gray-50 rounded-xl p-8 border-2 border-dashed border-gray-300 text-center">
                  <div className="text-4xl mb-3">📷</div>
                  <div className="text-gray-600">No image available</div>
                </div>
              )}

              {/* Spaces List */}
              {detection.spaces && detection.spaces.length > 0 && (
                <div className="bg-gray-50 rounded-xl p-4 border-2 border-gray-200">
                  <h3 className="text-lg font-semibold text-gray-800 mb-3 flex items-center gap-2">
                    <span>📋</span>
                    <span>Parking Spaces List ({detection.spaces.length})</span>
                  </h3>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3 max-h-60 overflow-y-auto">
                    {detection.spaces.map((space, idx) => (
                      <div
                        key={space.id}
                        className="bg-white rounded-lg p-3 border border-gray-200 hover:border-blue-300 transition"
                      >
                        <div className="flex items-center justify-between mb-2">
                          <div className="text-sm font-semibold text-gray-700">
                            Space #{idx + 1}
                          </div>
                          <div className="text-xs bg-green-100 text-green-700 px-2 py-1 rounded-full">
                            {Math.round(space.confidence * 100)}%
                          </div>
                        </div>
                        <div className="text-xs text-gray-500 font-mono">
                          [{space.bbox[0].toFixed(0)}, {space.bbox[1].toFixed(0)}, {space.bbox[2].toFixed(0)}, {space.bbox[3].toFixed(0)}]
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="sticky bottom-0 bg-gray-50 px-6 py-4 border-t border-gray-200 flex justify-end gap-3">
          <button
            onClick={onClose}
            className="px-6 py-2 bg-gray-200 hover:bg-gray-300 rounded-lg transition font-medium"
          >
            Đóng
          </button>
        </div>
      </div>
    </div>
  );
}

