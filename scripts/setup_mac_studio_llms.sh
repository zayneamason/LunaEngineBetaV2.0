#!/bin/bash
# Luna Engine — Mac Studio M4 Max LLM Setup Script
# Run with: bash scripts/setup_mac_studio_llms.sh
# 
# Prerequisites: Homebrew installed, internet connection
# Target: Mac Studio 2025, M4 Max 48GB, Sequoia 15.6
# Budget: 50GB disk for models

set -e

echo "╔══════════════════════════════════════════════╗"
echo "║  Luna Engine — Mac Studio LLM Setup          ║"
echo "║  M4 Max 48GB • 50GB Model Budget             ║"
echo "╚══════════════════════════════════════════════╝"
echo ""

# ---------------------------------------------------
# Phase 1: Install Ollama
# ---------------------------------------------------
echo "▶ Phase 1: Installing Ollama..."

if command -v ollama &> /dev/null; then
    echo "  ✓ Ollama already installed: $(ollama --version)"
else
    echo "  Installing via Homebrew..."
    brew install ollama
    echo "  ✓ Ollama installed: $(ollama --version)"
fi

# Start Ollama service
echo "  Starting Ollama service..."
brew services start ollama 2>/dev/null || true
sleep 3  # Wait for daemon

# Verify Ollama is running
if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
    echo "  ✓ Ollama daemon running on :11434"
else
    echo "  ⚠ Ollama not responding — trying manual start..."
    ollama serve &
    sleep 5
    if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
        echo "  ✓ Ollama daemon running"
    else
        echo "  ✗ Failed to start Ollama. Check logs."
        exit 1
    fi
fi

echo ""

# ---------------------------------------------------
# Phase 2: Download Models (~48GB total)
# ---------------------------------------------------
echo "▶ Phase 2: Downloading models..."
echo "  This will download ~48GB. Grab a coffee. ☕"
echo ""

# Router / Fast model first (smallest, needed for testing)
echo "  [1/4] qwen3:8b (~5GB) — Router / Fast..."
ollama pull qwen3:8b
echo "  ✓ qwen3:8b ready"
echo ""

# General Brain (main workhorse)
echo "  [2/4] qwen3:30b-a3b (~19GB) — General Brain (MoE)..."
ollama pull qwen3:30b-a3b
echo "  ✓ qwen3:30b-a3b ready"
echo ""

# Code Brain
echo "  [3/4] qwen3-coder:30b (~19GB) — Code Brain (MoE)..."
ollama pull qwen3-coder:30b
echo "  ✓ qwen3-coder:30b ready"
echo ""

# Vision
echo "  [4/4] qwen2-vl:7b (~5GB) — Vision..."
ollama pull qwen2-vl:7b
echo "  ✓ qwen2-vl:7b ready"
echo ""

# ---------------------------------------------------
# Phase 3: Verify
# ---------------------------------------------------
echo "▶ Phase 3: Verifying installation..."
echo ""

echo "  Installed models:"
ollama list
echo ""

# Quick smoke test
echo "  Smoke test (qwen3:8b)..."
RESPONSE=$(curl -s http://localhost:11434/api/chat -d '{
  "model": "qwen3:8b",
  "messages": [{"role":"user","content":"Say hello in exactly 5 words"}],
  "stream": false,
  "options": {"temperature": 0.6}
}' | python3 -c "import sys,json; print(json.load(sys.stdin)['message']['content'][:100])" 2>/dev/null)

if [ -n "$RESPONSE" ]; then
    echo "  ✓ Model responded: $RESPONSE"
else
    echo "  ⚠ No response from smoke test — check Ollama logs"
fi

echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║  ✓ Setup complete!                           ║"
echo "║                                              ║"
echo "║  Models:                                     ║"
echo "║    • qwen3:8b        — Router/Fast           ║"
echo "║    • qwen3:30b-a3b   — General Brain         ║"
echo "║    • qwen3-coder:30b — Code Brain            ║"
echo "║    • qwen2-vl:7b     — Vision                ║"
echo "║                                              ║"
echo "║  Next: Update Luna config files              ║"
echo "║  See: handoffs/mac-studio-llm-setup.md       ║"
echo "╚══════════════════════════════════════════════╝"
