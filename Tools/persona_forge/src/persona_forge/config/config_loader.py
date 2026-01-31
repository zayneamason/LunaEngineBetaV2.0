"""
Configuration loader for Persona Forge training targets.

Manages LLM-specific configurations including:
- Target personality profiles
- Base personality characteristics
- Training parameters (LoRA rank, alpha, etc.)
"""

import json
from pathlib import Path
from typing import Any, Optional


# Default Luna target profile
DEFAULT_TARGET_PROFILE = {
    "warmth": 0.85,
    "technical": 0.70,
    "humor": 0.65,
    "directness": 0.80,
    "creativity": 0.70,
    "reflection": 0.75,
    "relationship": 0.90,
    "assertiveness": 0.75,
}

# Required personality dimensions
REQUIRED_DIMENSIONS = [
    "warmth",
    "technical",
    "humor",
    "directness",
    "creativity",
    "reflection",
    "relationship",
    "assertiveness",
]


class ConfigLoader:
    """
    Load and validate training target configurations.

    Supports multiple LLM targets with specific personality profiles
    and training parameters.
    """

    def __init__(self, config_path: Optional[Path] = None):
        """
        Initialize configuration loader.

        Args:
            config_path: Path to training_targets.json
                        Defaults to config/training_targets.json
        """
        if config_path is None:
            # Find config relative to this file's package
            config_path = (
                Path(__file__).parent.parent.parent.parent /
                "config" / "training_targets.json"
            )

        self.config_path = Path(config_path)
        self._configs: dict[str, dict] = {}

        if self.config_path.exists():
            self._load_configs()
        else:
            print(f"Warning: Config file not found: {self.config_path}")

    def _load_configs(self) -> None:
        """Load configurations from JSON file."""
        with open(self.config_path, 'r', encoding='utf-8') as f:
            self._configs = json.load(f)

        # Validate all configs
        for llm_name, config in self._configs.items():
            self._validate_config(llm_name, config)

    def _validate_config(self, llm_name: str, config: dict[str, Any]) -> None:
        """
        Validate configuration structure.

        Args:
            llm_name: Name of the LLM configuration
            config: Configuration dictionary

        Raises:
            ValueError: If config is invalid
        """
        required_fields = [
            "model_path",
            "personality_profile",
            "base_personality",
            "training_params",
        ]

        for field in required_fields:
            if field not in config:
                raise ValueError(
                    f"Config for '{llm_name}' missing required field: {field}"
                )

        # Validate personality profile
        profile = config["personality_profile"]
        for dim in REQUIRED_DIMENSIONS:
            if dim not in profile:
                raise ValueError(
                    f"Config for '{llm_name}' personality_profile "
                    f"missing dimension: {dim}"
                )

            if not isinstance(profile[dim], (int, float)):
                raise ValueError(
                    f"Config for '{llm_name}' personality_profile[{dim}] "
                    f"must be a number, got: {type(profile[dim])}"
                )

            if not 0 <= profile[dim] <= 1:
                raise ValueError(
                    f"Config for '{llm_name}' personality_profile[{dim}] "
                    f"out of range: {profile[dim]} (must be 0-1)"
                )

        # Validate base personality (same dimensions, but 'note' is optional)
        base = config["base_personality"]
        for dim in REQUIRED_DIMENSIONS:
            if dim not in base:
                raise ValueError(
                    f"Config for '{llm_name}' base_personality "
                    f"missing dimension: {dim}"
                )

    def get_config(self, llm_name: str) -> dict[str, Any]:
        """
        Get full configuration for specific LLM.

        Args:
            llm_name: Name of the LLM configuration

        Returns:
            Full configuration dictionary

        Raises:
            ValueError: If LLM name is unknown
        """
        if llm_name not in self._configs:
            available = list(self._configs.keys())
            raise ValueError(
                f"Unknown LLM: '{llm_name}'. "
                f"Available: {', '.join(available)}"
            )

        return self._configs[llm_name]

    def list_llms(self) -> list[str]:
        """
        List available LLM configurations.

        Returns:
            List of LLM configuration names
        """
        return list(self._configs.keys())

    def get_personality_profile(self, llm_name: str) -> dict[str, float]:
        """
        Get target personality profile for LLM.

        Args:
            llm_name: Name of the LLM configuration

        Returns:
            Target personality profile dictionary
        """
        config = self.get_config(llm_name)
        return config["personality_profile"]

    def get_base_personality(self, llm_name: str) -> dict[str, Any]:
        """
        Get base personality characteristics for LLM.

        This describes the model's natural tendencies before fine-tuning.

        Args:
            llm_name: Name of the LLM configuration

        Returns:
            Base personality dictionary (includes 'note' explaining characteristics)
        """
        config = self.get_config(llm_name)
        return config["base_personality"]

    def get_training_params(self, llm_name: str) -> dict[str, Any]:
        """
        Get training parameters for LLM.

        Args:
            llm_name: Name of the LLM configuration

        Returns:
            Training parameters (rank, alpha, learning_rate, etc.)
        """
        config = self.get_config(llm_name)
        return config["training_params"]

    def get_model_path(self, llm_name: str) -> str:
        """
        Get HuggingFace model path for LLM.

        Args:
            llm_name: Name of the LLM configuration

        Returns:
            HuggingFace model identifier
        """
        config = self.get_config(llm_name)
        return config["model_path"]

    def get_description(self, llm_name: str) -> str:
        """
        Get human-readable description for LLM.

        Args:
            llm_name: Name of the LLM configuration

        Returns:
            Description string
        """
        config = self.get_config(llm_name)
        return config.get("description", "")

    def compute_training_focus(self, llm_name: str) -> dict[str, float]:
        """
        Compute which personality dimensions need the most training.

        Returns the gap between target and base personality for each dimension.
        Higher values = needs more training focus.

        Args:
            llm_name: Name of the LLM configuration

        Returns:
            Dictionary of dimension -> training gap
        """
        target = self.get_personality_profile(llm_name)
        base = self.get_base_personality(llm_name)

        focus = {}
        for dim in REQUIRED_DIMENSIONS:
            gap = target[dim] - base.get(dim, 0.5)
            focus[dim] = max(0, gap)  # Only positive gaps (need improvement)

        return focus


# Convenience functions
def load_training_config(llm_name: str) -> dict[str, Any]:
    """
    Load training configuration for specific LLM.

    Convenience function that creates a ConfigLoader and gets the config.

    Args:
        llm_name: Name of the LLM configuration

    Returns:
        Full configuration dictionary
    """
    loader = ConfigLoader()
    return loader.get_config(llm_name)


def get_available_llms() -> list[str]:
    """
    Get list of available LLM configurations.

    Returns:
        List of LLM configuration names
    """
    loader = ConfigLoader()
    return loader.list_llms()


def get_default_target_profile() -> dict[str, float]:
    """
    Get the default Luna target personality profile.

    Returns:
        Default target profile dictionary
    """
    return DEFAULT_TARGET_PROFILE.copy()
