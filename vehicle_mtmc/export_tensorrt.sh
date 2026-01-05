#!/bin/bash
# Export ReID model: PyTorch → ONNX → TensorRT

MODEL_DIR="models/resnet50_mixstyle"
OPTS="${MODEL_DIR}/opts.yaml"
CHECKPOINT="${MODEL_DIR}/net_19.pth"
ONNX_OUTPUT="${MODEL_DIR}/model.onnx"
TRT_OUTPUT="${MODEL_DIR}/model.trt"

echo "=========================================="
echo "ReID Model TensorRT Export Pipeline"
echo "=========================================="

# Step 1: Export PyTorch to ONNX (if not already done)
if [ ! -f "$ONNX_OUTPUT" ]; then
    echo ""
    echo "Step 1/2: Exporting PyTorch → ONNX..."
    conda run -n vehicle_mtmc python3 reid/onnx_exporter.py \
        --opts "$OPTS" \
        --checkpoint "$CHECKPOINT" \
        --output "$ONNX_OUTPUT"
else
    echo ""
    echo "Step 1/2: ONNX model already exists at $ONNX_OUTPUT"
fi

# Step 2: Export ONNX to TensorRT
echo ""
echo "Step 2/2: Exporting ONNX → TensorRT..."
conda run -n vehicle_mtmc python3 reid/tensorrt_exporter.py \
    --onnx "$ONNX_OUTPUT" \
    --output "$TRT_OUTPUT" \
    --fp16 \
    --max-batch 32 \
    --workspace 2048

echo ""
echo "=========================================="
echo "✓ TensorRT export complete!"
echo "Engine: $TRT_OUTPUT"
echo "=========================================="
echo ""
echo "To use this engine, update your config:"
echo "  MOT:"
echo "    REID_TRT: '$TRT_OUTPUT'"
