#!/bin/bash
# ===================================================
#  Start SmartParking FastAPI Server (Conda version)
# ===================================================

echo ""
echo "============================================================"
echo "   Starting SmartParking FastAPI Server"
echo "============================================================"
echo ""

# Check if conda is available
if ! command -v conda &> /dev/null; then
    echo "[ERROR] Conda not found!"
    echo ""
    echo "Please:"
    echo "  1. Install Anaconda/Miniconda"
    echo "  2. Or add Conda to PATH"
    echo ""
    exit 1
fi

# Check if environment exists
if ! conda env list | grep -q "smartparking"; then
    echo "[WARNING] Environment 'smartparking' not found!"
    echo ""
    echo "Creating environment from environment.yml..."
    conda env create -f environment.yml
    if [ $? -ne 0 ]; then
        echo "[ERROR] Failed to create environment!"
        exit 1
    fi
    echo ""
    echo "[SUCCESS] Environment created!"
    echo ""
fi

echo "Activating Conda environment: smartparking"
source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate smartparking

echo ""
echo "Checking Python version..."
python --version

echo ""
echo "Starting FastAPI server..."
echo "Server will be available at: http://localhost:8000"
echo "API Docs: http://localhost:8000/docs"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""

# Start server
python main_fastapi.py

# If server stops
echo ""
echo "Server stopped."

