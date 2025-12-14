"""
Firebase Service - Tương tác với Firestore
Sử dụng Firebase Admin SDK (Python)
"""
import firebase_admin
from firebase_admin import credentials, firestore
from typing import Dict, Any, List, Optional
from datetime import datetime
import os
from pathlib import Path


class FirebaseService:
    """Firebase Service quản lý Firestore operations"""
    
    def __init__(self, credentials_path: Optional[str] = None):
        """
        Initialize Firebase Admin SDK
        
        Args:
            credentials_path: Path đến firebase service account JSON file
                             Nếu None, sẽ tìm trong thư mục server/
        """
        self.db = None
        self._initialize_firebase(credentials_path)
    
    def _initialize_firebase(self, credentials_path: Optional[str] = None):
        """Initialize Firebase Admin SDK"""
        
        # Check if already initialized
        if firebase_admin._apps:
            print("ℹ️  Firebase already initialized")
            self.db = firestore.client()
            return
        
        # Find credentials file
        if credentials_path is None:
            # Tìm trong thư mục server/
            script_dir = Path(__file__).parent.parent
            possible_paths = [
                script_dir / "firebase_credentials.json",
                script_dir / "serviceAccountKey.json",
                script_dir / "firebase-adminsdk.json",
            ]
            
            for path in possible_paths:
                if path.exists():
                    credentials_path = str(path)
                    break
        
        if credentials_path and os.path.exists(credentials_path):
            # Initialize với service account
            print(f"🔥 Initializing Firebase with credentials: {credentials_path}")
            cred = credentials.Certificate(credentials_path)
            firebase_admin.initialize_app(cred)
        else:
            # Initialize với default credentials (for local emulator hoặc GAE)
            print("⚠️  No credentials found, using default initialization")
            print("💡 For production, download service account key from Firebase Console:")
            print("   Project Settings > Service Accounts > Generate new private key")
            
            try:
                firebase_admin.initialize_app()
            except Exception as e:
                print(f"❌ Firebase initialization failed: {e}")
                print("⚠️  Firebase features will be limited")
                return
        
        self.db = firestore.client()
        print("✅ Firebase Firestore connected")
    
    # ========== PLATE DETECTION ==========
    
    async def save_plate_detection(self, detection_result: Dict[str, Any]) -> str:
        """
        Lưu plate detection result vào Firestore
        
        Args:
            detection_result: Result từ AI service
        
        Returns:
            Document ID
        """
        if not self.db:
            print("⚠️  Firebase not initialized, skipping save")
            return ""
        
        try:
            # Tạo document data
            doc_data = {
                "timestamp": firestore.SERVER_TIMESTAMP,
                "plates": detection_result.get("plates", []),
                "plate_count": len(detection_result.get("plates", [])),
                "source": "esp32_camera",
                "processed": True,
            }
            
            # Thêm plate texts để query dễ hơn
            if doc_data["plates"]:
                doc_data["plate_texts"] = [p["text"] for p in doc_data["plates"]]
            
            # Lưu vào collection 'plate_detections'
            doc_ref = self.db.collection("plate_detections").add(doc_data)
            doc_id = doc_ref[1].id
            
            print(f"✅ Saved plate detection to Firebase: {doc_id}")
            return doc_id
            
        except Exception as e:
            print(f"❌ Error saving plate detection: {e}")
            return ""
    
    async def get_plate_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Lấy plate detection history từ Firestore
        
        Args:
            limit: Số lượng records tối đa
        
        Returns:
            List of detection records
        """
        if not self.db:
            return []
        
        try:
            # Query với order by timestamp
            docs = (
                self.db.collection("plate_detections")
                .order_by("timestamp", direction=firestore.Query.DESCENDING)
                .limit(limit)
                .stream()
            )
            
            results = []
            for doc in docs:
                data = doc.to_dict()
                data["id"] = doc.id
                results.append(data)
            
            return results
            
        except Exception as e:
            print(f"❌ Error getting plate history: {e}")
            return []
    
    async def search_plate(self, plate_text: str) -> List[Dict[str, Any]]:
        """
        Tìm kiếm plate theo text
        
        Args:
            plate_text: Biển số cần tìm (e.g., "30A-12345")
        
        Returns:
            List of matching records
        """
        if not self.db:
            return []
        
        try:
            # Query sử dụng array-contains
            docs = (
                self.db.collection("plate_detections")
                .where("plate_texts", "array_contains", plate_text.upper())
                .order_by("timestamp", direction=firestore.Query.DESCENDING)
                .limit(10)
                .stream()
            )
            
            results = []
            for doc in docs:
                data = doc.to_dict()
                data["id"] = doc.id
                results.append(data)
            
            return results
            
        except Exception as e:
            print(f"❌ Error searching plate: {e}")
            return []
    
    # ========== OBJECT TRACKING ==========
    
    async def save_tracking_result(self, tracking_result: Dict[str, Any]) -> str:
        """
        Lưu object tracking result vào Firestore
        
        Args:
            tracking_result: Result từ AI service
        
        Returns:
            Document ID
        """
        if not self.db:
            print("⚠️  Firebase not initialized, skipping save")
            return ""
        
        try:
            # Tạo document data (không lưu video base64 vào Firestore - quá lớn)
            doc_data = {
                "timestamp": firestore.SERVER_TIMESTAMP,
                "total_frames": tracking_result.get("total_frames", 0),
                "processed_frames": tracking_result.get("processed_frames", 0),
                "unique_tracks": tracking_result.get("unique_tracks", 0),
                "video_width": tracking_result.get("video_width", 0),
                "video_height": tracking_result.get("video_height", 0),
                "fps": tracking_result.get("fps", 0),
                "summary": tracking_result.get("summary", {}),
                "source": "uploaded_video",
            }
            
            # Lưu vào collection 'tracking_sessions'
            doc_ref = self.db.collection("tracking_sessions").add(doc_data)
            doc_id = doc_ref[1].id
            
            print(f"✅ Saved tracking session to Firebase: {doc_id}")
            return doc_id
            
        except Exception as e:
            print(f"❌ Error saving tracking result: {e}")
            return ""
    
    async def get_detections(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Lấy tất cả detection records (plates + tracking)
        
        Args:
            limit: Số lượng records tối đa
        
        Returns:
            List of detection records
        """
        if not self.db:
            return []
        
        try:
            # Kết hợp cả 2 collections
            plate_docs = (
                self.db.collection("plate_detections")
                .order_by("timestamp", direction=firestore.Query.DESCENDING)
                .limit(limit // 2)
                .stream()
            )
            
            tracking_docs = (
                self.db.collection("tracking_sessions")
                .order_by("timestamp", direction=firestore.Query.DESCENDING)
                .limit(limit // 2)
                .stream()
            )
            
            results = []
            
            for doc in plate_docs:
                data = doc.to_dict()
                data["id"] = doc.id
                data["type"] = "plate_detection"
                results.append(data)
            
            for doc in tracking_docs:
                data = doc.to_dict()
                data["id"] = doc.id
                data["type"] = "tracking_session"
                results.append(data)
            
            # Sort by timestamp
            results.sort(key=lambda x: x.get("timestamp", datetime.min), reverse=True)
            
            return results[:limit]
            
        except Exception as e:
            print(f"❌ Error getting detections: {e}")
            return []
    
    # ========== DETECTION RECORDS (Parking Spaces + Barrier Zones) ==========
    
    def get_detection_by_id(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """
        Get detection record by document ID.
        
        Args:
            doc_id: Document ID (format: {ownerId}__{cameraId})
        
        Returns:
            Detection record or None if not found
        """
        if not self.db:
            print("⚠️  Firebase not initialized")
            return None
        
        try:
            doc_ref = self.db.collection("detections").document(doc_id)
            doc = doc_ref.get()
            
            if doc.exists:
                data = doc.to_dict()
                data['id'] = doc.id
                print(f"✅ Found detection record: {doc_id}")
                return data
            else:
                print(f"⚠️  Detection record not found: {doc_id}")
                return None
                
        except Exception as e:
            print(f"❌ Error getting detection by ID: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    # ========== PARKING SPACES (cho future features) ==========
    
    async def save_parking_space(self, space_data: Dict[str, Any]) -> str:
        """Lưu parking space definition"""
        if not self.db:
            return ""
        
        try:
            doc_ref = self.db.collection("parking_spaces").add({
                **space_data,
                "created_at": firestore.SERVER_TIMESTAMP,
            })
            return doc_ref[1].id
        except Exception as e:
            print(f"❌ Error saving parking space: {e}")
            return ""
    
    async def get_parking_spaces(self) -> List[Dict[str, Any]]:
        """Lấy tất cả parking spaces"""
        if not self.db:
            return []
        
        try:
            docs = self.db.collection("parking_spaces").stream()
            return [{"id": doc.id, **doc.to_dict()} for doc in docs]
        except Exception as e:
            print(f"❌ Error getting parking spaces: {e}")
            return []
    
    # ========== ALERTS ==========
    
    async def create_alert(self, alert_data: Dict[str, Any]) -> str:
        """Tạo alert mới"""
        if not self.db:
            return ""
        
        try:
            doc_ref = self.db.collection("alerts").add({
                **alert_data,
                "timestamp": firestore.SERVER_TIMESTAMP,
                "resolved": False,
            })
            return doc_ref[1].id
        except Exception as e:
            print(f"❌ Error creating alert: {e}")
            return ""
    
    async def get_alerts(self, resolved: Optional[bool] = None) -> List[Dict[str, Any]]:
        """
        Lấy alerts
        
        Args:
            resolved: None = all, True = resolved only, False = unresolved only
        """
        if not self.db:
            return []
        
        try:
            query = self.db.collection("alerts")
            
            if resolved is not None:
                query = query.where("resolved", "==", resolved)
            
            docs = query.order_by("timestamp", direction=firestore.Query.DESCENDING).limit(50).stream()
            
            return [{"id": doc.id, **doc.to_dict()} for doc in docs]
            
        except Exception as e:
            print(f"❌ Error getting alerts: {e}")
            return []
    
    async def resolve_alert(self, alert_id: str) -> bool:
        """Mark alert as resolved"""
        if not self.db:
            return False
        
        try:
            self.db.collection("alerts").document(alert_id).update({
                "resolved": True,
                "resolved_at": firestore.SERVER_TIMESTAMP,
            })
            return True
        except Exception as e:
            print(f"❌ Error resolving alert: {e}")
            return False

