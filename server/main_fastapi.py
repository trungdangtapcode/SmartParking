"""
FastAPI Backend cho SmartParking
Modular architecture with separated routers and middleware
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import os
import sys
import asyncio
from pathlib import Path
from contextlib import asynccontextmanager
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add ESP32 folder to path
ESP32_PATH = Path(__file__).parent.parent / "ESP32"
sys.path.insert(0, str(ESP32_PATH))

# Import services
from services.ai_service import AIService
from services.firebase_service import FirebaseService
from services.stream_broadcaster import broadcast_manager
from esp32_client import ESP32Client

# Import routers
from routers import health, user_config, streams, esp32, ai_detection, firebase, websocket_streams

# Import worker
from parking_monitor_worker import ParkingMonitorWorker

# Global instances
ai_service = None
firebase_service = None
esp32_client = None
parking_worker = None

# Configuration
ESP32_URL = os.getenv("ESP32_URL", "http://localhost:5069")
ENABLE_PARKING_MONITOR = os.getenv("ENABLE_PARKING_MONITOR", "true").lower() == "true"
MONITOR_CHECK_INTERVAL = int(os.getenv("MONITOR_CHECK_INTERVAL", "10"))

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager - load models on server start"""
    global ai_service, firebase_service, esp32_client, parking_worker
    
    print("🚀 Starting FastAPI SmartParking Server...")
    
    # Load AI models
    print("📦 Loading AI models...")
    ai_service = AIService()
    await ai_service.load_models()
    print("✅ AI models loaded successfully")
    
    # Initialize Firebase
    print("🔥 Initializing Firebase Admin SDK...")
    try:
        firebase_service = FirebaseService()
        print("✅ Firebase initialized")
    except Exception as e:
        print(f"⚠️  Firebase initialization failed: {e}")
        print("⚠️  Continuing without Firebase (some features will be disabled)")
        firebase_service = None
    
    # Initialize ESP32 client
    print(f"📹 Connecting to ESP32: {ESP32_URL}")
    esp32_client = ESP32Client(ESP32_URL)
    
    # Test connection
    async with ESP32Client(ESP32_URL) as test_client:
        result = await test_client.test_connection()
        if result['connected']:
            print(f"✅ ESP32 connected: {ESP32_URL}")
        else:
            print(f"⚠️  ESP32 not connected: {result.get('error', 'Unknown error')}")
            print(f"   💡 Start ESP32 server: cd ESP32 && python start_mock.py --port 5069")
    
    # Initialize all routers with service instances
    health.init_router(ai_service, firebase_service, ESP32_URL)
    user_config.init_router(firebase_service)
    streams.init_router(ai_service, firebase_service, ESP32_URL)
    websocket_streams.init_router(ai_service, firebase_service, ESP32_URL)
    esp32.init_router(esp32_client)
    ai_detection.init_router(ai_service, firebase_service)
    firebase.init_router(firebase_service)
    
    # Start parking monitor worker (optional)
    if ENABLE_PARKING_MONITOR and firebase_service:
        print(f"👁️  Starting parking monitor worker (interval: {MONITOR_CHECK_INTERVAL}s)...")
        parking_worker = ParkingMonitorWorker(
            check_interval=MONITOR_CHECK_INTERVAL,
            detection_url="http://localhost:8069"
        )
        # Start worker in background
        asyncio.create_task(parking_worker.start())
        print("✅ Parking monitor worker started")
    elif not ENABLE_PARKING_MONITOR:
        print("⏸️  Parking monitor worker disabled (set ENABLE_PARKING_MONITOR=true to enable)")
    
    yield  # Server runs here
    
    # Cleanup on shutdown
    print("🛑 Shutting down server...")
    
    # Stop parking worker
    if parking_worker:
        print("🛑 Stopping parking monitor worker...")
        parking_worker.stop()
    
    # Stop all broadcasters
    print("📡 Stopping broadcasters...")
    await broadcast_manager.cleanup_all()
    
    if ai_service:
        ai_service.cleanup()

# Create FastAPI app
app = FastAPI(
    title="SmartParking API",
    description="FastAPI backend with ESP32-CAM streaming & AI detection",
    version="2.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5169",
        "http://localhost:5173",
        "http://127.0.0.1:5169",
        "http://127.0.0.1:5173",
        "*"  # Allow all for development
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include all routers
app.include_router(health.router)
app.include_router(user_config.router)
app.include_router(streams.router)
app.include_router(websocket_streams.router)
app.include_router(esp32.router)
app.include_router(ai_detection.router)
app.include_router(firebase.router)

if __name__ == "__main__":
    print("=" * 60)
    print("🚀 SmartParking FastAPI Server")
    print("=" * 60)
    print(f"📹 ESP32-CAM: {ESP32_URL}")
    print(f"🌐 Backend Server: http://localhost:8069")
    print(f"📖 API Docs: http://localhost:8069/docs")
    print(f"💡 Start ESP32 server: cd ESP32 && python start_mock.py --port 5069")
    print("=" * 60)
    
    uvicorn.run(
        "main_fastapi:app",
        host="0.0.0.0",
        port=8069,
        reload=True,
        log_level="info"
    )
