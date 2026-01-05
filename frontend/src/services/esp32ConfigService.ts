import { db } from '../config/firebase';
import { doc, setDoc, collection, query, where, getDocs, deleteDoc } from 'firebase/firestore';

export interface ESP32Config {
  id: string;
  userId: string;
  name: string; // User-friendly name for the ESP32
  ipAddress: string; // ESP32 IP (e.g., "192.168.1.100:81" or "http://192.168.1.100:81")
  createdAt: Date;
  updatedAt: Date;
  isDefault?: boolean; // Mark as default ESP32
  workerEnabled?: boolean; // Enable background worker monitoring for this camera
}

/**
 * Save ESP32 configuration to Firebase
 */
export async function saveESP32Config(
  userId: string,
  name: string,
  ipAddress: string,
  isDefault: boolean = false
): Promise<ESP32Config> {
  try {
    // Normalize IP address (ensure it has protocol)
    const normalizedIP = ipAddress.startsWith('http') ? ipAddress : `http://${ipAddress}`;
    
    // Create document ID from userId and IP
    const configId = `${userId}_${Date.now()}`;
    
    const config: ESP32Config = {
      id: configId,
      userId,
      name,
      ipAddress: normalizedIP,
      createdAt: new Date(),
      updatedAt: new Date(),
      isDefault,
    };
    
    // Save to Firestore
    await setDoc(doc(db, 'esp32_configs', configId), {
      ...config,
      createdAt: config.createdAt.toISOString(),
      updatedAt: config.updatedAt.toISOString(),
    });
    
    console.log('✅ ESP32 config saved:', config);
    return config;
  } catch (error) {
    console.error('❌ Error saving ESP32 config:', error);
    throw error;
  }
}

/**
 * Get all ESP32 configurations for a user
 */
export async function getUserESP32Configs(userId: string): Promise<ESP32Config[]> {
  try {
    const q = query(
      collection(db, 'esp32_configs'),
      where('userId', '==', userId)
    );
    
    const snapshot = await getDocs(q);
    const configs: ESP32Config[] = [];
    
    snapshot.forEach((doc) => {
      const data = doc.data();
      configs.push({
        id: doc.id,
        userId: data.userId,
        name: data.name,
        ipAddress: data.ipAddress,
        createdAt: new Date(data.createdAt),
        updatedAt: new Date(data.updatedAt),
        isDefault: data.isDefault || false,
        workerEnabled: data.workerEnabled || false,
      });
    });
    
    // Sort by createdAt (newest first)
    configs.sort((a, b) => b.createdAt.getTime() - a.createdAt.getTime());
    
    console.log(`✅ Loaded ${configs.length} ESP32 configs for user ${userId}`);
    return configs;
  } catch (error) {
    console.error('❌ Error loading ESP32 configs:', error);
    return [];
  }
}

/**
 * Get default ESP32 configuration for a user
 */
export async function getDefaultESP32Config(userId: string): Promise<ESP32Config | null> {
  try {
    const configs = await getUserESP32Configs(userId);
    const defaultConfig = configs.find(c => c.isDefault);
    
    if (defaultConfig) {
      console.log('✅ Found default ESP32 config:', defaultConfig);
      return defaultConfig;
    }
    
    // If no default, return the most recent one
    if (configs.length > 0) {
      console.log('✅ Using most recent ESP32 config as default:', configs[0]);
      return configs[0];
    }
    
    return null;
  } catch (error) {
    console.error('❌ Error getting default ESP32 config:', error);
    return null;
  }
}

/**
 * Update ESP32 configuration
 */
export async function updateESP32Config(
  configId: string,
  updates: Partial<Omit<ESP32Config, 'id' | 'userId' | 'createdAt'>>
): Promise<void> {
  try {
    const docRef = doc(db, 'esp32_configs', configId);
    
    await setDoc(docRef, {
      ...updates,
      updatedAt: new Date().toISOString(),
    }, { merge: true });
    
    console.log('✅ ESP32 config updated:', configId);
  } catch (error) {
    console.error('❌ Error updating ESP32 config:', error);
    throw error;
  }
}

/**
 * Delete ESP32 configuration
 */
export async function deleteESP32Config(configId: string): Promise<void> {
  try {
    await deleteDoc(doc(db, 'esp32_configs', configId));
    console.log('✅ ESP32 config deleted:', configId);
  } catch (error) {
    console.error('❌ Error deleting ESP32 config:', error);
    throw error;
  }
}

/**
 * Set ESP32 as default (unset all others)
 */
export async function setDefaultESP32(userId: string, configId: string): Promise<void> {
  try {
    // Get all configs for user
    const configs = await getUserESP32Configs(userId);
    
    // Update all configs
    const promises = configs.map(config => {
      return updateESP32Config(config.id, {
        isDefault: config.id === configId,
      });
    });
    
    await Promise.all(promises);
    console.log('✅ Default ESP32 set:', configId);
  } catch (error) {
    console.error('❌ Error setting default ESP32:', error);
    throw error;
  }
}

/**
 * Enable worker monitoring for a camera
 */
export async function enableWorkerForCamera(configId: string): Promise<void> {
  try {
    await updateESP32Config(configId, { workerEnabled: true });
    console.log('✅ Worker enabled for camera:', configId);
  } catch (error) {
    console.error('❌ Error enabling worker:', error);
    throw error;
  }
}

/**
 * Disable worker monitoring for a camera
 */
export async function disableWorkerForCamera(configId: string): Promise<void> {
  try {
    await updateESP32Config(configId, { workerEnabled: false });
    console.log('✅ Worker disabled for camera:', configId);
  } catch (error) {
    console.error('❌ Error disabling worker:', error);
    throw error;
  }
}

/**
 * Toggle worker status for a camera
 */
export async function toggleWorkerForCamera(configId: string, enabled: boolean): Promise<void> {
  try {
    await updateESP32Config(configId, { workerEnabled: enabled });
    console.log(`✅ Worker ${enabled ? 'enabled' : 'disabled'} for camera:`, configId);
  } catch (error) {
    console.error('❌ Error toggling worker:', error);
    throw error;
  }
}
