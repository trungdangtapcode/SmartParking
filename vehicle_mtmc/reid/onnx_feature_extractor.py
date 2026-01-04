"""ONNX Runtime-based feature extractor for faster inference."""

import numpy as np
import cv2
try:
    import onnxruntime as ort
except ImportError:
    ort = None


class ONNXFeatureExtractor:
    """Fast feature extractor using ONNX Runtime."""
    
    def __init__(self, onnx_path, use_gpu=True):
        if ort is None:
            raise ImportError("onnxruntime not installed. Install with: pip install onnxruntime-gpu")
        
        self.input_size = (128, 256)  # width, height
        
        # Setup ONNX Runtime session with TensorRT
        providers = []
        if use_gpu:
            # Try TensorRT first (fastest)
            if 'TensorrtExecutionProvider' in ort.get_available_providers():
                providers.append(('TensorrtExecutionProvider', {
                    'trt_fp16_enable': True,
                    'trt_engine_cache_enable': True,
                    'trt_engine_cache_path': './trt_cache',
                }))
            # Fallback to CUDA
            if 'CUDAExecutionProvider' in ort.get_available_providers():
                providers.append('CUDAExecutionProvider')
        providers.append('CPUExecutionProvider')
        
        sess_options = ort.SessionOptions()
        sess_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        
        print(f"Loading ONNX model from {onnx_path}...")
        print(f"Using providers: {providers}")
        
        self.session = ort.InferenceSession(
            onnx_path,
            sess_options=sess_options,
            providers=providers
        )
        
        self.input_name = self.session.get_inputs()[0].name
        self.output_name = self.session.get_outputs()[0].name
        
        print(f"✓ ONNX ReID model loaded on {self.session.get_providers()[0]}")
    
    def preprocess(self, img):
        """Preprocess image for ReID model."""
        if len(img.shape) == 2:  # grayscale
            img = cv2.cvtColor(img, cv2.COLOR_GRAY2RGB)
        elif img.shape[2] == 4:  # RGBA
            img = cv2.cvtColor(img, cv2.COLOR_RGBA2RGB)
        
        # Resize
        img = cv2.resize(img, self.input_size)
        
        # Normalize (ImageNet stats)
        img = img.astype(np.float32) / 255.0
        mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
        std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
        img = (img - mean) / std
        
        # HWC -> CHW
        img = np.transpose(img, (2, 0, 1))
        
        return img
    
    def __call__(self, frame, bboxes):
        """Extract features from frame crops using bboxes.
        
        Args:
            frame: numpy array (H, W, C) in BGR format
            bboxes: list of [x, y, w, h] bounding boxes in tlwh format
            
        Returns:
            features: numpy array (N, feature_dim)
        """
        if len(bboxes) == 0:
            return np.array([])
        
        # Crop patches from frame
        patches = []
        for bbox in bboxes:
            x, y, w, h = bbox
            x, y, w, h = int(x), int(y), int(w), int(h)
            
            # Ensure bbox is within frame bounds
            h_frame, w_frame = frame.shape[:2]
            x = max(0, x)
            y = max(0, y)
            w = min(w, w_frame - x)
            h = min(h, h_frame - y)
            
            if w > 0 and h > 0:
                patch = frame[y:y+h, x:x+w]
                patches.append(patch)
            else:
                # Invalid bbox, use empty patch
                patches.append(np.zeros((10, 10, 3), dtype=np.uint8))
        
        # Preprocess batch
        batch = np.stack([self.preprocess(img) for img in patches], axis=0)
        
        # Run inference
        features = self.session.run(
            [self.output_name],
            {self.input_name: batch}
        )[0]
        
        return features
