"""
Detection Logs API
Endpoints for viewing and managing detection logs
"""
from fastapi import APIRouter, Query, HTTPException
from typing import Optional
import logging

from services.detection_logger import detection_logger

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/logs/stats")
async def get_log_stats():
    """
    Get statistics about detection log files
    
    Returns information about all log files, their sizes, and entry counts
    
    Example response:
    {
        "log_directory": "logs/detections",
        "log_files": [
            {
                "filename": "detection_cam001_2026-01-05.log",
                "size_mb": 2.5,
                "entries": 1500,
                "modified": "2026-01-05T14:30:00"
            }
        ],
        "total_size_mb": 10.2
    }
    """
    try:
        stats = detection_logger.get_log_stats()
        return stats
    except Exception as e:
        logger.error(f"Error getting log stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/logs/detections")
async def get_detection_logs(
    camera_id: str = Query(..., description="Camera ID to get logs for"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of entries to return")
):
    """
    Get recent detection log entries for a specific camera
    
    Query params:
        camera_id: Camera ID to get logs for
        limit: Maximum number of entries (1-1000, default 100)
    
    Returns list of detection entries with:
        - timestamp
        - summary (vehicle count, occupancy)
        - detections (bounding boxes, confidence)
        - space_occupancy
        - metadata
    
    Example response:
    [
        {
            "timestamp": "2026-01-05T14:30:15.123456",
            "camera_id": "cam001",
            "summary": {
                "vehicle_count": 5,
                "total_spaces": 20,
                "occupied_spaces": 12,
                "available_spaces": 8,
                "occupancy_rate": "60.0%"
            },
            "detections": [
                {"bbox": [100, 200, 150, 250], "confidence": 0.95, "class": "car"}
            ],
            "space_occupancy": {
                "space_01": true,
                "space_02": false
            }
        }
    ]
    """
    try:
        entries = await detection_logger.read_latest_detections(camera_id, limit)
        return {
            "camera_id": camera_id,
            "count": len(entries),
            "entries": entries
        }
    except Exception as e:
        logger.error(f"Error reading detection logs for {camera_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/logs/cleanup")
async def cleanup_old_logs(
    days: int = Query(7, ge=1, le=365, description="Delete logs older than this many days")
):
    """
    Delete log files older than specified number of days
    
    Query params:
        days: Delete files older than this many days (1-365, default 7)
    
    Example response:
    {
        "message": "Cleaned up old log files",
        "days": 7
    }
    """
    try:
        detection_logger.cleanup_old_logs(days)
        return {
            "message": f"Cleaned up log files older than {days} days",
            "days": days
        }
    except Exception as e:
        logger.error(f"Error cleaning up logs: {e}")
        raise HTTPException(status_code=500, detail=str(e))
