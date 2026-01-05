#!/usr/bin/env python3
"""Test fast-alpr standalone to debug the issue."""

import cv2
import numpy as np
from fast_alpr import ALPR

# Test with a simple image
frame = np.zeros((480, 640, 3), dtype=np.uint8)

print("Initializing ALPR...")
alpr = ALPR(
    detector_model="yolo-v9-t-384-license-plate-end2end",
    ocr_model="global-plates-mobile-vit-v2-model",
)

print("Testing with blank frame...")
try:
    results = alpr.predict(frame)
    print(f"Success! Detected {len(results)} plates")
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()

# Test with real video frame if available
try:
    video_path = "datasets/parking_a_30sec.mp4"
    cap = cv2.VideoCapture(video_path)
    ret, real_frame = cap.read()
    cap.release()
    
    if ret:
        print(f"\nTesting with real frame shape: {real_frame.shape}, dtype: {real_frame.dtype}")
        results = alpr.predict(real_frame)
        print(f"Success! Detected {len(results)} plates")
except Exception as e:
    print(f"Real frame test error: {e}")
    import traceback
    traceback.print_exc()
