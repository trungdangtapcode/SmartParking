#!/bin/bash
# Quick script to export MobileNetV4 to ONNX

conda run -n vehicle_mtmc python3 reid/onnx_exporter.py --opts "models/resnet50_mixstyle/opts.yaml \
 --output models/resnet50_mixstyle/model.onnx \
 --checkpoint models/resnet50_mixstyle/net_19.pth