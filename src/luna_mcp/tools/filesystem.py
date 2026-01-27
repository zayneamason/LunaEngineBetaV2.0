"""
Filesystem tools — luna_read, luna_write, luna_list
====================================================

Provides secure filesystem access within the Luna project directory.
All paths are validated to prevent traversal attacks.
"""

from pathlib import Path
from typing import List

from luna_mcp.models import ReadFileInput, WriteFileInput, ListDirInput
from luna_mcp.security import validate_path, check_extension, LUNA_BASE_PATH


async def luna_read(path: str) -> str:
    """
    Read a file from the project folder.

    Args:
        path: Relative path to file within project

    Returns:
        File contents or error message
    """
    try:
        full_path = validate_path(path)
        if not full_path.exists():
            return f"Error: File not found: {path}"
        if not full_path.is_file():
            return f"Error: Not a file: {path}"
        check_extension(full_path)
        return full_path.read_text(encoding='utf-8')
    except Exception as e:
        return f"Error: {str(e)}"


async def luna_write(path: str, content: str, create_dirs: bool = True) -> str:
    """
    Write content to a file in the project folder.

    Args:
        path: Relative path to file within project
        content: Content to write
        create_dirs: Create parent directories if they don't exist

    Returns:
        Success message or error
    """
    try:
        full_path = validate_path(path)
        check_extension(full_path)
        if create_dirs:
            full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content, encoding='utf-8')
        size = len(content.encode('utf-8'))
        return f"✓ Written {size} bytes to {path}"
    except Exception as e:
        return f"Error: {str(e)}"


async def luna_list(path: str = "", recursive: bool = False, max_depth: int = 3) -> str:
    """
    List contents of a directory in the project folder.

    Args:
        path: Relative path to directory (empty for project root)
        recursive: Recursively list subdirectories
        max_depth: Maximum depth for recursive listing

    Returns:
        Formatted directory listing or error
    """
    try:
        full_path = validate_path(path) if path else Path(LUNA_BASE_PATH)
        if not full_path.exists():
            return f"Error: Directory not found: {path or '/'}"
        if not full_path.is_dir():
            return f"Error: Not a directory: {path}"

        def list_dir(dir_path: Path, prefix: str = "", depth: int = 0) -> List[str]:
            if depth >= max_depth:
                return [f"{prefix}..."]
            items = []
            try:
                entries = sorted(dir_path.iterdir(), key=lambda x: (x.is_file(), x.name.lower()))
            except PermissionError:
                return [f"{prefix}[permission denied]"]

            for i, entry in enumerate(entries):
                # Skip hidden files and common ignore patterns
                if entry.name.startswith('.') and entry.name not in ['.gitignore']:
                    continue
                if entry.name in ['__pycache__', 'node_modules', '.git', '.venv', 'venv']:
                    continue

                is_last = i == len(entries) - 1
                connector = "└── " if is_last else "├── "
                if entry.is_dir():
                    items.append(f"{prefix}{connector}📁 {entry.name}/")
                    if recursive:
                        extension = "    " if is_last else "│   "
                        items.extend(list_dir(entry, prefix + extension, depth + 1))
                else:
                    size = entry.stat().st_size
                    if size < 1024:
                        size_str = f"{size}B"
                    elif size < 1024 * 1024:
                        size_str = f"{size / 1024:.1f}KB"
                    else:
                        size_str = f"{size / (1024 * 1024):.1f}MB"
                    items.append(f"{prefix}{connector}📄 {entry.name} ({size_str})")
            return items

        lines = [f"📁 {path or 'Project'}/"]
        lines.extend(list_dir(full_path))
        return "\n".join(lines)
    except Exception as e:
        return f"Error: {str(e)}"
