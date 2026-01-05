"""Test ONNX Runtime with TensorRT for EfficientNet-B0"""

import numpy as np
import time
import onnxruntime as ort

def test_tensorrt():
    print("=" * 70)
    print("Testing EfficientNet-B0 ONNX with TensorRT")
    print("=" * 70)
    
    # Show available providers
    print(f"\nAvailable providers: {ort.get_available_providers()}\n")
    
    onnx_path = "models/efficientnetb0/model.onnx"
    
    # Test 1: TensorRT provider
    print("Test 1: TensorRT Execution Provider")
    print("-" * 70)
    providers = [
        ('TensorrtExecutionProvider', {
            'trt_fp16_enable': True,
            'trt_engine_cache_enable': True,
            'trt_engine_cache_path': './trt_cache',
        }),
        'CUDAExecutionProvider',
        'CPUExecutionProvider'
    ]
    
    sess_options = ort.SessionOptions()
    sess_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
    
    session_trt = ort.InferenceSession(onnx_path, sess_options=sess_options, providers=providers)
    print(f"Active provider: {session_trt.get_providers()[0]}")
    
    # Prepare test input
    batch_size = 32
    input_name = session_trt.get_inputs()[0].name
    output_name = session_trt.get_outputs()[0].name
    dummy_input = np.random.randn(batch_size, 3, 256, 128).astype(np.float32)
    
    # Warmup (TensorRT builds engine on first run)
    print(f"\nWarming up with batch size {batch_size}... (TensorRT engine building)")
    for _ in range(3):
        session_trt.run([output_name], {input_name: dummy_input})
    print("✓ Warmup complete")
    
    # Benchmark
    num_runs = 100
    print(f"\nBenchmarking {num_runs} runs...")
    start = time.time()
    for _ in range(num_runs):
        features = session_trt.run([output_name], {input_name: dummy_input})[0]
    elapsed = time.time() - start
    
    print(f"✓ Output shape: {features.shape}")
    print(f"✓ Total time: {elapsed:.3f}s")
    print(f"✓ Time per batch: {elapsed/num_runs*1000:.2f}ms")
    print(f"✓ Throughput: {num_runs * batch_size / elapsed:.1f} images/sec")
    
    trt_time = elapsed / num_runs
    
    # Test 2: CUDA provider (for comparison)
    print("\n" + "=" * 70)
    print("Test 2: CUDA Execution Provider (baseline)")
    print("-" * 70)
    
    session_cuda = ort.InferenceSession(
        onnx_path, 
        sess_options=sess_options, 
        providers=['CUDAExecutionProvider', 'CPUExecutionProvider']
    )
    print(f"Active provider: {session_cuda.get_providers()[0]}")
    
    # Warmup
    print(f"\nWarming up with batch size {batch_size}...")
    for _ in range(3):
        session_cuda.run([output_name], {input_name: dummy_input})
    print("✓ Warmup complete")
    
    # Benchmark
    print(f"\nBenchmarking {num_runs} runs...")
    start = time.time()
    for _ in range(num_runs):
        features = session_cuda.run([output_name], {input_name: dummy_input})[0]
    elapsed = time.time() - start
    
    print(f"✓ Total time: {elapsed:.3f}s")
    print(f"✓ Time per batch: {elapsed/num_runs*1000:.2f}ms")
    print(f"✓ Throughput: {num_runs * batch_size / elapsed:.1f} images/sec")
    
    cuda_time = elapsed / num_runs
    
    # Summary
    print("\n" + "=" * 70)
    print("Performance Summary")
    print("=" * 70)
    print(f"TensorRT:  {trt_time*1000:.2f}ms per batch ({batch_size} images)")
    print(f"CUDA:      {cuda_time*1000:.2f}ms per batch ({batch_size} images)")
    print(f"Speedup:   {cuda_time/trt_time:.2f}x faster with TensorRT")
    print("=" * 70)

if __name__ == "__main__":
    test_tensorrt()
