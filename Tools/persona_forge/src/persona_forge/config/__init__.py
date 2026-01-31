"""
Configuration module for Persona Forge.

Provides LLM-specific training target configurations.
"""

from .config_loader import (
    ConfigLoader,
    load_training_config,
    get_available_llms,
    get_default_target_profile,
    DEFAULT_TARGET_PROFILE,
    REQUIRED_DIMENSIONS,
)

__all__ = [
    "ConfigLoader",
    "load_training_config",
    "get_available_llms",
    "get_default_target_profile",
    "DEFAULT_TARGET_PROFILE",
    "REQUIRED_DIMENSIONS",
]
