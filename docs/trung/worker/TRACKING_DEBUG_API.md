# Tracking Debug API Documentation

## Overview
The Tracking Debug API provides real-time WebSocket streaming and HTTP endpoints for debugging and monitoring vehicle tracking information. This is designed for development and debugging purposes to inspect the detailed tracking data being processed by the worker.

## Table of Contents
1. [WebSocket Endpoint](#websocket-endpoint)
2. [HTTP Endpoints](#http-endpoints)
3. [Message Formats](#message-formats)
4. [Web UI](#web-ui)
5. [Usage Examples](#usage-examples)

---

## WebSocket Endpoint

### Connect to Debug Stream

**Endpoint:** `ws://localhost:8069/debug/ws/tracking/{camera_id}`

**Description:** Stream real-time tracking information for a specific camera.

**Parameters:**
- `camera_id` (path): Camera identifier (e.g., "CAM1")

**Example:**
```javascript
const ws = new WebSocket('ws://localhost:8069/debug/ws/tracking/CAM1');

ws.onopen = () => {
    console.log('✅ Connected to debug stream');
};

ws.onmessage = (event) => {
    if (event.data === 'keepalive') {
        console.log('💓 Keepalive');
        return;
    }
    
    const message = JSON.parse(event.data);
    console.log('Tracking data:', message);
};

// Send ping to keep connection alive
setInterval(() => {
    if (ws.readyState === WebSocket.OPEN) {
        ws.send('ping');
    }
}, 10000);
```

---

## HTTP Endpoints

### 1. Get Latest Tracking Info

**Endpoint:** `GET /debug/tracking-info/{camera_id}`

**Description:** Retrieve the latest tracking information for a camera (HTTP snapshot).

**Parameters:**
- `camera_id` (path): Camera identifier

**Response:**
```json
{
  "camera_id": "CAM1",
  "timestamp": "2026-01-07T12:30:45.123456",
  "summary": {
    "vehicle_count": 3,
    "occupied_spaces": 2,
    "total_spaces": 4,
    "tracking_enabled": true
  },
  "detections": [
    {
      "class": "car",
      "confidence": 0.87,
      "bbox": [100, 200, 150, 100],
      "track_id": 42,
      "center": [175, 250]
    }
  ],
  "space_occupancy": [
    {
      "space_id": "space_1",
      "space_name": "A1",
      "is_occupied": true,
      "bbox": {
        "x": 0.1,
        "y": 0.2,
        "width": 0.15,
        "height": 0.2
      }
    }
  ],
  "matched_detections": [
    {
      "detection": {
        "class": "car",
        "confidence": 0.87,
        "bbox": [100, 200, 150, 100],
        "track_id": 42
      },
      "space_id": "space_1"
    }
  ],
  "viewer_count": 1
}
```

**cURL Example:**
```bash
curl http://localhost:8069/debug/tracking-info/CAM1
```

---

### 2. Get Active Cameras

**Endpoint:** `GET /debug/active-cameras`

**Description:** List all cameras that have sent tracking data recently.

**Response:**
```json
{
  "active_cameras": [
    {
      "camera_id": "CAM1",
      "last_update": "2026-01-07T12:30:45.123456",
      "vehicle_count": 3,
      "occupied_spaces": 2,
      "total_spaces": 4,
      "tracking_enabled": true,
      "debug_viewers": 1
    }
  ],
  "total_cameras": 1
}
```

**cURL Example:**
```bash
curl http://localhost:8069/debug/active-cameras
```

---

## Message Formats

### WebSocket Message Format

When connected to the debug stream, you'll receive messages in this format:

```json
{
  "type": "tracking_data",
  "camera_id": "CAM1",
  "timestamp": "2026-01-07T12:30:45.123456",
  "data": {
    "summary": {
      "vehicle_count": 3,
      "occupied_spaces": 2,
      "total_spaces": 4,
      "occupancy_rate": 0.5,
      "tracking_enabled": true
    },
    "detections": [
      {
        "class": "car",
        "confidence": 0.87,
        "bbox": [100, 200, 150, 100],
        "track_id": 42,
        "center": [175, 250]
      }
    ],
    "space_occupancy": [
      {
        "space_id": "space_1",
        "space_name": "A1",
        "is_occupied": true,
        "bbox": {
          "x": 0.1,
          "y": 0.2,
          "width": 0.15,
          "height": 0.2
        }
      }
    ],
    "matched_detections": [
      {
        "detection": {
          "class": "car",
          "confidence": 0.87,
          "bbox": [100, 200, 150, 100],
          "track_id": 42
        },
        "space_id": "space_1"
      }
    ],
    "statistics": {
      "vehicles_by_type": {
        "car": 2,
        "motorcycle": 1
      },
      "tracked_vehicle_count": 3,
      "track_ids": [42, 43, 44],
      "occupied_space_names": ["A1", "A2"],
      "available_space_names": ["A3", "A4"]
    }
  }
}
```

### Field Descriptions

#### `summary`
- **`vehicle_count`**: Total number of detected vehicles
- **`occupied_spaces`**: Number of parking spaces with vehicles
- **`total_spaces`**: Total number of parking spaces
- **`occupancy_rate`**: Percentage of occupied spaces (0.0 - 1.0)
- **`tracking_enabled`**: Whether ByteTrack tracking is active

#### `detections`
- **`class`**: Vehicle type ("car", "truck", "bus", "motorcycle")
- **`confidence`**: Detection confidence (0.0 - 1.0)
- **`bbox`**: Bounding box [x, y, width, height] in pixels
- **`track_id`**: Persistent tracking ID (null if tracking disabled)
- **`center`**: Center point [x, y] of the vehicle

#### `space_occupancy`
- **`space_id`**: Unique space identifier
- **`space_name`**: Human-readable name (e.g., "A1")
- **`is_occupied`**: Boolean occupancy status
- **`bbox`**: Normalized coordinates (0.0 - 1.0)

#### `matched_detections`
- **`detection`**: Full detection object with track_id
- **`space_id`**: Which parking space contains this vehicle

#### `statistics`
- **`vehicles_by_type`**: Count of vehicles per type
- **`tracked_vehicle_count`**: Number of vehicles with track IDs
- **`track_ids`**: List of active track IDs
- **`occupied_space_names`**: Names of occupied spaces
- **`available_space_names`**: Names of available spaces

---

## Web UI

### Access the Debug Viewer

**URL:** http://localhost:8069/static/tracking_debug.html

**Features:**
- ✅ Real-time tracking data visualization
- ✅ Vehicle detection list with track IDs
- ✅ Parking space occupancy grid
- ✅ Vehicle-space association viewer
- ✅ Raw JSON data inspector
- ✅ Summary statistics dashboard
- ✅ Occupancy rate progress bar
- ✅ Active track ID badges

**Screenshot Description:**

```
┌─────────────────────────────────────────────────────────┐
│  🔍 Tracking Debug Viewer                               │
│  Real-time tracking information and vehicle detection   │
│  🟢 Connected                                           │
├─────────────────────────────────────────────────────────┤
│  Camera ID: [CAM1        ] [Connect to Debug Stream]   │
├─────────────────────────────────────────────────────────┤
│  📊 Summary Statistics      │  🎯 Active Track IDs     │
│  ┌─────┬─────┬─────┬─────┐ │  #42 #43 #44            │
│  │  3  │ 2/4 │  3  │ ✅  │ │                          │
│  │Veh. │Occ. │Trck │Trck │ │  Occupied Spaces:       │
│  └─────┴─────┴─────┴─────┘ │  • A1 • A2              │
│  Occupancy: [████░░] 50%    │  Available Spaces:      │
│  Vehicles by Type:          │  • A3 • A4              │
│  • car: 2 • motorcycle: 1   │                          │
├─────────────────────────────────────────────────────────┤
│  🚗 Vehicle Detections      │  🅿️ Parking Spaces      │
│  Track #42 - car            │  ┌────┬────┬────┬────┐  │
│  Confidence: 87.0%          │  │ A1 │ A2 │ A3 │ A4 │  │
│  BBox: [100, 200, 150, 100] │  │Occ.│Occ.│Free│Free│  │
│  Center: [175, 250]         │  └────┴────┴────┴────┘  │
├─────────────────────────────────────────────────────────┤
│  🔗 Vehicle-Space Associations                         │
│  Track #42 → space_1 (car, 87.0%)                     │
│  Track #43 → space_2 (car, 92.0%)                     │
├─────────────────────────────────────────────────────────┤
│  📋 Raw JSON Data                                      │
│  {                                                      │
│    "type": "tracking_data",                           │
│    "camera_id": "CAM1",                               │
│    ...                                                 │
│  }                                                      │
└─────────────────────────────────────────────────────────┘
```

---

## Usage Examples

### Python Client Example

```python
import asyncio
import websockets
import json

async def debug_tracking(camera_id):
    uri = f"ws://localhost:8069/debug/ws/tracking/{camera_id}"
    
    async with websockets.connect(uri) as websocket:
        print(f"✅ Connected to debug stream for {camera_id}")
        
        # Send ping every 10 seconds
        async def send_ping():
            while True:
                await asyncio.sleep(10)
                await websocket.send("ping")
        
        # Start ping task
        ping_task = asyncio.create_task(send_ping())
        
        try:
            # Receive messages
            async for message in websocket:
                if message in ['keepalive', 'pong']:
                    print("💓 Keepalive")
                    continue
                
                data = json.loads(message)
                
                if data['type'] == 'tracking_data':
                    print(f"\n📊 Tracking Data Update:")
                    print(f"  Vehicles: {data['data']['summary']['vehicle_count']}")
                    print(f"  Occupied: {data['data']['summary']['occupied_spaces']}/{data['data']['summary']['total_spaces']}")
                    print(f"  Track IDs: {data['data']['statistics']['track_ids']}")
        
        finally:
            ping_task.cancel()

# Run
asyncio.run(debug_tracking("CAM1"))
```

### JavaScript/Node.js Example

```javascript
const WebSocket = require('ws');

function connectDebugStream(cameraId) {
    const ws = new WebSocket(`ws://localhost:8069/debug/ws/tracking/${cameraId}`);
    
    ws.on('open', () => {
        console.log(`✅ Connected to debug stream for ${cameraId}`);
        
        // Send ping every 10 seconds
        setInterval(() => {
            if (ws.readyState === WebSocket.OPEN) {
                ws.send('ping');
            }
        }, 10000);
    });
    
    ws.on('message', (data) => {
        if (data === 'keepalive' || data === 'pong') {
            console.log('💓 Keepalive');
            return;
        }
        
        const message = JSON.parse(data);
        
        if (message.type === 'tracking_data') {
            console.log('\n📊 Tracking Data Update:');
            console.log(`  Vehicles: ${message.data.summary.vehicle_count}`);
            console.log(`  Occupied: ${message.data.summary.occupied_spaces}/${message.data.summary.total_spaces}`);
            console.log(`  Track IDs: ${message.data.statistics.track_ids}`);
        }
    });
    
    ws.on('close', () => {
        console.log('🔌 Connection closed');
    });
    
    ws.on('error', (error) => {
        console.error('❌ Error:', error);
    });
}

// Connect to CAM1
connectDebugStream('CAM1');
```

### cURL Example (HTTP)

```bash
# Get latest tracking info
curl -s http://localhost:8069/debug/tracking-info/CAM1 | jq .

# Get active cameras
curl -s http://localhost:8069/debug/active-cameras | jq .

# Monitor in real-time (using watch command)
watch -n 1 'curl -s http://localhost:8069/debug/tracking-info/CAM1 | jq .summary'
```

### Fetch API (Browser)

```javascript
// Get latest tracking info
async function getTrackingInfo(cameraId) {
    const response = await fetch(`http://localhost:8069/debug/tracking-info/${cameraId}`);
    const data = await response.json();
    
    console.log('📊 Tracking Info:');
    console.log('  Vehicles:', data.summary.vehicle_count);
    console.log('  Occupied:', data.summary.occupied_spaces, '/', data.summary.total_spaces);
    console.log('  Track IDs:', data.detections.map(d => d.track_id));
    
    return data;
}

// Get active cameras
async function getActiveCameras() {
    const response = await fetch('http://localhost:8069/debug/active-cameras');
    const data = await response.json();
    
    console.log('📹 Active Cameras:', data.total_cameras);
    data.active_cameras.forEach(cam => {
        console.log(`  ${cam.camera_id}: ${cam.vehicle_count} vehicles`);
    });
    
    return data;
}

// Usage
getTrackingInfo('CAM1');
getActiveCameras();
```

---

## Integration with Worker

The worker automatically sends tracking data to this debug endpoint when it broadcasts frames. No additional configuration is needed - the debug stream will receive data as soon as the worker starts processing cameras.

**Worker Flow:**
```
Worker → broadcast_frame_to_viewers()
       → HTTP POST to /api/broadcast-detection
       → Broadcasts to regular viewers
       → Broadcasts to debug viewers (tracking data)
```

---

## Use Cases

### 1. Development & Debugging
- Verify tracking IDs are persistent across frames
- Check vehicle detection accuracy
- Debug parking space matching logic
- Monitor ByteTrack performance

### 2. Testing
- Validate tracking data structure
- Test vehicle-space association algorithm
- Verify occupancy calculations
- Check confidence thresholds

### 3. Monitoring
- Real-time system health checks
- Performance metrics (FPS, latency)
- Alert on anomalies
- Track system behavior

### 4. Analytics Development
- Understand data structure for analytics
- Develop business logic with live data
- Test data processing pipelines
- Validate edge cases

---

## Performance Considerations

### WebSocket Connection
- **Bandwidth**: ~5-10 KB per message (JSON)
- **Frequency**: Same as worker FPS (default: 10 FPS)
- **Latency**: < 50ms from worker to debug viewer

### HTTP Polling
- **Recommended**: Only for occasional checks
- **Not Recommended**: Continuous polling (use WebSocket instead)
- **Rate Limit**: No enforced limit, but respect server resources

### Multiple Viewers
- **Supported**: Unlimited debug viewers per camera
- **Performance**: Minimal overhead (<1% CPU per viewer)
- **Memory**: ~1 MB per active debug connection

---

## Troubleshooting

### Connection Issues

**Problem:** Cannot connect to WebSocket

**Solution:**
1. Check FastAPI server is running: `curl http://localhost:8069/health`
2. Verify camera ID is correct
3. Check firewall settings (port 8069)
4. Check browser console for errors

**Problem:** No data received

**Solution:**
1. Verify worker is running: `ps aux | grep parking_monitor_worker`
2. Check worker is processing the camera
3. Verify camera has workerEnabled=true in Firebase
4. Check worker logs for errors

**Problem:** Connection drops frequently

**Solution:**
1. Ensure ping/pong keepalive is working
2. Check network stability
3. Increase timeout values
4. Check server logs for errors

---

## API Reference Summary

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/debug/ws/tracking/{camera_id}` | WebSocket | Stream real-time tracking data |
| `/debug/tracking-info/{camera_id}` | GET | Get latest tracking info (HTTP) |
| `/debug/active-cameras` | GET | List cameras with active tracking |

---

**Last Updated:** January 7, 2026  
**Version:** 1.0  
**Author:** Smart Parking System Team
