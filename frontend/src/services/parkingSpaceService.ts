import {
  collection,
  doc,
  setDoc,
  getDoc,
  getDocs,
  deleteDoc,
  query,
  where,
  Timestamp,
} from 'firebase/firestore';
import { db } from '../config/firebase';
import type { ParkingSpaceDefinition } from '../types/parkingLot.types';

const PARKING_SPACE_DEFINITIONS_COLLECTION = 'parkingSpaceDefinitions';

/**
 * Create or update a parking space definition
 */
export async function saveParkingSpace(
  space: Omit<ParkingSpaceDefinition, 'createdAt' | 'updatedAt'>
): Promise<{ success: boolean; error?: string }> {
  try {
    if (!db) {
      throw new Error('Firestore database is not initialized.');
    }

    const docRef = doc(db, PARKING_SPACE_DEFINITIONS_COLLECTION, space.id);
    const existingDoc = await getDoc(docRef);

    const spaceData: ParkingSpaceDefinition = {
      ...space,
      createdAt: existingDoc.exists() 
        ? (existingDoc.data().createdAt as Timestamp) 
        : Timestamp.now(),
      updatedAt: Timestamp.now(),
    };

    await setDoc(docRef, spaceData);
    console.log(`✅ Saved parking space: ${space.id}`);
    return { success: true };
  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : 'Unknown error';
    console.error('❌ Failed to save parking space:', errorMessage);
    return { success: false, error: errorMessage };
  }
}

/**
 * Get all parking spaces for a specific camera
 */
export async function getParkingSpacesByCamera(
  cameraId: string
): Promise<ParkingSpaceDefinition[]> {
  try {
    if (!db) {
      throw new Error('Firestore database is not initialized.');
    }

    const q = query(
      collection(db, PARKING_SPACE_DEFINITIONS_COLLECTION),
      where('cameraId', '==', cameraId)
    );

    const querySnapshot = await getDocs(q);
    const spaces: ParkingSpaceDefinition[] = [];

    querySnapshot.forEach((doc) => {
      spaces.push(doc.data() as ParkingSpaceDefinition);
    });

    return spaces;
  } catch (error) {
    console.error('❌ Failed to get parking spaces:', error);
    return [];
  }
}

/**
 * Get all parking spaces for a parking lot
 */
export async function getParkingSpacesByParkingLot(
  parkingId: string
): Promise<ParkingSpaceDefinition[]> {
  try {
    if (!db) {
      throw new Error('Firestore database is not initialized.');
    }

    const q = query(
      collection(db, PARKING_SPACE_DEFINITIONS_COLLECTION),
      where('parkingId', '==', parkingId)
    );

    const querySnapshot = await getDocs(q);
    const spaces: ParkingSpaceDefinition[] = [];

    querySnapshot.forEach((doc) => {
      spaces.push(doc.data() as ParkingSpaceDefinition);
    });

    return spaces;
  } catch (error) {
    console.error('❌ Failed to get parking spaces:', error);
    return [];
  }
}

/**
 * Delete a parking space
 */
export async function deleteParkingSpace(
  spaceId: string
): Promise<{ success: boolean; error?: string }> {
  try {
    if (!db) {
      throw new Error('Firestore database is not initialized.');
    }

    const docRef = doc(db, PARKING_SPACE_DEFINITIONS_COLLECTION, spaceId);
    await deleteDoc(docRef);
    console.log(`✅ Deleted parking space: ${spaceId}`);
    return { success: true };
  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : 'Unknown error';
    console.error('❌ Failed to delete parking space:', errorMessage);
    return { success: false, error: errorMessage };
  }
}

/**
 * Batch save multiple parking spaces
 */
export async function batchSaveParkingSpaces(
  spaces: Omit<ParkingSpaceDefinition, 'createdAt' | 'updatedAt'>[]
): Promise<{ success: boolean; error?: string; savedCount: number }> {
  try {
    if (!db) {
      throw new Error('Firestore database is not initialized.');
    }

    let savedCount = 0;
    for (const space of spaces) {
      const result = await saveParkingSpace(space);
      if (result.success) {
        savedCount++;
      }
    }

    console.log(`✅ Batch saved ${savedCount}/${spaces.length} parking spaces`);
    return { success: true, savedCount };
  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : 'Unknown error';
    console.error('❌ Failed to batch save parking spaces:', errorMessage);
    return { success: false, error: errorMessage, savedCount: 0 };
  }
}

/**
 * Check if a detection bounding box overlaps with a parking space
 * Uses Intersection over Union (IoU) threshold
 */
export function checkOverlap(
  detectionBox: { x: number; y: number; width: number; height: number },
  parkingSpace: { x: number; y: number; width: number; height: number },
  threshold: number = 0.5
): boolean {
  // Calculate intersection
  const x1 = Math.max(detectionBox.x, parkingSpace.x);
  const y1 = Math.max(detectionBox.y, parkingSpace.y);
  const x2 = Math.min(
    detectionBox.x + detectionBox.width,
    parkingSpace.x + parkingSpace.width
  );
  const y2 = Math.min(
    detectionBox.y + detectionBox.height,
    parkingSpace.y + parkingSpace.height
  );

  const intersectionWidth = Math.max(0, x2 - x1);
  const intersectionHeight = Math.max(0, y2 - y1);
  const intersectionArea = intersectionWidth * intersectionHeight;

  // Calculate union
  const detectionArea = detectionBox.width * detectionBox.height;
  const spaceArea = parkingSpace.width * parkingSpace.height;
  const unionArea = detectionArea + spaceArea - intersectionArea;

  // Calculate IoU
  const iou = intersectionArea / unionArea;

  return iou >= threshold;
}
