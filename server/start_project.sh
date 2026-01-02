#!/bin/bash

# SmartParking Project Startup Script
# Starts both backend servers and frontend

echo "🚀 Starting SmartParking Project..."
echo "=" * 60

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Activate conda environment
eval "$(conda shell.bash hook)"
conda activate scheduler

# Check if conda env activated
if [ "$CONDA_DEFAULT_ENV" != "scheduler" ]; then
    echo "❌ Failed to activate scheduler conda environment"
    exit 1
fi

echo -e "${GREEN}✅ Conda environment: scheduler${NC}"

# Kill existing processes on ports
echo "🧹 Cleaning up existing processes..."
lsof -ti:8081 | xargs kill -9 2>/dev/null
lsof -ti:8069 | xargs kill -9 2>/dev/null
lsof -ti:5169 | xargs kill -9 2>/dev/null
sleep 2

# Start Mock ESP32 Server
echo -e "${YELLOW}📹 Starting Mock ESP32 Server (port 8081)...${NC}"
cd "$(dirname "$0")"
python mock_esp32_server.py > /tmp/mock_esp32.log 2>&1 &
MOCK_PID=$!
echo "   PID: $MOCK_PID"
sleep 3

# Check if mock server started
if ps -p $MOCK_PID > /dev/null; then
    echo -e "${GREEN}   ✅ Mock ESP32 Server running${NC}"
else
    echo "   ❌ Mock ESP32 Server failed to start"
    echo "   Check log: tail -f /tmp/mock_esp32.log"
    exit 1
fi

# Start Main API Server
echo -e "${YELLOW}🔧 Starting Main API Server (port 8069)...${NC}"
python main_fastapi.py > /tmp/main_api.log 2>&1 &
API_PID=$!
echo "   PID: $API_PID"
sleep 5

# Check if API server started
if ps -p $API_PID > /dev/null; then
    echo -e "${GREEN}   ✅ Main API Server running${NC}"
else
    echo "   ❌ Main API Server failed to start"
    echo "   Check log: tail -f /tmp/main_api.log"
    kill $MOCK_PID 2>/dev/null
    exit 1
fi

# Start Frontend
echo -e "${YELLOW}🌐 Starting Frontend (port 5169)...${NC}"
cd ../frontend
npm run dev > /tmp/frontend.log 2>&1 &
FRONTEND_PID=$!
echo "   PID: $FRONTEND_PID"
sleep 3

# Check if frontend started
if ps -p $FRONTEND_PID > /dev/null; then
    echo -e "${GREEN}   ✅ Frontend running${NC}"
else
    echo "   ❌ Frontend failed to start"
    echo "   Check log: tail -f /tmp/frontend.log"
    kill $MOCK_PID $API_PID 2>/dev/null
    exit 1
fi

# Summary
echo ""
echo "=" * 60
echo -e "${GREEN}🎉 All services started successfully!${NC}"
echo "=" * 60
echo "📹 Mock ESP32:  http://localhost:8081/docs"
echo "🔧 Main API:    http://localhost:8069/docs"
echo "🌐 Frontend:    http://localhost:5169"
echo ""
echo "📊 Stream test: http://localhost:8069/stream"
echo ""
echo "📝 Logs:"
echo "   Mock ESP32: tail -f /tmp/mock_esp32.log"
echo "   Main API:   tail -f /tmp/main_api.log"
echo "   Frontend:   tail -f /tmp/frontend.log"
echo ""
echo "🛑 To stop all services, run: ./stop_project.sh"
echo "=" * 60

# Save PIDs for cleanup
echo "$MOCK_PID" > /tmp/smartparking_mock.pid
echo "$API_PID" > /tmp/smartparking_api.pid
echo "$FRONTEND_PID" > /tmp/smartparking_frontend.pid

# Keep script running and wait for Ctrl+C
trap "echo ''; echo '🛑 Stopping all services...'; kill $MOCK_PID $API_PID $FRONTEND_PID 2>/dev/null; exit 0" INT TERM

echo ""
echo "Press Ctrl+C to stop all services..."
wait
