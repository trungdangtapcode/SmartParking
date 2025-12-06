import {
  collection,
  doc,
  setDoc,
  getDoc,
  getDocs,
  updateDoc,
  deleteDoc,
  query,
  where,
  Timestamp,
  arrayUnion,
  arrayRemove,
  increment,
} from 'firebase/firestore';
import { db } from '../config/firebase';
import type {
  ParkingLot,
  CreateParkingLotInput,
  UpdateParkingLotInput,
} from '../types/parkingLot.types';

const PARKING_LOTS_COLLECTION = 'parkingLots';
const DETECTIONS_COLLECTION = 'detections';

/**
 * Create a new parking lot
 */
export async function createParkingLot(
  input: CreateParkingLotInput
): Promise<{ success: boolean; error?: string }> {
  try {
    if (!db) {
      throw new Error('Firestore database is not initialized.');
    }

    // Check if parking lot already exists
    const docRef = doc(db, PARKING_LOTS_COLLECTION, input.id);
    const existingDoc = await getDoc(docRef);
    
    if (existingDoc.exists()) {
      return { success: false, error: 'Parking lot ID already exists' };
    }

    const parkingLot: ParkingLot = {
      id: input.id,
      name: input.name,
      address: input.address,
      ownerId: input.ownerId,
      totalSpaces: 0,
      availableSpaces: 0,
      occupiedSpaces: 0,
      cameras: [],
      status: 'active',
      createdAt: Timestamp.now(),
      updatedAt: Timestamp.now(),
      pricePerHour: input.pricePerHour,
      openTime: input.openTime,
      closeTime: input.closeTime,
      description: input.description,
    };

    await setDoc(docRef, parkingLot);
    console.log(`✅ Created parking lot: ${input.id}`);
    return { success: true };
  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : 'Unknown error';
    console.error('❌ Failed to create parking lot:', errorMessage);
    return { success: false, error: errorMessage };
  }
}

/**
 * Get parking lot by ID
 */
export async function getParkingLot(
  parkingId: string
): Promise<ParkingLot | null> {
  try {
    if (!db) {
      throw new Error('Firestore database is not initialized.');
    }

    const docRef = doc(db, PARKING_LOTS_COLLECTION, parkingId);
    const docSnap = await getDoc(docRef);

    if (!docSnap.exists()) {
      return null;
    }

    return docSnap.data() as ParkingLot;
  } catch (error) {
    console.error('❌ Failed to get parking lot:', error);
    return null;
  }
}

/**
 * Get all parking lots for an owner
 */
export async function getParkingLotsByOwner(
  ownerId: string
): Promise<ParkingLot[]> {
  try {
    if (!db) {
      throw new Error('Firestore database is not initialized.');
    }

    const q = query(
      collection(db, PARKING_LOTS_COLLECTION),
      where('ownerId', '==', ownerId)
    );
    const querySnapshot = await getDocs(q);

    return querySnapshot.docs.map(doc => doc.data() as ParkingLot);
  } catch (error) {
    console.error('❌ Failed to get parking lots:', error);
    return [];
  }
}

/**
 * Update parking lot info
 */
export async function updateParkingLot(
  parkingId: string,
  input: UpdateParkingLotInput
): Promise<{ success: boolean; error?: string }> {
  try {
    if (!db) {
      throw new Error('Firestore database is not initialized.');
    }

    const docRef = doc(db, PARKING_LOTS_COLLECTION, parkingId);
    const updates: any = {
      ...input,
      updatedAt: Timestamp.now(),
    };

    await updateDoc(docRef, updates);
    console.log(`✅ Updated parking lot: ${parkingId}`);
    return { success: true };
  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : 'Unknown error';
    console.error('❌ Failed to update parking lot:', errorMessage);
    return { success: false, error: errorMessage };
  }
}

/**
 * Delete parking lot
 */
export async function deleteParkingLot(
  parkingId: string
): Promise<{ success: boolean; error?: string }> {
  try {
    if (!db) {
      throw new Error('Firestore database is not initialized.');
    }

    await deleteDoc(doc(db, PARKING_LOTS_COLLECTION, parkingId));
    console.log(`✅ Deleted parking lot: ${parkingId}`);
    return { success: true };
  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : 'Unknown error';
    console.error('❌ Failed to delete parking lot:', errorMessage);
    return { success: false, error: errorMessage };
  }
}

/**
 * Add camera to parking lot
 */
export async function addCameraToParkingLot(
  parkingId: string,
  cameraId: string
): Promise<{ success: boolean; error?: string }> {
  try {
    if (!db) {
      throw new Error('Firestore database is not initialized.');
    }

    const docRef = doc(db, PARKING_LOTS_COLLECTION, parkingId);
    await updateDoc(docRef, {
      cameras: arrayUnion(cameraId),
      updatedAt: Timestamp.now(),
    });

    console.log(`✅ Added camera ${cameraId} to parking lot ${parkingId}`);
    return { success: true };
  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : 'Unknown error';
    console.error('❌ Failed to add camera:', errorMessage);
    return { success: false, error: errorMessage };
  }
}

/**
 * Remove camera from parking lot
 */
export async function removeCameraFromParkingLot(
  parkingId: string,
  cameraId: string
): Promise<{ success: boolean; error?: string }> {
  try {
    if (!db) {
      throw new Error('Firestore database is not initialized.');
    }

    const docRef = doc(db, PARKING_LOTS_COLLECTION, parkingId);
    await updateDoc(docRef, {
      cameras: arrayRemove(cameraId),
      updatedAt: Timestamp.now(),
    });

    console.log(`✅ Removed camera ${cameraId} from parking lot ${parkingId}`);
    return { success: true };
  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : 'Unknown error';
    console.error('❌ Failed to remove camera:', errorMessage);
    return { success: false, error: errorMessage };
  }
}

/**
 * Calculate and update total spaces for a parking lot
 * Aggregate từ tất cả cameras trong bãi
 */
export async function updateTotalSpaces(
  parkingId: string,
  ownerId: string
): Promise<{ success: boolean; totalSpaces: number; error?: string }> {
  try {
    if (!db) {
      throw new Error('Firestore database is not initialized.');
    }

    // Get parking lot
    const parkingLot = await getParkingLot(parkingId);
    if (!parkingLot) {
      return { success: false, totalSpaces: 0, error: 'Parking lot not found' };
    }

    // Sum spaces from all cameras
    let totalSpaces = 0;
    for (const cameraId of parkingLot.cameras) {
      const detectionDocId = `${ownerId}__${cameraId}`;
      const detectionDoc = await getDoc(doc(db, DETECTIONS_COLLECTION, detectionDocId));
      
      if (detectionDoc.exists()) {
        const data = detectionDoc.data();
        totalSpaces += data.spaceCount || 0;
      }
    }

    // Update parking lot
    await updateDoc(doc(db, PARKING_LOTS_COLLECTION, parkingId), {
      totalSpaces,
      availableSpaces: totalSpaces, // Reset to total (assuming all empty initially)
      occupiedSpaces: 0,
      updatedAt: Timestamp.now(),
    });

    console.log(`✅ Updated total spaces for ${parkingId}: ${totalSpaces}`);
    return { success: true, totalSpaces };
  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : 'Unknown error';
    console.error('❌ Failed to update total spaces:', errorMessage);
    return { success: false, totalSpaces: 0, error: errorMessage };
  }
}

/**
 * Update occupancy (called by tracking system)
 * Increase or decrease occupied/available counts
 */
export async function updateOccupancy(
  parkingId: string,
  occupied: boolean
): Promise<{ success: boolean; error?: string }> {
  try {
    if (!db) {
      throw new Error('Firestore database is not initialized.');
    }

    const docRef = doc(db, PARKING_LOTS_COLLECTION, parkingId);
    
    if (occupied) {
      // Xe vào → Tăng occupied, giảm available
      await updateDoc(docRef, {
        occupiedSpaces: increment(1),
        availableSpaces: increment(-1),
        updatedAt: Timestamp.now(),
      });
    } else {
      // Xe ra → Giảm occupied, tăng available
      await updateDoc(docRef, {
        occupiedSpaces: increment(-1),
        availableSpaces: increment(1),
        updatedAt: Timestamp.now(),
      });
    }

    console.log(`✅ Updated occupancy for ${parkingId}: occupied=${occupied}`);
    return { success: true };
  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : 'Unknown error';
    console.error('❌ Failed to update occupancy:', errorMessage);
    return { success: false, error: errorMessage };
  }
}

/**
 * Get parking lot statistics
 */
export async function getParkingLotStats(parkingId: string) {
  const parkingLot = await getParkingLot(parkingId);
  if (!parkingLot) return null;

  const occupancyRate = parkingLot.totalSpaces > 0
    ? (parkingLot.occupiedSpaces / parkingLot.totalSpaces) * 100
    : 0;

  return {
    totalSpaces: parkingLot.totalSpaces,
    availableSpaces: parkingLot.availableSpaces,
    occupiedSpaces: parkingLot.occupiedSpaces,
    occupancyRate: Math.round(occupancyRate * 10) / 10, // Round to 1 decimal
    cameras: parkingLot.cameras.length,
    status: parkingLot.status,
  };
}

