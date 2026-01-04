"""Script to export YOLO model to ONNX for faster detection."""

import sys
from pathlib import Path

def export_yolo_to_onnx(model_path, output_path=None, imgsz=640, half=True):
    """Export YOLO model to ONNX format.
    
    Args:
        model_path: Path to .pt YOLO model
        output_path: Output ONNX path (auto-generated if None)
        imgsz: Input image size
        half: Use FP16 precision
    """
    try:
        from ultralytics import YOLO
    except ImportError:
        print("ERROR: ultralytics not installed")
        print("Install with: pip install ultralytics")
        sys.exit(1)
    
    model_path = Path(model_path)
    if output_path is None:
        output_path = model_path.with_suffix('.onnx')
    
    print(f"Loading YOLO model: {model_path}")
    model = YOLO(str(model_path))
    
    print(f"Exporting to ONNX: {output_path}")
    model.export(
        format='onnx',
        imgsz=imgsz,
        half=half,
        simplify=True,
        opset=14
    )
    
    print(f"✓ Exported to {output_path}")
    return output_path


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Export YOLO to ONNX')
    parser.add_argument('--model', type=str, required=True, help='Path to .pt model')
    parser.add_argument('--output', type=str, default=None, help='Output ONNX path')
    parser.add_argument('--imgsz', type=int, default=640, help='Input image size')
    parser.add_argument('--fp16', action='store_true', help='Use FP16 precision')
    
    args = parser.parse_args()
    
    export_yolo_to_onnx(args.model, args.output, args.imgsz, args.fp16)
