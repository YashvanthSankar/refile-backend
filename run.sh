#!/bin/bash

# Quick Run - Start Backend on Port 8000

cd "$(dirname "$0")"

# Kill existing
lsof -ti :8000 | xargs kill -9 2>/dev/null

echo "🚀 Starting backend on port 8000..."

# Start server
nohup .venv/bin/python simple_test.py > backend.log 2>&1 &
PID=$!

sleep 2

# Check
if curl -s http://localhost:8000/api/health > /dev/null 2>&1; then
    echo "✅ Backend running on port 8000 (PID: $PID)"
    echo "📍 http://localhost:8000"
    echo "🛑 To stop: kill $PID"
else
    echo "❌ Failed - check backend.log"
fi
