#!/bin/bash
# =============================================================================
# LUNA ENGINE GIT FORENSICS
# =============================================================================
# Analyze recent changes to find potential regression causes
# Usage: ./scripts/git_forensics.sh
# =============================================================================

PROJECT_ROOT="/Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root"
cd "$PROJECT_ROOT"

OUTPUT_DIR="/tmp/luna_forensics"
mkdir -p "$OUTPUT_DIR"

echo "🔍 Luna Engine Git Forensics"
echo "============================"
echo ""

# 1. Recent commits
echo "📋 Recent Commits (last 7 days)..."
git log --oneline --since="7 days ago" > "$OUTPUT_DIR/recent_commits.txt"
echo "   Saved to: $OUTPUT_DIR/recent_commits.txt"
echo "   Count: $(wc -l < "$OUTPUT_DIR/recent_commits.txt") commits"

# 2. Changed files
echo ""
echo "📁 Changed Files (last 50 commits)..."
git diff HEAD~50 --name-only 2>/dev/null | sort | uniq > "$OUTPUT_DIR/changed_files.txt"
echo "   Saved to: $OUTPUT_DIR/changed_files.txt"
echo "   Count: $(wc -l < "$OUTPUT_DIR/changed_files.txt") files"

# 3. Director changes
echo ""
echo "🎬 Director.py History..."
git log --oneline -20 -- "**/director.py" > "$OUTPUT_DIR/director_history.txt"
echo "   Saved to: $OUTPUT_DIR/director_history.txt"
echo "   Recent changes: $(wc -l < "$OUTPUT_DIR/director_history.txt")"

# 4. Engine changes
echo ""
echo "⚙️  Engine.py History..."
git log --oneline -20 -- "**/engine.py" > "$OUTPUT_DIR/engine_history.txt"
echo "   Saved to: $OUTPUT_DIR/engine_history.txt"
echo "   Recent changes: $(wc -l < "$OUTPUT_DIR/engine_history.txt")"

# 5. Context-related changes
echo ""
echo "🧠 Context-Related Changes..."
git log --oneline -20 -- "**/context*" "**/prompt*" "**/system*" > "$OUTPUT_DIR/context_history.txt"
echo "   Saved to: $OUTPUT_DIR/context_history.txt"
echo "   Recent changes: $(wc -l < "$OUTPUT_DIR/context_history.txt")"

# 6. History/memory changes
echo ""
echo "📜 History/Memory Changes..."
git log --oneline -20 -- "**/history*" "**/memory*" "**/conversation*" > "$OUTPUT_DIR/memory_history.txt"
echo "   Saved to: $OUTPUT_DIR/memory_history.txt"
echo "   Recent changes: $(wc -l < "$OUTPUT_DIR/memory_history.txt")"

# 7. Local inference changes
echo ""
echo "💻 Local Inference Changes..."
git log --oneline -20 -- "**/local*" "**/inference*" "**/mlx*" > "$OUTPUT_DIR/local_history.txt"
echo "   Saved to: $OUTPUT_DIR/local_history.txt"
echo "   Recent changes: $(wc -l < "$OUTPUT_DIR/local_history.txt")"

# 8. Find suspicious patterns in recent diffs
echo ""
echo "🔎 Searching for suspicious patterns in recent changes..."

echo "" > "$OUTPUT_DIR/suspicious_patterns.txt"

# Look for removed lines that might matter
echo "--- Removed important-looking lines ---" >> "$OUTPUT_DIR/suspicious_patterns.txt"
git diff HEAD~20 | grep "^-" | grep -iE "history|context|entity|prompt|system|memory" | head -50 >> "$OUTPUT_DIR/suspicious_patterns.txt"

echo "" >> "$OUTPUT_DIR/suspicious_patterns.txt"
echo "--- Added lines that might be problematic ---" >> "$OUTPUT_DIR/suspicious_patterns.txt"
git diff HEAD~20 | grep "^+" | grep -iE "pass|todo|fixme|hack|skip|disable" | head -50 >> "$OUTPUT_DIR/suspicious_patterns.txt"

echo "   Saved to: $OUTPUT_DIR/suspicious_patterns.txt"

# 9. Current branch status
echo ""
echo "🌿 Branch Status..."
echo "   Current branch: $(git branch --show-current)"
echo "   Uncommitted changes: $(git status --porcelain | wc -l)"
echo "   Last commit: $(git log -1 --oneline)"

# 10. Summary
echo ""
echo "============================"
echo "📊 FORENSICS SUMMARY"
echo "============================"
echo ""
echo "Files to review:"
echo "  $OUTPUT_DIR/recent_commits.txt"
echo "  $OUTPUT_DIR/changed_files.txt"
echo "  $OUTPUT_DIR/director_history.txt"
echo "  $OUTPUT_DIR/engine_history.txt"
echo "  $OUTPUT_DIR/context_history.txt"
echo "  $OUTPUT_DIR/memory_history.txt"
echo "  $OUTPUT_DIR/local_history.txt"
echo "  $OUTPUT_DIR/suspicious_patterns.txt"
echo ""
echo "Most likely culprits (recently changed critical files):"
git diff HEAD~20 --name-only | grep -E "director|engine|context|history|memory|local" | sort | uniq
echo ""
echo "Run 'cat $OUTPUT_DIR/suspicious_patterns.txt' to see suspicious changes"
