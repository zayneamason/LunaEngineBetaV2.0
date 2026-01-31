"""
Persona Forge - Main Entry Point

Enables execution via: python -m persona_forge

This module serves as the entry point when running the package
directly as a module, providing access to the CLI interface.
"""

from .cli import main

if __name__ == "__main__":
    main()
