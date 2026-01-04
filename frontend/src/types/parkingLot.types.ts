import { Timestamp } from 'firebase/firestore';

/**
 * Parking Lot (Bãi đỗ xe) - Collection: parkingLots
 * Quản lý thông tin tổng quan của từng bãi đỗ
 */
export interface ParkingLot {
  // Basic Info
  id: string;                    // "PARKING_A"
  name: string;                  // "Bãi đỗ xe tòa nhà A"
  address: string;               // "123 Nguyễn Văn A, TP.HCM"
  ownerId: string;               // User ID của chủ bãi
  
  // Capacity
  totalSpaces: number;           // Tổng số chỗ (aggregate từ cameras)
  availableSpaces: number;       // Số chỗ trống (updated by tracking)
  occupiedSpaces: number;        // Số chỗ đã đỗ (updated by tracking)
  
  // Cameras
  cameras: string[];             // ["CAM001", "CAM002", "CAM003"]
  
  // Metadata
  createdAt: Timestamp;
  updatedAt: Timestamp;
  status: 'active' | 'inactive'; // Bãi có đang hoạt động không
  
  // Optional: Business info
  pricePerHour?: number;         // Giá tiền/giờ (VND)
  openTime?: string;             // "00:00"
  closeTime?: string;            // "23:59"
  description?: string;          // Mô tả bãi đỗ
}

/**
 * Parking Space Definition - Collection: parkingSpaceDefinitions
 * Định nghĩa vị trí các parking spaces trên camera (do user config)
 */
export interface ParkingSpaceDefinition {
  // Space Identity
  id: string;                    // "space-001"
  parkingId: string;             // "PARKING_A"
  cameraId: string;              // "CAM001" or ESP32 config ID
  name: string;                  // "A1", "A2", "B1" etc.
  
  // Location (normalized 0-1 based on image dimensions)
  x: number;                     // x position (0-1)
  y: number;                     // y position (0-1)
  width: number;                 // width (0-1)
  height: number;                // height (0-1)
  
  // Metadata
  createdAt: Timestamp;
  updatedAt: Timestamp;
  createdBy: string;             // User ID who created this space
}

/**
 * Parking Space Status - Collection: parkingSpaces
 * Track trạng thái từng parking slot (Phase 2 - Tracking)
 */
export interface ParkingSpaceStatus {
  // Space Identity
  spaceId: string;               // "space-001"
  parkingId: string;             // "PARKING_A"
  cameraId: string;              // "CAM001"
  
  // Location
  bbox: [number, number, number, number]; // [x, y, width, height]
  
  // Status (Updated by tracking system)
  occupied: boolean;             // true = có xe, false = trống
  lastDetectionTime: Timestamp;  // Lần cuối detect
  
  // Vehicle Info (if occupied)
  vehicleType?: string;          // "car", "motorbike"
  vehicleId?: string;            // Tracking ID
  entryTime?: Timestamp;         // Thời gian xe vào
  licensePlate?: string;         // Biển số (from OCR)
  
  // Metadata
  createdAt: Timestamp;
  updatedAt: Timestamp;
}

/**
 * Vehicle Tracking Record - Collection: vehicleTracking
 * Lưu lịch sử xe ra vào (cho báo cáo, tính tiền)
 */
export interface VehicleTrackingRecord {
  // Vehicle Info
  vehicleId: string;             // Tracking ID
  licensePlate?: string;         // Biển số
  vehicleType: string;           // "car", "motorbike"
  
  // Location
  parkingId: string;             // "PARKING_A"
  spaceId: string;               // "space-001"
  cameraId: string;              // "CAM001"
  
  // Timing
  entryTime: Timestamp;          // Thời gian vào
  exitTime?: Timestamp;          // Thời gian ra (null nếu chưa ra)
  duration?: number;             // Thời gian đỗ (seconds)
  
  // Images
  entryImage?: string;           // Ảnh lúc vào
  exitImage?: string;            // Ảnh lúc ra
  
  // Payment
  fee?: number;                  // Phí đỗ xe
  paid?: boolean;                // Đã thanh toán chưa
  
  // Metadata
  createdAt: Timestamp;
  updatedAt: Timestamp;
}

/**
 * Create Parking Lot Input
 */
export interface CreateParkingLotInput {
  id: string;
  name: string;
  address: string;
  ownerId: string;
  pricePerHour?: number;
  openTime?: string;
  closeTime?: string;
  description?: string;
}

/**
 * Update Parking Lot Input
 */
export interface UpdateParkingLotInput {
  name?: string;
  address?: string;
  pricePerHour?: number;
  openTime?: string;
  closeTime?: string;
  description?: string;
  status?: 'active' | 'inactive';
}

