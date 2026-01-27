"""
Git tools — git_sync
====================

Tools for Git operations within the Luna project.
"""

import subprocess
from pathlib import Path
from typing import Optional

from luna_mcp.security import LUNA_BASE_PATH


async def luna_git_sync(message: Optional[str] = None, push: bool = True) -> str:
    """
    Sync changes with Git (add, commit, push).

    Args:
        message: Commit message (optional, will auto-generate if not provided)
        push: Whether to push to remote after commit

    Returns:
        Status message
    """
    project_path = Path(LUNA_BASE_PATH)

    try:
        # Check if we're in a git repo
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=project_path,
            capture_output=True,
            text=True,
            timeout=30
        )

        if result.returncode != 0:
            return f"Error: Not a git repository or git not available"

        changes = result.stdout.strip()
        if not changes:
            return "✓ No changes to commit"

        # Count changes
        lines = changes.split('\n') if changes else []
        change_count = len(lines)

        # Stage all changes
        result = subprocess.run(
            ["git", "add", "-A"],
            cwd=project_path,
            capture_output=True,
            text=True,
            timeout=30
        )
        if result.returncode != 0:
            return f"Error staging changes: {result.stderr}"

        # Create commit message if not provided
        if not message:
            message = f"Luna sync: {change_count} file(s) changed"

        # Commit
        result = subprocess.run(
            ["git", "commit", "-m", message],
            cwd=project_path,
            capture_output=True,
            text=True,
            timeout=30
        )
        if result.returncode != 0:
            # Check if it's just "nothing to commit"
            if "nothing to commit" in result.stdout or "nothing to commit" in result.stderr:
                return "✓ No changes to commit"
            return f"Error committing: {result.stderr}"

        output_lines = [f"✓ Committed: {message}"]

        # Push if requested
        if push:
            result = subprocess.run(
                ["git", "push"],
                cwd=project_path,
                capture_output=True,
                text=True,
                timeout=60
            )
            if result.returncode != 0:
                output_lines.append(f"⚠️ Push failed: {result.stderr}")
            else:
                output_lines.append("✓ Pushed to remote")

        return "\n".join(output_lines)

    except subprocess.TimeoutExpired:
        return "Error: Git operation timed out"
    except Exception as e:
        return f"Error: {str(e)}"


async def luna_git_status() -> str:
    """
    Get current git status.

    Returns:
        Formatted git status
    """
    project_path = Path(LUNA_BASE_PATH)

    try:
        # Get status
        result = subprocess.run(
            ["git", "status", "--short", "--branch"],
            cwd=project_path,
            capture_output=True,
            text=True,
            timeout=30
        )

        if result.returncode != 0:
            return f"Error: {result.stderr}"

        output = result.stdout.strip()
        if not output:
            return "✓ Clean working directory"

        return f"Git Status:\n```\n{output}\n```"

    except Exception as e:
        return f"Error: {str(e)}"
