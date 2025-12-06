import { API_CONFIG } from '../config/api';
import { savePlateDetection } from './plateDetectionService';
import { createVehicleCheckIn } from './vehicleService';
import type { SavePlateDetectionPayload } from './plateDetectionService';

const API_BASE = API_CONFIG.baseURL;

export interface CheckInResult {
  success: boolean;
  vehicleId?: string;
  licensePlate?: string;
  confidence?: number;
  error?: string;
}

/**
 * Check-in vehicle: OCR plate + Create Vehicle ID
 */
export async function performVehicleCheckIn(
  imageData: string,
  parkingId: string,
  cameraId: string,
  ownerId: string,
  onProgress?: (stage: string, percentage: number) => void
): Promise<CheckInResult> {
  try {
    // Step 1: OCR biển số với timeout
    onProgress?.('Đang khởi động OCR model...', 60);
    console.log('🔍 Starting OCR plate detection...');
    
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 30000); // 30s timeout cho OCR
    
    let ocrResponse: Response;
    try {
      onProgress?.('Đang xử lý OCR biển số...', 70);
      ocrResponse = await fetch(`${API_BASE}${API_CONFIG.endpoints.plateDetect}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ imageData }),
        signal: controller.signal,
      });
      clearTimeout(timeoutId);
    } catch (fetchError) {
      clearTimeout(timeoutId);
      if (fetchError instanceof Error && fetchError.name === 'AbortError') {
        throw new Error('OCR request timeout (30s). Model có thể đang load hoặc xử lý quá lâu.');
      }
      throw fetchError;
    }
    
    onProgress?.('Đang phân tích kết quả OCR...', 80);

    if (!ocrResponse.ok) {
      const errorText = await ocrResponse.text();
      throw new Error(`OCR failed: ${errorText}`);
    }

    const ocrData = await ocrResponse.json();
    
    if (!ocrData.success || !ocrData.plates || ocrData.plates.length === 0) {
      return {
        success: false,
        error: 'Không tìm thấy biển số trong frame. Hãy đảm bảo biển số rõ ràng và thử lại.',
      };
    }

    // Filter valid plates (confidence >= 10%)
    const validPlates = ocrData.plates.filter(
      (plate: { text: string; confidence: number }) => 
        plate.text && plate.text.trim().length > 0 && (plate.confidence || 0) >= 0.1
    );

    if (validPlates.length === 0) {
      return {
        success: false,
        error: 'Biển số không đủ tin cậy. Hãy thử lại.',
      };
    }

    // Use the first valid plate (highest confidence)
    const bestPlate = validPlates[0];
    const licensePlate = bestPlate.text.trim().toUpperCase();

    console.log(`✅ OCR result: ${licensePlate} (confidence: ${(bestPlate.confidence * 100).toFixed(1)}%)`);

    onProgress?.('Đang lưu kết quả OCR...', 85);

    // Step 2: Save plate detection to Firestore
    const plateDetectionPayload: SavePlateDetectionPayload = {
      ownerId,
      parkingId,
      cameraId,
      plateText: licensePlate,
      confidence: bestPlate.confidence,
      inputImageUrl: imageData, // Compressed version
      annotatedImageUrl: ocrData.annotatedImage,
    };

    const savePlateResult = await savePlateDetection(plateDetectionPayload);
    if (!savePlateResult.success) {
      console.warn('⚠️ Failed to save plate detection:', savePlateResult.error);
    }

    onProgress?.('Đang tạo Vehicle ID...', 90);

    // Step 3: Create vehicle check-in record
    const checkInResult = await createVehicleCheckIn({
      licensePlate,
      parkingId,
      cameraId,
      ownerId,
      entryImage: imageData,
    });

    if (!checkInResult.success) {
      return {
        success: false,
        error: checkInResult.error || 'Failed to create vehicle check-in',
      };
    }

    console.log(`✅ Vehicle check-in created: ${checkInResult.vehicleId}`);

    return {
      success: true,
      vehicleId: checkInResult.vehicleId,
      licensePlate,
      confidence: bestPlate.confidence,
    };
  } catch (error) {
    console.error('❌ Check-in error:', error);
    return {
      success: false,
      error: error instanceof Error ? error.message : 'Unknown error',
    };
  }
}

