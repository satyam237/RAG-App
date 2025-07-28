#!/bin/bash

echo "🚀 Starting Hybrid RAG Webapp..."
echo "=================================="

# Kill any existing processes on our ports
echo "🧹 Cleaning up existing processes..."
lsof -ti:4001 | xargs kill -9 2>/dev/null || echo "No process on port 4001"
lsof -ti:3000 | xargs kill -9 2>/dev/null || echo "No process on port 3000"

# Start API server
echo "🔧 Starting API server on port 4001..."
python3 api_server.py &
API_PID=$!

# Wait for API server to start
sleep 3

# Test API server
echo "✅ Testing API server..."
if curl -s http://localhost:4001/health > /dev/null; then
    echo "✅ API server is running!"
else
    echo "❌ API server failed to start"
    exit 1
fi

# Start React app
echo "🎨 Starting React app on port 3000..."
npm start &
REACT_PID=$!

# Wait for React app to start
sleep 5

# Test React app
echo "✅ Testing React app..."
if curl -s http://localhost:3000 > /dev/null; then
    echo "✅ React app is running!"
else
    echo "❌ React app failed to start"
    exit 1
fi

echo ""
echo "🎉 Both servers are running!"
echo "📱 React App: http://localhost:3000"
echo "🔧 API Server: http://localhost:4001"
echo ""
echo "Press Ctrl+C to stop both servers"

# Wait for user to stop
trap "echo '🛑 Stopping servers...'; kill $API_PID $REACT_PID 2>/dev/null; exit" INT
wait 