import { useState, useEffect } from 'react';
import { LiveDetection } from '../components/LiveDetection';
import { MediaSourceSelector } from '../components/MediaSourceSelector';
import { CameraCaptureSelector } from '../components/CameraCaptureSelector';
import { aiDetection } from '../services/ai/aiDetection';
import { useAuth } from '../context/AuthContext';

export function SpaceDetectionPage() {
  const { user } = useAuth();
  const [mediaElement, setMediaElement] = useState<HTMLVideoElement | HTMLImageElement | null>(null);
  const [modelLoaded, setModelLoaded] = useState(false);
  const [modelError, setModelError] = useState<string>('');
  const [sourceType, setSourceType] = useState<'camera' | 'upload' | 'capture'>('upload');
  const [capturedImageUrl, setCapturedImageUrl] = useState<string>('');
  
  useEffect(() => {
    // Load AI model with error handling
    const loadAI = async () => {
      try {
        await aiDetection.loadModel();
        setModelLoaded(true);
        console.log('✅ Model loaded successfully!');
      } catch (error) {
        const errorMsg = error instanceof Error ? error.message : 'Unknown error';
        setModelError(errorMsg);
        console.error('❌ Model load error:', errorMsg);
      }
    };
    
    loadAI();
  }, []);
  
  const handleStreamReady = (_stream: MediaStream) => {
    // Get video element from camera
    const video = document.querySelector('video');
    if (video) {
      setMediaElement(video);
    }
  };
  
  const handleMediaReady = (element: HTMLVideoElement | HTMLImageElement) => {
    // Get uploaded media element
    setMediaElement(element);
  };
  
  const handleSourceChange = (source: 'camera' | 'upload' | 'capture') => {
    setSourceType(source);
    setMediaElement(null); // Reset when switching
    setCapturedImageUrl(''); // Clear captured image
  };
  
  const handleCapture = (imageUrl: string) => {
    setCapturedImageUrl(imageUrl);
    // Create an image element from the captured URL
    const img = new Image();
    img.onload = () => {
      setMediaElement(img);
    };
    img.src = imageUrl;
  };
  
  return (
    <div className="p-6 min-h-full flex flex-col">
      {modelError ? (
        <div className="p-4 bg-red-50 text-red-700 rounded-lg shadow">
          <div className="font-bold mb-2">❌ Failed to load AI model</div>
          <div className="text-sm mb-3">{modelError}</div>
          {modelError.includes('API Key') && (
            <div className="text-xs bg-red-100 p-3 rounded">
              <strong>Hướng dẫn fix:</strong>
              <ol className="list-decimal ml-4 mt-1">
                <li>Vào <a href="https://roboflow.com/" target="_blank" className="underline">roboflow.com</a> và sign up</li>
                <li>Settings ⚙️ → Roboflow API → Copy API Key</li>
                <li>Paste vào file: <code className="bg-red-200 px-1">frontend/env.local</code></li>
                <li>Restart dev server: <code className="bg-red-200 px-1">npm run dev</code></li>
              </ol>
            </div>
          )}
        </div>
      ) : !modelLoaded ? (
        <div className="p-4 bg-yellow-50 text-yellow-700 rounded-lg shadow">
          ⏳ Loading AI model... Please wait.
        </div>
      ) : (
        <>
          {/* Source Selector */}
          <MediaSourceSelector 
            selectedSource={sourceType}
            onSourceChange={handleSourceChange}
          />
          
          {/* Camera Capture Component */}
          {sourceType === 'capture' && user && (
            <CameraCaptureSelector 
              userId={user.uid}
              onCapture={handleCapture}
            />
          )}
          
          {/* Detection Component */}
          <LiveDetection 
            videoElement={mediaElement} 
            onStreamReady={handleStreamReady}
            onMediaReady={handleMediaReady}
            sourceType={sourceType}
            capturedImageUrl={capturedImageUrl}
          />
        </>
      )}
    </div>
  );
}