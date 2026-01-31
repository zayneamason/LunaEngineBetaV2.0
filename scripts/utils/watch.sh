#!/bin/bash
# =============================================================================
# LUNA ENGINE WATCH — Multi-pane log viewer
# =============================================================================
# Opens tmux with split views for different log streams
# Usage: ./scripts/watch.sh
# =============================================================================

# Check for tmux
if ! command -v tmux &> /dev/null; then
    echo "tmux not found. Install with: brew install tmux"
    echo ""
    echo "Falling back to simple tail..."
    tail -f /tmp/luna_backend.log
    exit 0
fi

SESSION="luna-watch"

# Kill existing session
tmux kill-session -t $SESSION 2>/dev/null

# Create new session
tmux new-session -d -s $SESSION -n "Luna Watch"

# Split into 4 panes
#  ┌─────────┬─────────┐
#  │ REQUEST │ ROUTE   │
#  ├─────────┼─────────┤
#  │ CONTEXT │ ERRORS  │
#  └─────────┴─────────┘

tmux split-window -h -t $SESSION
tmux split-window -v -t $SESSION:0.0
tmux split-window -v -t $SESSION:0.2

# Pane 0: Requests
tmux send-keys -t $SESSION:0.0 "echo '📥 REQUESTS' && tail -f /tmp/luna_backend.log 2>/dev/null | grep --line-buffered -E '\[REQUEST\]|Message:'" Enter

# Pane 1: Routing
tmux send-keys -t $SESSION:0.1 "echo '🔀 ROUTING' && tail -f /tmp/luna_backend.log 2>/dev/null | grep --line-buffered -E '\[ROUTE\]|delegated|local'" Enter

# Pane 2: Context
tmux send-keys -t $SESSION:0.2 "echo '🧠 CONTEXT' && tail -f /tmp/luna_backend.log 2>/dev/null | grep --line-buffered -E '\[CONTEXT\]|History|Entity|prompt'" Enter

# Pane 3: Errors
tmux send-keys -t $SESSION:0.3 "echo '⚠️  ERRORS' && tail -f /tmp/luna_backend.log 2>/dev/null | grep --line-buffered -E '\[ERROR\]|\[WARN\]|Error|Exception|Traceback|FAILED'" Enter

# Attach to session
tmux attach-session -t $SESSION
