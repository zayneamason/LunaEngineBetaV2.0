#!/bin/bash
# KOZMO Development Server Start Script
# Prevents multiple instances by checking if port is already in use

PORT=5174

# Check if port is already in use
if lsof -Pi :$PORT -sTCP:LISTEN -t >/dev/null 2>&1 ; then
    echo "❌ Port $PORT is already in use!"
    echo ""
    echo "To kill existing process and restart:"
    echo "  ./dev.sh --restart"
    echo ""
    echo "To view running instance:"
    echo "  lsof -i :$PORT"
    exit 1
fi

# Start Vite dev server
echo "🚀 Starting KOZMO on http://localhost:$PORT"
npm run dev
