"""Export PyTorch ReID models to ONNX for faster inference."""

import torch
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(SCRIPT_DIR, 'vehicle_reid'))

from vehicle_reid.load_model import load_model_from_opts


def export_reid_to_onnx(opts_yaml, checkpoint, output_path, opset_version=14):
    """Export ReID model to ONNX format.
    
    Args:
        opts_yaml: Path to model opts.yaml
        checkpoint: Path to model checkpoint (.pth), or None for raw pretrained
        output_path: Output ONNX file path
        opset_version: ONNX opset version
    """
    print(f"Loading model from {opts_yaml}...")
    model = load_model_from_opts(
        opts_yaml, 
        ckpt=checkpoint,
        return_feature=True,
        remove_classifier=True
    )
    
    model.eval()
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    model = model.to(device)
    
    # Dummy input (batch_size=1, channels=3, height=256, width=128)
    dummy_input = torch.randn(1, 3, 256, 128, device=device)
    
    print(f"Exporting to {output_path}...")
    torch.onnx.export(
        model,
        dummy_input,
        output_path,
        opset_version=opset_version,
        input_names=['input'],
        output_names=['output'],
        dynamic_axes={
            'input': {0: 'batch_size'},
            'output': {0: 'batch_size'}
        },
        verbose=False
    )
    
    print(f"✓ Exported to {output_path}")
    
    # Verify the exported model
    try:
        import onnx
        onnx_model = onnx.load(output_path)
        onnx.checker.check_model(onnx_model)
        print("✓ ONNX model verified successfully")
    except ImportError:
        print("⚠ onnx package not found, skipping verification")
    except Exception as e:
        print(f"⚠ ONNX verification failed: {e}")
    
    return output_path


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Export ReID model to ONNX')
    parser.add_argument('--opts', type=str, required=True, help='Path to opts.yaml')
    parser.add_argument('--checkpoint', type=str, default=None, help='Path to checkpoint .pth (optional)')
    parser.add_argument('--output', type=str, required=True, help='Output ONNX path')
    parser.add_argument('--opset', type=int, default=14, help='ONNX opset version')
    
    args = parser.parse_args()
    
    export_reid_to_onnx(args.opts, args.checkpoint, args.output, args.opset)
