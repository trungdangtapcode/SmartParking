# Parking Monitor Worker Control

## Overview

The parking monitor worker can be enabled/disabled per camera using the `workerEnabled` field. By default, worker monitoring is disabled (`workerEnabled: false`) for all cameras to conserve resources.

## Backend Implementation

### Worker Filtering Logic

The worker in `server/parking_monitor_worker.py` checks the `workerEnabled` field:

```python
async def get_active_cameras(self) -> List[Dict]:
    # ... query parking lots and cameras ...
    
    # Check if worker is enabled for this camera
    worker_enabled = camera_data.get('workerEnabled', False)
    if not worker_enabled:
        logger.debug(f"Skipping camera with worker disabled: {camera_name}")
        continue
    
    logger.info(f"Found worker-enabled camera: {camera_name}")
    # ... process camera ...
```

**Key Points:**
- Default: `False` (worker disabled)
- Only cameras with `workerEnabled: true` are processed
- Checked on every monitoring loop iteration
- Changes take effect within next check interval (default 5 seconds)

## Frontend Implementation

### Service Functions

Located in `frontend/src/services/esp32ConfigService.ts`:

#### 1. Enable Worker

```typescript
import { enableWorkerForCamera } from '../services/esp32ConfigService';

await enableWorkerForCamera(configId);
```

#### 2. Disable Worker

```typescript
import { disableWorkerForCamera } from '../services/esp32ConfigService';

await disableWorkerForCamera(configId);
```

#### 3. Toggle Worker (Recommended)

```typescript
import { toggleWorkerForCamera } from '../services/esp32ConfigService';

// Enable
await toggleWorkerForCamera(configId, true);

// Disable
await toggleWorkerForCamera(configId, false);
```

## Adding UI Controls

### Example: Toggle Switch in Camera Config

```tsx
import { useState } from 'react';
import { toggleWorkerForCamera } from '../services/esp32ConfigService';
import type { ESP32Config } from '../services/esp32ConfigService';

interface CameraCardProps {
  config: ESP32Config;
  onUpdate: () => void;
}

function CameraCard({ config, onUpdate }: CameraCardProps) {
  const [isUpdating, setIsUpdating] = useState(false);
  const workerEnabled = config.workerEnabled ?? false;

  const handleToggleWorker = async () => {
    setIsUpdating(true);
    try {
      await toggleWorkerForCamera(config.id, !workerEnabled);
      onUpdate(); // Refresh parent component
    } catch (error) {
      console.error('Failed to toggle worker:', error);
      alert('Failed to update worker status');
    } finally {
      setIsUpdating(false);
    }
  };

  return (
    <div className="border rounded-lg p-4">
      <h3>{config.name}</h3>
      <p className="text-sm text-gray-600">{config.ipAddress}</p>
      
      <div className="mt-4 flex items-center justify-between">
        <span className="text-sm">Background Monitoring</span>
        <button
          onClick={handleToggleWorker}
          disabled={isUpdating}
          className={`px-4 py-2 rounded ${
            workerEnabled
              ? 'bg-green-500 text-white'
              : 'bg-gray-300 text-gray-700'
          }`}
        >
          {isUpdating ? 'Updating...' : workerEnabled ? 'Enabled' : 'Disabled'}
        </button>
      </div>
      
      {/* Worker Status Indicator */}
      {workerEnabled && (
        <div className="mt-2 flex items-center text-sm text-green-600">
          <span className="mr-2">●</span>
          <span>Worker Active</span>
        </div>
      )}
    </div>
  );
}
```

### Example: Checkbox in Settings Page

```tsx
import { useState, useEffect } from 'react';
import { getUserESP32Configs, toggleWorkerForCamera } from '../services/esp32ConfigService';
import { useAuth } from '../context/AuthContext';

function CameraSettingsPage() {
  const { user } = useAuth();
  const [cameras, setCameras] = useState<ESP32Config[]>([]);

  useEffect(() => {
    loadCameras();
  }, [user]);

  const loadCameras = async () => {
    if (!user) return;
    const configs = await getUserESP32Configs(user.uid);
    setCameras(configs);
  };

  const handleWorkerToggle = async (configId: string, enabled: boolean) => {
    try {
      await toggleWorkerForCamera(configId, enabled);
      await loadCameras(); // Refresh
    } catch (error) {
      console.error('Failed to toggle worker:', error);
    }
  };

  return (
    <div className="p-6">
      <h1 className="text-2xl font-bold mb-6">Camera Worker Settings</h1>
      
      <div className="space-y-4">
        {cameras.map((camera) => (
          <div key={camera.id} className="flex items-center justify-between p-4 border rounded">
            <div>
              <h3 className="font-semibold">{camera.name}</h3>
              <p className="text-sm text-gray-600">{camera.ipAddress}</p>
            </div>
            
            <label className="flex items-center cursor-pointer">
              <span className="mr-3 text-sm">Enable Monitoring</span>
              <input
                type="checkbox"
                checked={camera.workerEnabled ?? false}
                onChange={(e) => handleWorkerToggle(camera.id, e.target.checked)}
                className="w-5 h-5"
              />
            </label>
          </div>
        ))}
      </div>
    </div>
  );
}
```

## Database Schema

### Firestore: `esp32_configs` Collection

```typescript
{
  id: string;                    // Document ID
  userId: string;                // Owner user ID
  name: string;                  // Camera name
  ipAddress: string;             // Camera URL
  createdAt: Timestamp;
  updatedAt: Timestamp;
  isDefault?: boolean;           // Default camera flag
  workerEnabled?: boolean;       // Worker monitoring flag (default: false)
}
```

## Resource Management

### When to Enable Worker

✅ **Enable worker when:**
- Camera monitors high-traffic parking area
- Real-time occupancy updates needed
- During business hours
- Camera is stable and reliable

❌ **Disable worker when:**
- Camera is for testing/development
- Outside business hours (overnight)
- Camera is unreliable/offline frequently
- To save GPU/CPU resources

### Performance Considerations

- Each enabled camera consumes:
  - Network bandwidth (fetching frames)
  - GPU resources (YOLO detection)
  - CPU resources (image decoding, IoU matching)
  - Firebase write operations
  
- Recommended limits:
  - < 10 cameras: Enable all if needed
  - 10-20 cameras: Enable selectively
  - > 20 cameras: Use multiple worker instances with load balancing

## Testing Worker Control

### 1. Enable Worker via UI

```bash
# Watch worker logs
cd server
conda activate smartparking
python parking_monitor_worker.py --interval 5 --log-level DEBUG
```

### 2. Check Logs

**Worker Disabled:**
```
DEBUG - Skipping camera with worker disabled: Front Gate Camera
```

**Worker Enabled:**
```
INFO - Found worker-enabled camera: Front Gate Camera
INFO - Processing camera: http://192.168.1.100:81
DEBUG - Fetched 48531 bytes from camera
INFO - ✅ Updated occupancy for camera: 0/4 occupied
```

### 3. Verify Firebase Updates

Check `parkingSpaces` collection for occupancy updates:
- `occupied: true/false`
- `lastChecked: Timestamp`
- `vehicleDetected: {...}` (if occupied)

## Environment Variables

Configure worker behavior in `server/.env`:

```bash
# Enable/disable entire worker system
ENABLE_PARKING_MONITOR=true

# Check interval in seconds
MONITOR_CHECK_INTERVAL=5

# YOLO model path
YOLO_MODEL_PATH=yolov8s_car_custom.pt

# IoU threshold for matching
IOU_THRESHOLD=0.5
```

## Troubleshooting

### Worker Not Processing Camera

**Problem:** Worker ignores camera even with `workerEnabled: true`

**Solutions:**
1. Check worker logs for "Found worker-enabled camera" message
2. Verify camera exists in a parking lot with `status: 'active'`
3. Check Firebase `esp32_configs` document has `workerEnabled: true`
4. Restart worker service

### UI Toggle Not Working

**Problem:** Clicking toggle doesn't update worker status

**Solutions:**
1. Check browser console for errors
2. Verify user has permission to update `esp32_configs`
3. Check Firebase Rules allow updates
4. Verify `configId` is correct

### Worker Processes Wrong Cameras

**Problem:** Worker processes cameras that should be disabled

**Solutions:**
1. Clear browser cache and refresh
2. Check worker is reading latest Firestore data
3. Verify `workerEnabled` field exists in database
4. Check default value handling (`camera_data.get('workerEnabled', False)`)

## Best Practices

1. **Default Disabled**: Always create cameras with `workerEnabled: false`
2. **Selective Enabling**: Only enable worker for production cameras
3. **Resource Monitoring**: Monitor CPU/GPU usage when enabling multiple cameras
4. **Gradual Rollout**: Enable 1-2 cameras at a time to test performance
5. **User Feedback**: Show worker status clearly in UI
6. **Logging**: Use DEBUG level to track worker decisions
7. **Graceful Degradation**: Worker should handle camera failures without crashing

## Related Documentation

- [PARKING_MONITOR_WORKER.md](./PARKING_MONITOR_WORKER.md) - Full worker documentation
- [PARKING_SPACE_EDITOR.md](./PARKING_SPACE_EDITOR.md) - How to define parking spaces
- [PARKING_SPACE_INTEGRATION.md](./PARKING_SPACE_INTEGRATION.md) - Integration guide
