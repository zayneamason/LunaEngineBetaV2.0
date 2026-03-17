"""
Security utilities for MCP — path validation, extension checks.
================================================================

Security hardening:
- Rejects null bytes
- Rejects absolute paths
- Rejects traversal attempts
- Uses Path.is_relative_to() for containment
- Enforces allowed file extensions
"""

import os
from pathlib import Path
from typing import Set

from luna.core.paths import project_root

# Configuration - resolve to project root
LUNA_BASE_PATH = str(project_root())

ALLOWED_EXTENSIONS: Set[str] = {
    # Documentation
    '.md', '.txt', '.rst',
    # Data formats
    '.json', '.yaml', '.yml', '.toml',
    # Python
    '.py', '.pyi',
    # JavaScript/TypeScript
    '.js', '.ts', '.jsx', '.tsx', '.mjs', '.cjs',
    # Web
    '.html', '.css', '.scss', '.less',
    # Database
    '.sql',
    # Config
    '.ini', '.cfg', '.conf', '.env.example',
    # Shell
    '.sh', '.bash', '.zsh',
    # Other
    '.gitignore', '.dockerignore',
}

# Explicitly forbidden extensions (even if extensionless)
FORBIDDEN_PATTERNS: Set[str] = {
    '.env',       # Environment secrets
    '.pem',       # Private keys
    '.key',       # Private keys
    '.crt',       # Certificates (might contain private data)
    '.p12',       # PKCS12 keystores
    '.pfx',       # PKCS12 keystores
    '.sqlite',    # Could contain sensitive data - use API instead
    '.db',        # Could contain sensitive data
}


def validate_path(relative_path: str) -> Path:
    """
    Validate path is within allowed directory.

    Security hardening:
    - Rejects null bytes
    - Rejects absolute paths
    - Rejects traversal attempts
    - Uses Path.is_relative_to() for containment

    Args:
        relative_path: Path relative to LUNA_BASE_PATH

    Returns:
        Resolved absolute Path

    Raises:
        ValueError: If path is invalid or escapes base directory
    """
    # Null byte injection protection
    if '\x00' in relative_path:
        raise ValueError("Path contains null bytes")

    # Strip whitespace
    relative_path = relative_path.strip()

    # Reject empty paths
    if not relative_path:
        raise ValueError("Empty path not allowed")

    # Reject absolute paths
    if relative_path.startswith('/') or relative_path.startswith('\\'):
        raise ValueError("Absolute paths not allowed")

    # Windows drive letters
    if len(relative_path) >= 2 and relative_path[1] == ':':
        raise ValueError("Windows absolute paths not allowed")

    # Path traversal protection
    if '..' in relative_path:
        raise ValueError("Path traversal not allowed")

    # Resolve base and full path
    base = Path(LUNA_BASE_PATH).resolve()
    full_path = (base / relative_path).resolve()

    # Verify containment
    try:
        full_path.relative_to(base)
    except ValueError:
        raise ValueError("Path escapes base directory")

    return full_path


def check_extension(path: Path) -> None:
    """
    Check if file extension is allowed.

    Args:
        path: Path to check

    Raises:
        ValueError: If extension is not in ALLOWED_EXTENSIONS or is forbidden
    """
    suffix = path.suffix.lower()

    # Check forbidden first
    if suffix in FORBIDDEN_PATTERNS:
        raise ValueError(
            f"Extension '{suffix}' is forbidden for security reasons"
        )

    # Allow files without extension (like Makefile, Dockerfile)
    if suffix == '':
        return

    # Check allowed extensions
    if suffix not in ALLOWED_EXTENSIONS:
        raise ValueError(
            f"Extension '{suffix}' not allowed. "
            f"Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
        )


def get_base_path() -> Path:
    """Get the resolved base path."""
    return Path(LUNA_BASE_PATH).resolve()
