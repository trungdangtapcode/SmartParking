# Parking Monitor Worker

A background service that continuously monitors active cameras and updates parking space occupancy in real-time.

## 🎯 What It Does

The Parking Monitor Worker:

1. **Discovers Active Cameras** - Queries Firebase for parking lots and their cameras
2. **Fetches Camera Frames** - Gets snapshots from each camera every few seconds
3. **Detects Vehicles** - Runs YOLO detection on each frame
4. **Matches to Parking Spaces** - Uses IoU algorithm to match detections to defined spaces
5. **Updates Firebase** - Writes occupancy status to Firestore in real-time

## 🚀 Quick Start

### Option 1: Run as Standalone Worker

```bash
# From server directory
cd /mnt/mmlab2024nas/vund/.svn/bin/server

# Activate conda environment
conda activate scheduler

# Run worker (checks every 5 seconds)
python parking_monitor_worker.py --interval 5
```

### Option 2: Integrated with FastAPI Server

The worker is automatically started when you run the main FastAPI server:

```bash
# Set environment variable
export ENABLE_PARKING_MONITOR=true
export MONITOR_CHECK_INTERVAL=5

# Start server (worker starts automatically)
python main_fastapi.py
```

Or disable it:
```bash
export ENABLE_PARKING_MONITOR=false
python main_fastapi.py
```

### Option 3: Using Shell Script

```bash
# Make script executable
chmod +x start_worker.sh

# Run worker
./start_worker.sh
```

## ⚙️ Configuration

### Command Line Arguments

```bash
python parking_monitor_worker.py --help
```

Options:
- `--interval` - Check interval in seconds (default: 5)
- `--detection-url` - FastAPI server URL (default: http://localhost:8069)

### Environment Variables

Set in `.env` file or export:

```bash
# Enable/disable worker when running with FastAPI
ENABLE_PARKING_MONITOR=true

# Check interval in seconds
MONITOR_CHECK_INTERVAL=5

# ESP32 camera URL (for standalone worker)
ESP32_URL=http://localhost:5069
```

## 📊 How It Works

### 1. Discovery Phase

```
Firebase (parkingLots) → Get active parking lots
    ↓
For each parking lot:
    Get camera IDs from 'cameras' array
    ↓
Firebase (esp32_configs) → Get camera IP addresses
    ↓
Return list of active cameras
```

### 2. Monitoring Loop

```
For each active camera:
    ↓
Fetch camera frame (/capture endpoint)
    ↓
Run YOLO detection
    ↓
Filter vehicles only (car, truck, bus, motorcycle)
    ↓
Load parking space definitions from Firebase
    ↓
Match detections to spaces (IoU algorithm)
    ↓
Update occupancy in Firebase (parkingSpaces collection)
    ↓
Wait {interval} seconds
    ↓
Repeat
```

### 3. Data Flow

```
Camera → Frame → YOLO → Detections
                             ↓
                    Parking Spaces ← Firebase
                             ↓
                      IoU Matching
                             ↓
                    Space Occupancy
                             ↓
                    Firebase Update
```

## 📝 Logs

The worker outputs detailed logs:

```
2026-01-04 14:30:00 - INFO - 🚀 Starting parking monitor worker...
2026-01-04 14:30:00 - INFO - ⏱️  Check interval: 5 seconds
2026-01-04 14:30:01 - INFO - Loading AI models...
2026-01-04 14:30:05 - INFO - ✅ AI models loaded
2026-01-04 14:30:05 - INFO - Found 3 active cameras
2026-01-04 14:30:06 - INFO - Processing camera: Floor 1 Camera (CAM001)
2026-01-04 14:30:06 - INFO - Loaded 10 parking spaces for camera CAM001
2026-01-04 14:30:07 - INFO - Detected 3 vehicles in camera CAM001
2026-01-04 14:30:07 - INFO - ✅ Updated occupancy for camera CAM001: 3/10 occupied
```

## 🔍 Firebase Collections Used

### Read From:

1. **parkingLots**
   - Gets active parking lots
   - Gets camera IDs for each lot

2. **esp32_configs**
   - Gets camera IP addresses
   - Gets camera names

3. **parkingSpaceDefinitions**
   - Gets parking space coordinates
   - Cached for performance

### Write To:

1. **parkingSpaces**
   - Updates space occupancy status
   - Updates last detection time
   - Updates vehicle info

## 📈 Performance

### Resource Usage

- **CPU**: ~10-30% (depends on number of cameras and detections)
- **Memory**: ~1-2 GB (YOLO model loaded)
- **Network**: ~100 KB/s per camera (fetching frames)

### Optimization Tips

1. **Increase check interval** for fewer cameras or less frequent updates:
   ```bash
   python parking_monitor_worker.py --interval 10
   ```

2. **Reduce IoU threshold** for faster matching:
   ```python
   # In parking_monitor_worker.py, line ~180
   iou_threshold=0.3  # Lower = faster, less accurate
   ```

3. **Cache parking spaces** (already implemented):
   - Spaces are cached per camera
   - Reloaded only when needed

4. **Batch Firebase updates** (already implemented):
   - All spaces updated in one operation
   - Minimizes database writes

## 🐛 Troubleshooting

### Worker not detecting cameras

**Problem**: "No active cameras found"

**Solutions**:
1. Check if parking lots exist in Firebase with `status: 'active'`
2. Verify parking lots have cameras in the `cameras` array
3. Check camera configs exist in `esp32_configs` collection

### Cameras not responding

**Problem**: "Could not fetch frame from [URL]"

**Solutions**:
1. Verify camera is online: `curl http://localhost:5069/status`
2. Check camera IP address in Firebase is correct
3. Ensure `/capture` endpoint exists on camera
4. Check network connectivity

### No parking spaces found

**Problem**: "No parking spaces defined for camera"

**Solutions**:
1. Go to Parking Space Editor (`/parking-spaces`)
2. Draw and save parking spaces for the camera
3. Verify spaces exist in Firebase `parkingSpaceDefinitions` collection

### Detection not matching spaces

**Problem**: "Updated occupancy: 0/10 occupied" (but cars are present)

**Solutions**:
1. Lower IoU threshold from 0.5 to 0.3
2. Redraw parking spaces to better match actual parking areas
3. Check camera view hasn't changed
4. Verify YOLO is detecting vehicles (check logs)

### High CPU usage

**Problem**: Worker using too much CPU

**Solutions**:
1. Increase check interval: `--interval 10` or `--interval 30`
2. Reduce number of active cameras
3. Use smaller YOLO model (yolov8n instead of yolov8s)
4. Limit cameras per worker (run multiple workers)

## 🔧 Advanced Usage

### Run Multiple Workers

For large deployments with many cameras, run multiple workers:

```bash
# Terminal 1: Worker for Parking Lot A
python parking_monitor_worker.py --interval 5

# Terminal 2: Worker for Parking Lot B  
python parking_monitor_worker.py --interval 5
```

Filter by parking lot in the code:
```python
# In get_active_cameras(), add filter:
if lot_doc.id not in ['P01', 'P02']:  # Only process these lots
    continue
```

### Custom Detection Models

Use different YOLO models:

```python
# In AIService.__init__()
self.model = YOLO('yolov8s.pt')  # Better accuracy, slower
self.model = YOLO('yolov8n.pt')  # Faster, lower accuracy
self.model = YOLO('path/to/custom_model.pt')  # Custom trained
```

### Scheduled Monitoring

Use cron for scheduled monitoring:

```bash
# Run every 30 minutes during business hours
0,30 8-18 * * * /path/to/start_worker.sh
```

### Docker Deployment

Create `Dockerfile`:

```dockerfile
FROM python:3.11

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY server/ .
CMD ["python", "parking_monitor_worker.py", "--interval", "5"]
```

Run:
```bash
docker build -t parking-worker .
docker run -d --name parking-worker parking-worker
```

## 📊 Monitoring & Alerts

### Health Checks

Add to your monitoring system:

```bash
# Check if worker is running
ps aux | grep parking_monitor_worker

# Check logs for errors
tail -f worker.log | grep ERROR

# Check Firebase for recent updates
# Query parkingSpaces where updatedAt > 1 minute ago
```

### Alerts

Set up alerts for:
- Worker process stopped
- No updates to Firebase in X minutes
- High error rate in logs
- Camera connection failures

## 🤝 Integration with Dashboard

The worker automatically updates Firebase, so your dashboard gets real-time updates:

```typescript
// In your React dashboard
const spacesRef = collection(db, 'parkingSpaces');
const q = query(spacesRef, where('parkingId', '==', 'P01'));

// Real-time listener
onSnapshot(q, (snapshot) => {
  const spaces = snapshot.docs.map(doc => doc.data());
  const occupied = spaces.filter(s => s.occupied).length;
  console.log(`Occupancy: ${occupied}/${spaces.length}`);
});
```

## 🎓 Example Output

```
🚀 Starting parking monitor worker...
⏱️  Check interval: 5 seconds
Loading AI models...
✅ AI models loaded
Found 2 active cameras
Processing camera: Floor 1 Camera (CAM001)
Loaded 10 parking spaces for camera CAM001
Detected 3 vehicles in camera CAM001
✅ Updated occupancy for camera CAM001: 3/10 occupied
Processing camera: Floor 2 Camera (CAM002)
Loaded 8 parking spaces for camera CAM002
Detected 5 vehicles in camera CAM002
✅ Updated occupancy for camera CAM002: 5/8 occupied
Waiting 5 seconds before next check...
```

## 📚 Related Documentation

- [Parking Space Editor](../docs/PARKING_SPACE_EDITOR.md)
- [Parking Space Integration](../docs/PARKING_SPACE_INTEGRATION.md)
- [Backend API Documentation](./README.md)

---

**Last Updated**: January 4, 2026  
**Version**: 1.0  
**Status**: ✅ Production Ready
