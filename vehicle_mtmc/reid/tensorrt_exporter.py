"""Export ONNX ReID models to TensorRT engine for maximum speed."""

import tensorrt as trt
import os
import sys


def export_onnx_to_tensorrt(
    onnx_path,
    engine_path,
    fp16=True,
    max_batch_size=32,
    workspace_size=2048
):
    """Export ONNX model to TensorRT engine.
    
    Args:
        onnx_path: Path to ONNX model
        engine_path: Output TensorRT engine path (.trt or .engine)
        fp16: Enable FP16 precision (faster, slight accuracy loss)
        max_batch_size: Maximum batch size for dynamic batching
        workspace_size: Max workspace in MB (default 2GB)
    """
    TRT_LOGGER = trt.Logger(trt.Logger.INFO)
    
    print(f"Loading ONNX model from {onnx_path}...")
    
    # Create builder and network
    builder = trt.Builder(TRT_LOGGER)
    network = builder.create_network(1 << int(trt.NetworkDefinitionCreationFlag.EXPLICIT_BATCH))
    parser = trt.OnnxParser(network, TRT_LOGGER)
    
    # Parse ONNX model
    with open(onnx_path, 'rb') as f:
        if not parser.parse(f.read()):
            print('ERROR: Failed to parse ONNX file')
            for error in range(parser.num_errors):
                print(parser.get_error(error))
            return None
    
    print("✓ ONNX model parsed successfully")
    
    # Configure builder
    config = builder.create_builder_config()
    config.set_memory_pool_limit(trt.MemoryPoolType.WORKSPACE, workspace_size * (1 << 20))  # MB to bytes
    
    if fp16 and builder.platform_has_fast_fp16:
        print("✓ Enabling FP16 mode")
        config.set_flag(trt.BuilderFlag.FP16)
    else:
        print("⚠ FP16 not available or disabled, using FP32")
    
    # Dynamic batching optimization profile
    profile = builder.create_optimization_profile()
    
    # Assuming input name is 'input' with shape [batch, 3, 256, 128]
    input_name = network.get_input(0).name
    input_shape = network.get_input(0).shape
    
    print(f"Input: {input_name}, Shape: {input_shape}")
    
    # Define min/opt/max batch sizes for dynamic batching
    min_batch = 1
    opt_batch = max_batch_size // 2
    max_batch = max_batch_size
    
    # Set optimization profile for dynamic batch dimension
    profile.set_shape(
        input_name,
        (min_batch, 3, 256, 128),  # min
        (opt_batch, 3, 256, 128),  # optimal
        (max_batch, 3, 256, 128)   # max
    )
    config.add_optimization_profile(profile)
    
    print(f"Building TensorRT engine (batch: {min_batch}-{max_batch})...")
    print("This may take several minutes...")
    
    # Build engine
    serialized_engine = builder.build_serialized_network(network, config)
    
    if serialized_engine is None:
        print("ERROR: Failed to build TensorRT engine")
        return None
    
    print(f"✓ Engine built successfully")
    
    # Save engine
    print(f"Saving engine to {engine_path}...")
    with open(engine_path, 'wb') as f:
        f.write(serialized_engine)
    
    print(f"✓ TensorRT engine saved to {engine_path}")
    print(f"  - FP16: {fp16}")
    print(f"  - Max batch size: {max_batch}")
    print(f"  - Engine size: {os.path.getsize(engine_path) / (1024*1024):.2f} MB")
    
    return engine_path


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Export ONNX to TensorRT engine')
    parser.add_argument('--onnx', type=str, required=True, help='Path to ONNX model')
    parser.add_argument('--output', type=str, required=True, help='Output TensorRT engine path (.trt)')
    parser.add_argument('--fp16', action='store_true', default=True, help='Enable FP16 precision')
    parser.add_argument('--fp32', dest='fp16', action='store_false', help='Use FP32 precision')
    parser.add_argument('--max-batch', type=int, default=32, help='Maximum batch size')
    parser.add_argument('--workspace', type=int, default=2048, help='Workspace size in MB')
    
    args = parser.parse_args()
    
    export_onnx_to_tensorrt(
        args.onnx,
        args.output,
        fp16=args.fp16,
        max_batch_size=args.max_batch,
        workspace_size=args.workspace
    )
