import {
  collection,
  addDoc,
  serverTimestamp,
  query,
  where,
  orderBy,
  getDocs,
  doc,
  setDoc,
  getDoc,
  Timestamp,
} from 'firebase/firestore';
import { db } from '../config/firebase';

const CHECKINS_COLLECTION = 'vehicleCheckIns';
const ACTIVE_VEHICLES_COLLECTION = 'activeVehicles';

export interface VehicleCheckIn {
  id: string;
  vehicleId: string;
  licensePlate: string;
  parkingId: string;
  cameraId: string;
  ownerId: string;
  entryImage?: string;
  checkInTime: Date;
  createdAt: Timestamp;
}

export interface ActiveVehicle {
  vehicleId: string;
  licensePlate: string;
  parkingId: string;
  checkInCameraId: string; // Cam1
  checkInTime: Timestamp;
  status: 'checking_in' | 'tracking' | 'parked' | 'exited';
  parkedSpaceId?: string;
  parkedCameraId?: string;
  lastSeen: Timestamp;
  createdAt: Timestamp;
}

export interface CreateVehicleCheckInPayload {
  licensePlate: string;
  parkingId: string;
  cameraId: string;
  ownerId: string;
  entryImage?: string;
}

/**
 * Generate Vehicle ID format: VEH-{timestamp}-{plate}
 * Example: VEH-1736078400-30A12345
 */
export function generateVehicleId(licensePlate: string): string {
  const timestamp = Math.floor(Date.now() / 1000);
  const cleanPlate = licensePlate.replace(/[^A-Z0-9]/g, '').toUpperCase();
  return `VEH-${timestamp}-${cleanPlate}`;
}

/**
 * Create vehicle check-in record
 */
export async function createVehicleCheckIn(
  payload: CreateVehicleCheckInPayload
): Promise<{ success: boolean; vehicleId?: string; error?: string }> {
  try {
    if (!db) {
      throw new Error('Firestore database is not initialized.');
    }

    const vehicleId = generateVehicleId(payload.licensePlate);
    const checkInTime = Timestamp.now();

    // Create check-in record
    const checkInData = {
      vehicleId,
      licensePlate: payload.licensePlate,
      parkingId: payload.parkingId,
      cameraId: payload.cameraId,
      ownerId: payload.ownerId,
      entryImage: payload.entryImage || null,
      checkInTime,
      createdAt: serverTimestamp(),
    };

    const checkInRef = await addDoc(collection(db, CHECKINS_COLLECTION), checkInData);

    // Create active vehicle record
    const activeVehicleData: Omit<ActiveVehicle, 'createdAt'> & { createdAt: any } = {
      vehicleId,
      licensePlate: payload.licensePlate,
      parkingId: payload.parkingId,
      checkInCameraId: payload.cameraId,
      checkInTime,
      status: 'tracking',
      lastSeen: checkInTime,
      createdAt: serverTimestamp(),
    };

    await setDoc(doc(db, ACTIVE_VEHICLES_COLLECTION, vehicleId), activeVehicleData);

    console.log(`✅ Vehicle check-in created: ${vehicleId}`);
    return { success: true, vehicleId };
  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : 'Unknown error';
    console.error('❌ Failed to create vehicle check-in:', errorMessage);
    return { success: false, error: errorMessage };
  }
}

/**
 * Get active vehicle by ID
 */
export async function getActiveVehicle(
  vehicleId: string
): Promise<ActiveVehicle | null> {
  try {
    if (!db) {
      throw new Error('Firestore database is not initialized.');
    }

    const docRef = doc(db, ACTIVE_VEHICLES_COLLECTION, vehicleId);
    const docSnap = await getDoc(docRef);

    if (!docSnap.exists()) {
      return null;
    }

    return docSnap.data() as ActiveVehicle;
  } catch (error) {
    console.error('❌ Failed to get active vehicle:', error);
    return null;
  }
}

/**
 * Get all active vehicles for a parking lot
 */
export async function getActiveVehiclesByParking(
  parkingId: string
): Promise<ActiveVehicle[]> {
  try {
    if (!db) {
      throw new Error('Firestore database is not initialized.');
    }

    const q = query(
      collection(db, ACTIVE_VEHICLES_COLLECTION),
      where('parkingId', '==', parkingId),
      where('status', 'in', ['tracking', 'parked']),
      orderBy('checkInTime', 'desc')
    );

    const querySnapshot = await getDocs(q);
    return querySnapshot.docs.map((doc) => doc.data() as ActiveVehicle);
  } catch (error) {
    console.error('❌ Failed to get active vehicles:', error);
    return [];
  }
}

/**
 * Update active vehicle status
 */
export async function updateActiveVehicleStatus(
  vehicleId: string,
  updates: Partial<ActiveVehicle>
): Promise<{ success: boolean; error?: string }> {
  try {
    if (!db) {
      throw new Error('Firestore database is not initialized.');
    }

    const docRef = doc(db, ACTIVE_VEHICLES_COLLECTION, vehicleId);
    
    await setDoc(
      docRef,
      {
        ...updates,
        lastSeen: serverTimestamp(),
      },
      { merge: true }
    );

    return { success: true };
  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : 'Unknown error';
    console.error('❌ Failed to update active vehicle:', errorMessage);
    return { success: false, error: errorMessage };
  }
}

