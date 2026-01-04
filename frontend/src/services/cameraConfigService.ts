/**
 * Camera Configuration Service
 * Saves and retrieves camera configurations for parking lots
 * This allows users to reuse camera setups with full information (URL, type, etc.)
 */

import { 
  collection, 
  doc, 
  setDoc, 
  getDoc, 
  getDocs, 
  query, 
  where, 
  orderBy, 
  deleteDoc,
  Timestamp 
} from 'firebase/firestore';
import { db } from '../config/firebase';

export interface CameraConfig {
  id: string; // Auto-generated document ID
  ownerId: string;
  parkingLotId: string;
  cameraId: string; // CAM1, ENTRANCE, etc.
  
  // Source configuration
  sourceType: 'esp32' | 'video' | 'rtsp';
  sourceUrl: string; // ESP32 IP, video filename, or RTSP URL
  
  // Optional metadata
  label?: string; // Friendly name
  description?: string;
  
  // Timestamps
  createdAt: Date;
  updatedAt: Date;
  lastUsed?: Date;
}

const COLLECTION_NAME = 'camera_configs';

/**
 * Save or update camera configuration
 */
export async function saveCameraConfig(config: Omit<CameraConfig, 'id' | 'createdAt' | 'updatedAt'>): Promise<{ success: boolean; id?: string; error?: string }> {
  try {
    if (!db) {
      console.error('[CameraConfig] Database not initialized');
      return { success: false, error: 'Database not initialized' };
    }

    console.log('[CameraConfig] Saving camera config:', {
      parkingLotId: config.parkingLotId,
      cameraId: config.cameraId,
      sourceType: config.sourceType,
      sourceUrl: config.sourceUrl
    });

    // Create unique ID based on owner + parking + camera
    const docId = `${config.ownerId}__${config.parkingLotId}__${config.cameraId}`;
    const docRef = doc(db, COLLECTION_NAME, docId);

    // Check if exists
    const existing = await getDoc(docRef);
    
    const data = {
      ...config,
      id: docId,
      updatedAt: Timestamp.now(),
      ...(existing.exists() 
        ? {} 
        : { createdAt: Timestamp.now() }
      )
    };

    await setDoc(docRef, data, { merge: true });

    console.log('[CameraConfig] ✅ Camera config saved successfully:', docId);
    return { success: true, id: docId };
  } catch (error) {
    console.error('[CameraConfig] ❌ Error saving camera config:', error);
    return { success: false, error: String(error) };
  }
}

/**
 * Get camera config by parking lot and camera ID
 */
export async function getCameraConfig(ownerId: string, parkingLotId: string, cameraId: string): Promise<CameraConfig | null> {
  try {
    if (!db) return null;

    const docId = `${ownerId}__${parkingLotId}__${cameraId}`;
    const docRef = doc(db, COLLECTION_NAME, docId);
    const snapshot = await getDoc(docRef);

    if (!snapshot.exists()) return null;

    const data = snapshot.data();
    return {
      ...data,
      id: snapshot.id,
      createdAt: data.createdAt?.toDate() || new Date(),
      updatedAt: data.updatedAt?.toDate() || new Date(),
      lastUsed: data.lastUsed?.toDate(),
    } as CameraConfig;
  } catch (error) {
    console.error('Error getting camera config:', error);
    return null;
  }
}

/**
 * Get all camera configs for a parking lot
 */
export async function getCameraConfigsByParkingLot(ownerId: string, parkingLotId: string): Promise<CameraConfig[]> {
  try {
    if (!db) {
      console.error('[CameraConfig] Database not initialized');
      return [];
    }

    console.log('[CameraConfig] Loading camera configs for:', { ownerId, parkingLotId });

    const q = query(
      collection(db, COLLECTION_NAME),
      where('ownerId', '==', ownerId),
      where('parkingLotId', '==', parkingLotId),
      orderBy('cameraId', 'asc')
    );

    const snapshot = await getDocs(q);
    const configs = snapshot.docs.map(doc => {
      const data = doc.data();
      return {
        ...data,
        id: doc.id,
        createdAt: data.createdAt?.toDate() || new Date(),
        updatedAt: data.updatedAt?.toDate() || new Date(),
        lastUsed: data.lastUsed?.toDate(),
      } as CameraConfig;
    });
    
    console.log('[CameraConfig] ✅ Loaded', configs.length, 'camera configs for parking lot:', configs);
    return configs;
  } catch (error) {
    console.error('[CameraConfig] ❌ Error getting camera configs by parking lot:', error);
    return [];
  }
}

/**
 * Get all camera configs for an owner
 */
export async function getUserCameraConfigs(ownerId: string): Promise<CameraConfig[]> {
  try {
    if (!db) {
      console.error('[CameraConfig] Database not initialized');
      return [];
    }

    console.log('[CameraConfig] Loading all camera configs for owner:', ownerId);

    const q = query(
      collection(db, COLLECTION_NAME),
      where('ownerId', '==', ownerId),
      orderBy('updatedAt', 'desc')
    );

    const snapshot = await getDocs(q);
    const configs = snapshot.docs.map(doc => {
      const data = doc.data();
      return {
        ...data,
        id: doc.id,
        createdAt: data.createdAt?.toDate() || new Date(),
        updatedAt: data.updatedAt?.toDate() || new Date(),
        lastUsed: data.lastUsed?.toDate(),
      } as CameraConfig;
    });
    
    console.log('[CameraConfig] ✅ Loaded', configs.length, 'camera configs:', configs);
    return configs;
  } catch (error) {
    console.error('[CameraConfig] ❌ Error getting user camera configs:', error);
    return [];
  }
}

/**
 * Update last used timestamp
 */
export async function updateCameraLastUsed(ownerId: string, parkingLotId: string, cameraId: string): Promise<void> {
  try {
    if (!db) return;

    const docId = `${ownerId}__${parkingLotId}__${cameraId}`;
    const docRef = doc(db, COLLECTION_NAME, docId);

    await setDoc(docRef, {
      lastUsed: Timestamp.now(),
      updatedAt: Timestamp.now(),
    }, { merge: true });
  } catch (error) {
    console.error('Error updating camera last used:', error);
  }
}

/**
 * Delete camera configuration
 */
export async function deleteCameraConfig(ownerId: string, parkingLotId: string, cameraId: string): Promise<{ success: boolean; error?: string }> {
  try {
    if (!db) {
      return { success: false, error: 'Database not initialized' };
    }

    const docId = `${ownerId}__${parkingLotId}__${cameraId}`;
    const docRef = doc(db, COLLECTION_NAME, docId);

    await deleteDoc(docRef);

    return { success: true };
  } catch (error) {
    console.error('Error deleting camera config:', error);
    return { success: false, error: String(error) };
  }
}

/**
 * Get available camera IDs for a parking lot (unique camera names)
 */
export async function getAvailableCameraIds(ownerId: string, parkingLotId?: string): Promise<string[]> {
  try {
    if (!db) return [];

    let q;
    if (parkingLotId) {
      q = query(
        collection(db, COLLECTION_NAME),
        where('ownerId', '==', ownerId),
        where('parkingLotId', '==', parkingLotId)
      );
    } else {
      q = query(
        collection(db, COLLECTION_NAME),
        where('ownerId', '==', ownerId)
      );
    }

    const snapshot = await getDocs(q);
    const cameraIds = new Set<string>();
    
    snapshot.docs.forEach(doc => {
      const data = doc.data();
      if (data.cameraId) {
        cameraIds.add(data.cameraId);
      }
    });

    return Array.from(cameraIds).sort();
  } catch (error) {
    console.error('Error getting available camera IDs:', error);
    return [];
  }
}
