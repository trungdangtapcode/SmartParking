/**
 * Capture frame from MJPEG stream (img element)
 * Since MJPEG streams are displayed as <img>, we can directly get the image src
 * or create a snapshot endpoint on backend
 */

/**
 * Capture frame from img element displaying MJPEG stream
 * Since img element may have CORS restrictions, we'll use the stream URL directly
 * or create a canvas from the loaded image
 */
export function captureFrameFromMJPEGImage(imgElement: HTMLImageElement): string | null {
  try {
    if (!imgElement || !imgElement.complete) {
      console.warn('⚠️ Image not loaded yet');
      return null;
    }

    const canvas = document.createElement('canvas');
    const ctx = canvas.getContext('2d');
    
    if (!ctx) {
      console.error('❌ Canvas context not available');
      return null;
    }

    // Check for CORS issues
    try {
      canvas.width = imgElement.naturalWidth || imgElement.width;
      canvas.height = imgElement.naturalHeight || imgElement.height;
      
      if (canvas.width === 0 || canvas.height === 0) {
        console.error('❌ Image dimensions are zero');
        return null;
      }

      // Draw image to canvas
      ctx.drawImage(imgElement, 0, 0, canvas.width, canvas.height);
      
      // Convert to base64
      const dataUrl = canvas.toDataURL('image/jpeg', 0.8);
      return dataUrl;
    } catch (error) {
      // CORS error - fallback to fetching image directly from URL
      console.warn('⚠️ Canvas capture failed (possibly CORS), using URL directly');
      return null; // Will need backend snapshot endpoint
    }
  } catch (error) {
    console.error('❌ Error capturing frame:', error);
    return null;
  }
}

/**
 * Get snapshot from backend stream endpoint
 * For MJPEG streams, we can request a snapshot
 */
export async function getSnapshotFromStreamUrl(streamUrl: string): Promise<string | null> {
  try {
    // For video file streams, we can add snapshot endpoint
    // For now, try to fetch the current frame
    const response = await fetch(streamUrl, {
      method: 'GET',
      cache: 'no-cache',
    });

    if (!response.ok) {
      throw new Error(`Failed to fetch snapshot: ${response.status}`);
    }

    const blob = await response.blob();
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onloadend = () => resolve(reader.result as string);
      reader.onerror = reject;
      reader.readAsDataURL(blob);
    });
  } catch (error) {
    console.error('❌ Error getting snapshot:', error);
    return null;
  }
}

