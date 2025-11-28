import type { Detection } from '../services/ai/aiDetection';

export type BoundingBox = [number, number, number, number];

export interface CameraParkingRule {
  cameraId: string;
  allowedZones?: BoundingBox[];
  restrictedZones?: BoundingBox[];
  tolerance?: number; // IoU threshold để xem như hợp lệ
}

const createBox = (x: number, y: number, width: number, height: number): BoundingBox => [x, y, width, height];

export const CAMERA_PARKING_RULES: CameraParkingRule[] = [
  {
    cameraId: 'CAM_001',
    tolerance: 0.35,
    allowedZones: [
      createBox(80, 140, 160, 300),
      createBox(260, 140, 160, 300),
      createBox(440, 140, 160, 300),
      createBox(620, 140, 160, 300),
    ],
    restrictedZones: [
      createBox(0, 0, 120, 110), // lối đi bộ
      createBox(650, 0, 170, 120), // khu vực cổng
    ],
  },
  {
    cameraId: 'CAM_002',
    tolerance: 0.3,
    allowedZones: [
      createBox(120, 80, 180, 260),
      createBox(320, 80, 180, 260),
      createBox(520, 80, 180, 260),
    ],
    restrictedZones: [
      createBox(0, 360, 800, 120), // đường nội bộ
    ],
  },
];

export function getParkingRule(cameraId: string): CameraParkingRule | undefined {
  return CAMERA_PARKING_RULES.find((rule) => rule.cameraId === cameraId);
}

const calculateIoU = (boxA: BoundingBox, boxB: BoundingBox): number => {
  const [ax, ay, aw, ah] = boxA;
  const [bx, by, bw, bh] = boxB;

  const x1 = Math.max(ax, bx);
  const y1 = Math.max(ay, by);
  const x2 = Math.min(ax + aw, bx + bw);
  const y2 = Math.min(ay + ah, by + bh);

  const intersectionWidth = Math.max(0, x2 - x1);
  const intersectionHeight = Math.max(0, y2 - y1);
  const intersectionArea = intersectionWidth * intersectionHeight;

  const areaA = aw * ah;
  const areaB = bw * bh;

  const unionArea = areaA + areaB - intersectionArea;
  if (unionArea === 0) {
    return 0;
  }
  return intersectionArea / unionArea;
};

export interface ParkingViolation {
  cameraId: string;
  vehicleBox: BoundingBox;
  violationType: 'OUT_OF_ZONE' | 'RESTRICTED_ZONE';
  message: string;
}

export function detectParkingViolations(
  cameraId: string,
  vehicles: Detection[],
): ParkingViolation[] {
  const rule = getParkingRule(cameraId);
  if (!rule || vehicles.length === 0) {
    return [];
  }

  const violations: ParkingViolation[] = [];
  const tolerance = rule.tolerance ?? 0.35;

  vehicles.forEach((vehicle, index) => {
    const bbox = vehicle.bbox;
    const intersectsRestricted = rule.restrictedZones?.some((zone) => calculateIoU(bbox, zone) > 0.2);

    if (intersectsRestricted) {
      violations.push({
        cameraId,
        vehicleBox: bbox,
        violationType: 'RESTRICTED_ZONE',
        message: `Vehicle #${index + 1} detected inside restricted area`,
      });
      return;
    }

    if (rule.allowedZones && rule.allowedZones.length > 0) {
      const matchesAllowed = rule.allowedZones.some((zone) => calculateIoU(bbox, zone) >= tolerance);
      if (!matchesAllowed) {
        violations.push({
          cameraId,
          vehicleBox: bbox,
          violationType: 'OUT_OF_ZONE',
          message: `Vehicle #${index + 1} does not align with any parking slot (IoU < ${tolerance})`,
        });
      }
    }
  });

  return violations;
}

