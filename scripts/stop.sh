#!/bin/bash
# =============================================================================
# LUNA ENGINE STOP SCRIPT
# =============================================================================

echo "🛑 Stopping Luna Engine..."

pkill -f "python.*luna" 2>/dev/null || true
pkill -f "uvicorn.*luna" 2>/dev/null || true
pkill -f "vite" 2>/dev/null || true
pkill -f "node.*luna" 2>/dev/null || true

sleep 1

echo "✓ All Luna processes stopped"
