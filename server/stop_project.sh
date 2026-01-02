#!/bin/bash

# Stop all SmartParking services

echo "🛑 Stopping SmartParking services..."

# Read PIDs from files
if [ -f /tmp/smartparking_mock.pid ]; then
    MOCK_PID=$(cat /tmp/smartparking_mock.pid)
    kill $MOCK_PID 2>/dev/null && echo "   Stopped Mock ESP32 (PID: $MOCK_PID)"
    rm /tmp/smartparking_mock.pid
fi

if [ -f /tmp/smartparking_api.pid ]; then
    API_PID=$(cat /tmp/smartparking_api.pid)
    kill $API_PID 2>/dev/null && echo "   Stopped Main API (PID: $API_PID)"
    rm /tmp/smartparking_api.pid
fi

if [ -f /tmp/smartparking_frontend.pid ]; then
    FRONTEND_PID=$(cat /tmp/smartparking_frontend.pid)
    kill $FRONTEND_PID 2>/dev/null && echo "   Stopped Frontend (PID: $FRONTEND_PID)"
    rm /tmp/smartparking_frontend.pid
fi

# Kill by port as fallback
lsof -ti:8081 | xargs kill -9 2>/dev/null && echo "   Killed process on port 8081"
lsof -ti:8069 | xargs kill -9 2>/dev/null && echo "   Killed process on port 8069"
lsof -ti:5169 | xargs kill -9 2>/dev/null && echo "   Killed process on port 5169"

echo "✅ All services stopped"
