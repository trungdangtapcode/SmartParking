# 🖥️ Worker Monitor Dashboard - User Guide

## Overview

The **Worker Monitor Dashboard** is an admin-only page that provides real-time monitoring and control of background worker processes. Admins can:

- ✅ Enable/disable workers for each camera
- 📊 View live worker statistics
- 📝 Monitor worker logs in real-time
- 🔄 Control auto-refresh settings
- 💾 Export logs for debugging

## Accessing the Dashboard

### Requirements
- ✅ **Admin account** (role = 'admin')
- ✅ At least one ESP32 camera configured
- ✅ Background worker running on server

### Navigation
1. Log in as admin
2. Click **🖥️ Worker Monitor** in the sidebar
3. Dashboard loads automatically

## Dashboard Layout

```
┌────────────────────────────────────────────────────────────────┐
│  🖥️ Worker Monitor Dashboard                                   │
├────────────────────────────────────────────────────────────────┤
│                                                                 │
│  [📹 Cameras] [✅ Enabled] [🔄 Running] [❌ Errors] [📝 Logs]  │
│                                                                 │
├──────────────────┬────────────────────────────────────────────┤
│                  │                                             │
│  ⚙️ Controls     │  📝 Worker Logs                            │
│  ┌──────────┐    │  ┌────────────────────────────────────┐   │
│  │ Auto:✅  │    │  │ [2026-01-05 10:00:00] [INFO]       │   │
│  │ 5s       │    │  │ [Camera 1] ✅ Processing...        │   │
│  │ 🔄Refresh│    │  │                                     │   │
│  └──────────┘    │  │ [2026-01-05 10:00:05] [DEBUG]      │   │
│                  │  │ [Camera 1] Fetched 48531 bytes     │   │
│  📹 Cameras      │  │                                     │   │
│  ┌──────────┐    │  │ [2026-01-05 10:00:07] [INFO]       │   │
│  │ 🟢 Cam1  │    │  │ [Camera 1] Detected 2 vehicles     │   │
│  │ ON  🎯   │    │  │                                     │   │
│  └──────────┘    │  └────────────────────────────────────┘   │
│  ┌──────────┐    │  [All Cameras ▼] [All Levels ▼]          │
│  │ ⚪ Cam2  │    │  [💾 Export] [🗑️ Clear]                   │
│  │ OFF      │    │                                             │
│  └──────────┘    │                                             │
│                  │                                             │
└──────────────────┴────────────────────────────────────────────┘
```

## Features

### 1. Statistics Cards (Top Row)

```
┌──────────────┬──────────────┬──────────────┬──────────────┬──────────────┐
│ 📹 Total     │ ✅ Workers   │ 🔄 Running   │ ❌ Errors    │ 📝 Total     │
│ Cameras      │ Enabled      │ Now          │              │ Logs         │
│              │              │              │              │              │
│    10        │     6        │     5        │     1        │    1,234     │
└──────────────┴──────────────┴──────────────┴──────────────┴──────────────┘
```

- **Total Cameras**: All ESP32 cameras configured
- **Workers Enabled**: Cameras with `workerEnabled = true`
- **Running Now**: Active workers processing frames
- **Errors**: Workers encountering errors
- **Total Logs**: Number of log entries captured

### 2. Controls Panel (Left Side)

#### Auto Refresh Toggle
```
Auto Refresh    [✅ ON]
               [⏸️ OFF]
```
- **ON**: Dashboard auto-refreshes at set interval
- **OFF**: Manual refresh only

#### Refresh Interval Slider
```
Refresh Interval: 5s
[━━━●━━━━━━━━━━━]
1s            30s
```
- Adjust refresh rate from 1-30 seconds
- Lower values = more frequent updates
- Higher values = less server load

#### Manual Refresh Button
```
[🔄 Refresh Now]
```
- Manually update worker status
- Useful when auto-refresh is OFF

### 3. Camera Status List (Left Side)

Each camera card shows:

```
┌────────────────────────────────┐
│ 🟢 Front Gate Camera           │  ← Status indicator
│ http://192.168.1.100:81        │  ← IP address
│                          [ON]  │  ← Worker toggle
├────────────────────────────────┤
│ Last Check: 10:00:00           │  ← Last activity
│ Spaces: 3/10                   │  ← Occupancy status
└────────────────────────────────┘
```

#### Status Indicators

| Icon | Status | Meaning |
|------|--------|---------|
| 🟢 | Running | Worker actively processing |
| 🟡 | Enabled | Worker enabled but waiting |
| 🔴 | Error | Worker encountered error |
| ⚪ | Idle | Worker disabled |

#### Card Colors

| Color | Status |
|-------|--------|
| ![#C8E6C9](https://via.placeholder.com/15/C8E6C9/000000?text=+) Green | Running successfully |
| ![#FFF9C4](https://via.placeholder.com/15/FFF9C4/000000?text=+) Yellow | Enabled but idle |
| ![#FFCDD2](https://via.placeholder.com/15/FFCDD2/000000?text=+) Red | Error state |
| ![#F5F5F5](https://via.placeholder.com/15/F5F5F5/000000?text=+) Gray | Disabled |

#### Worker Toggle Button

```
[ON]   ← Click to disable
[OFF]  ← Click to enable
```

**Actions:**
- Click **ON** → Disables worker (saves to Firebase)
- Click **OFF** → Enables worker (saves to Firebase)
- Changes take effect within refresh interval

### 4. Worker Logs Panel (Right Side)

#### Log Display

```
┌─────────────────────────────────────────────────────────────┐
│ [10:00:00] [INFO]  [Front Gate] ✅ Processing camera...     │
│ [10:00:01] [DEBUG] [Front Gate] Fetched 48531 bytes         │
│ [10:00:03] [INFO]  [Front Gate] Detected 2 vehicles         │
│ [10:00:03] [INFO]  [Front Gate] ✅ Updated occupancy: 2/10  │
│ [10:00:05] [WARNING] [Rear Lot] ⚠️ No vehicles detected     │
│ [10:00:07] [ERROR] [Side Gate] ❌ Failed to fetch frame     │
└─────────────────────────────────────────────────────────────┘
```

#### Log Levels & Colors

| Level | Color | Example |
|-------|-------|---------|
| INFO | ![#4CAF50](https://via.placeholder.com/15/4CAF50/000000?text=+) Green | Normal operations |
| DEBUG | ![#9E9E9E](https://via.placeholder.com/15/9E9E9E/000000?text=+) Gray | Detailed info |
| WARNING | ![#FFC107](https://via.placeholder.com/15/FFC107/000000?text=+) Yellow | Non-critical issues |
| ERROR | ![#F44336](https://via.placeholder.com/15/F44336/000000?text=+) Red | Critical errors |

#### Log Filters

**Filter by Camera**
```
[All Cameras ▼]
└─ Front Gate Camera
└─ Rear Lot Camera
└─ Side Gate Camera
```
- Select specific camera to filter logs
- Shows only logs from selected camera

**Filter by Log Level**
```
[All Levels ▼]
└─ INFO
└─ WARNING
└─ ERROR
└─ DEBUG
```
- Filter by severity level
- Useful for finding errors quickly

#### Log Actions

**Export Logs**
```
[💾 Export]
```
- Downloads logs as JSON file
- Filename: `worker-logs-2026-01-05T10:00:00.000Z.json`
- Useful for debugging and analysis

**Clear Logs**
```
[🗑️ Clear]
```
- Clears all log entries from display
- Requires confirmation
- Does not affect server logs

#### Auto-Scroll
- Logs automatically scroll to bottom
- Shows latest entries first
- Smooth scrolling animation

## Common Use Cases

### 1. Enable Worker for New Camera

**Steps:**
1. Go to Worker Monitor
2. Find camera in left panel
3. Click **OFF** button → Changes to **ON**
4. Status indicator changes: ⚪ → 🟡 → 🟢
5. Logs appear in right panel

**Expected Logs:**
```
[10:00:00] [INFO] [New Camera] 🔄 Worker enabled by admin
[10:00:05] [INFO] [New Camera] ✅ Processing camera...
[10:00:06] [DEBUG] [New Camera] Fetched 48531 bytes
[10:00:08] [INFO] [New Camera] Detected 0 vehicles
```

### 2. Troubleshoot Error

**Symptoms:**
- Camera card shows 🔴 Red
- Error message displayed
- Logs show ERROR entries

**Steps:**
1. Click on camera card to select
2. Logs filter to show only that camera
3. Look for ERROR entries
4. Check error message for details

**Common Errors:**

| Error | Cause | Solution |
|-------|-------|----------|
| Failed to fetch frame | Camera offline | Check camera IP/connection |
| No spaces defined | Missing config | Define spaces in Editor |
| Image decode failure | Corrupted frame | Restart camera |
| Connection timeout | Network issue | Check network settings |

**Example Error Log:**
```
[10:05:00] [ERROR] [Side Gate] ❌ Failed to fetch frame from camera
[10:05:00] [ERROR] [Side Gate] Connection timeout after 10s
```

### 3. Monitor Performance

**What to Watch:**

**Good Performance:**
```
[10:00:00] [INFO] ✅ Updated occupancy: 3/10 occupied
[10:00:05] [INFO] ✅ Updated occupancy: 3/10 occupied (stable)
[10:00:10] [INFO] ✅ Updated occupancy: 4/10 occupied (changed)
```

**Poor Performance:**
```
[10:00:00] [WARNING] ⚠️ Frame processing took 8.5s (slow)
[10:00:10] [WARNING] ⚠️ No vehicles detected in 10 frames
[10:00:15] [ERROR] ❌ Detection timeout
```

**Metrics to Monitor:**
- Processing frequency (every 5s by default)
- Frame fetch time (< 1s is good)
- Detection accuracy (check occupancy changes)
- Error frequency (< 1% is acceptable)

### 4. Bulk Enable/Disable Workers

**Enable All:**
1. Toggle each camera ON one by one
2. Watch status indicators turn green
3. Confirm logs appear for all cameras

**Disable All (Maintenance Mode):**
1. Toggle each camera OFF
2. Status indicators turn gray
3. Logs stop appearing
4. Workers stop consuming resources

## Best Practices

### 1. Monitoring Strategy

**Daily Checks (1-2 times/day):**
- Quick glance at statistics cards
- Check for any red error indicators
- Verify running workers match expectations

**Weekly Reviews:**
- Export and analyze logs
- Check for recurring warnings
- Review error patterns
- Optimize refresh intervals

**Before Production:**
- Enable workers gradually (1-2 at a time)
- Monitor performance for 5-10 minutes
- Check for errors or warnings
- Verify occupancy updates correctly

### 2. Resource Management

**Low Traffic Times:**
- Keep workers running for baseline data
- Use longer refresh intervals (10-15s)
- Monitor for anomalies

**High Traffic Times:**
- Enable all critical cameras
- Use shorter refresh intervals (3-5s)
- Monitor for overload warnings

**Maintenance Windows:**
- Disable all workers temporarily
- Perform system updates
- Re-enable and verify functionality

### 3. Troubleshooting Workflow

```
Error Detected
    ↓
Check Camera Card
    ↓
View Filtered Logs
    ↓
Identify Error Type
    ↓
┌───────────┬───────────┬───────────┐
│ Network   │ Config    │ Hardware  │
│ Error     │ Error     │ Error     │
└─────┬─────┴─────┬─────┴─────┬─────┘
      ↓           ↓           ↓
Check IP    Define Spaces  Restart
Ping Camera  In Editor     Camera
```

### 4. Performance Optimization

**If logs show slow processing:**
1. Increase refresh interval (reduce frequency)
2. Disable low-priority cameras
3. Check network bandwidth
4. Consider adding more worker instances

**If logs show frequent errors:**
1. Verify camera connectivity
2. Check parking space definitions
3. Review YOLO model configuration
4. Inspect server resources (CPU/GPU/RAM)

## Technical Notes

### Current Implementation

**Frontend (Mock Data):**
- Logs are **simulated** for demonstration
- Real-time updates via timers
- Status changes are random

**Production Implementation:**
- Connect to backend API endpoint
- Fetch real logs from Python worker
- Use WebSocket for real-time updates

### API Integration (TODO)

**Endpoints Needed:**

```typescript
// Get worker status for all cameras
GET /api/workers/status
Response: {
  cameras: [
    {
      cameraId: string,
      enabled: boolean,
      status: 'running' | 'idle' | 'error',
      lastCheck: string,
      spacesCount: number,
      occupiedCount: number,
      errorMessage?: string
    }
  ]
}

// Get worker logs
GET /api/workers/logs?camera={id}&level={level}&limit={n}
Response: {
  logs: [
    {
      timestamp: string,
      level: 'INFO' | 'DEBUG' | 'WARNING' | 'ERROR',
      cameraId: string,
      message: string
    }
  ]
}

// WebSocket for real-time logs
WS /api/workers/logs/stream
Message: {
  timestamp: string,
  level: string,
  cameraId: string,
  message: string
}
```

### Data Flow

```
┌─────────────────┐
│  Worker Monitor │  (Frontend)
│     Dashboard   │
└────────┬────────┘
         │
         │ HTTP GET/POST
         ↓
┌─────────────────┐
│   FastAPI       │  (Backend)
│   /api/workers  │
└────────┬────────┘
         │
         │ Query Firestore
         ↓
┌─────────────────┐
│   Firebase      │  (Database)
│  esp32_configs  │
│  workerEnabled  │
└─────────────────┘
         ↑
         │ Read/Write
         │
┌────────┴────────┐
│ parking_monitor │  (Worker Service)
│    _worker.py   │
└─────────────────┘
```

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `R` | Manual refresh |
| `A` | Toggle auto-refresh |
| `C` | Clear logs (with confirm) |
| `E` | Export logs |
| `1-9` | Select camera by number |
| `Esc` | Deselect camera |

## Mobile Responsiveness

The dashboard is **responsive** and adapts to mobile screens:

**Desktop (> 1024px):**
- Side-by-side layout
- Full controls visible
- Large log panel

**Tablet (768px - 1024px):**
- Stacked layout
- Compact controls
- Scrollable logs

**Mobile (< 768px):**
- Single column
- Minimal controls
- Touch-optimized buttons

## Summary

The Worker Monitor Dashboard provides comprehensive monitoring and control capabilities for admin users. Key benefits:

✅ **Real-time visibility** into worker processes  
✅ **Easy enable/disable** for each camera  
✅ **Detailed logging** for troubleshooting  
✅ **Performance metrics** for optimization  
✅ **Resource management** for efficiency  

Use this dashboard daily to ensure smooth operation of your smart parking system!
