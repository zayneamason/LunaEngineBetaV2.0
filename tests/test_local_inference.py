"""
Tests for Local Inference (MLX + Qwen 3B)
=========================================

Tests for the local inference module.
Note: Full integration tests require mlx-lm to be installed.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch


class TestInferenceConfig:
    """Tests for InferenceConfig."""

    def test_default_config(self):
        """Test default configuration values."""
        from luna.inference.local import InferenceConfig

        config = InferenceConfig()

        assert config.model_id == "Qwen/Qwen2.5-3B-Instruct"
        assert config.max_tokens == 512
        assert config.temperature == 0.7
        assert config.use_4bit is True
        assert config.hot_path_timeout_ms == 200

    def test_custom_config(self):
        """Test custom configuration."""
        from luna.inference.local import InferenceConfig

        config = InferenceConfig(
            model_id="custom/model",
            max_tokens=1024,
            temperature=0.5,
            use_4bit=False,
        )

        assert config.model_id == "custom/model"
        assert config.max_tokens == 1024
        assert config.temperature == 0.5
        assert config.use_4bit is False


class TestGenerationResult:
    """Tests for GenerationResult."""

    def test_generation_result(self):
        """Test generation result dataclass."""
        from luna.inference.local import GenerationResult

        result = GenerationResult(
            text="Hello world",
            tokens=5,
            latency_ms=100.5,
            tokens_per_second=50.0,
        )

        assert result.text == "Hello world"
        assert result.tokens == 5
        assert result.latency_ms == 100.5
        assert result.tokens_per_second == 50.0
        assert result.from_cache is False


class TestLocalInference:
    """Tests for LocalInference class."""

    def test_init(self):
        """Test initialization."""
        from luna.inference.local import LocalInference, InferenceConfig

        inference = LocalInference()
        assert inference.config is not None
        assert inference._loaded is False
        assert inference._stream_callbacks == []

    def test_init_with_config(self):
        """Test initialization with custom config."""
        from luna.inference.local import LocalInference, InferenceConfig

        config = InferenceConfig(max_tokens=256)
        inference = LocalInference(config=config)

        assert inference.config.max_tokens == 256

    def test_is_loaded_false_initially(self):
        """Test is_loaded property."""
        from luna.inference.local import LocalInference

        inference = LocalInference()
        assert inference.is_loaded is False

    def test_stream_callbacks(self):
        """Test stream callback registration."""
        from luna.inference.local import LocalInference

        inference = LocalInference()

        callback = MagicMock()
        inference.on_stream(callback)

        assert callback in inference._stream_callbacks

        inference.remove_stream_callback(callback)
        assert callback not in inference._stream_callbacks

    def test_get_stats(self):
        """Test get_stats method."""
        from luna.inference.local import LocalInference

        inference = LocalInference()
        stats = inference.get_stats()

        assert stats["loaded"] is False
        assert stats["model"] is None
        assert stats["generation_count"] == 0
        assert stats["total_tokens"] == 0

    def test_format_prompt_basic(self):
        """Test prompt formatting."""
        from luna.inference.local import LocalInference

        inference = LocalInference()
        # Mock tokenizer without chat template
        inference._tokenizer = MagicMock(spec=[])

        prompt = inference._format_prompt("Hello", "You are Luna")

        assert "<|im_start|>system" in prompt
        assert "You are Luna" in prompt
        assert "<|im_start|>user" in prompt
        assert "Hello" in prompt
        assert "<|im_start|>assistant" in prompt


class TestHybridInference:
    """Tests for HybridInference class."""

    def test_init(self):
        """Test initialization."""
        from luna.inference.local import HybridInference, LocalInference

        local = LocalInference()
        hybrid = HybridInference(local)

        assert hybrid.local is local
        # Default threshold is 0.15 (low) - delegate most queries to Claude
        assert hybrid.complexity_threshold == 0.15
        assert hybrid._local_count == 0
        assert hybrid._cloud_count == 0

    def test_estimate_complexity_simple(self):
        """Test complexity estimation for simple queries."""
        from luna.inference.local import HybridInference

        hybrid = HybridInference()

        # Simple greeting should be low complexity
        score = hybrid.estimate_complexity("Hi there!")
        assert score < 0.3

        # Single word
        score = hybrid.estimate_complexity("Hello")
        assert score < 0.2

    def test_estimate_complexity_complex(self):
        """Test complexity estimation for complex queries."""
        from luna.inference.local import HybridInference

        hybrid = HybridInference()

        # Complex multi-part question
        score = hybrid.estimate_complexity(
            "Can you explain how the neural network architecture works? "
            "What are the implications for training? "
            "How does this compare to other approaches?"
        )
        assert score > 0.5

        # Code request
        score = hybrid.estimate_complexity(
            "Please implement a function that calculates fibonacci numbers"
        )
        assert score > 0.4

    def test_estimate_complexity_code_blocks(self):
        """Test complexity estimation with code blocks."""
        from luna.inference.local import HybridInference

        hybrid = HybridInference()

        score = hybrid.estimate_complexity(
            "Debug this code:\n```python\ndef foo():\n    pass\n```"
        )
        assert score > 0.4

    def test_should_use_local_simple(self):
        """Test routing decision for simple queries."""
        from luna.inference.local import HybridInference, LocalInference

        # Mock local as available
        local = LocalInference()
        hybrid = HybridInference(local)

        # Simple query should use local (but won't because local not loaded)
        result = hybrid.should_use_local("Hello!")
        assert result is False  # MLX not available in test environment

    def test_get_stats(self):
        """Test get_stats method."""
        from luna.inference.local import HybridInference

        hybrid = HybridInference()
        hybrid._local_count = 5
        hybrid._cloud_count = 3

        stats = hybrid.get_stats()

        assert stats["local_count"] == 5
        assert stats["cloud_count"] == 3
        assert stats["local_percentage"] == 62.5


class TestDirectorIntegration:
    """Tests for Director integration with local inference."""

    @pytest.fixture
    def director(self):
        """Create director for testing."""
        from luna.actors.director import DirectorActor

        return DirectorActor(enable_local=False)  # Disable local for tests

    def test_director_local_disabled(self, director):
        """Test director with local disabled."""
        assert director._enable_local is False
        assert director.local_available is False

    def test_director_routing_stats(self, director):
        """Test routing stats method."""
        stats = director.get_routing_stats()

        assert "local_generations" in stats
        assert "delegated_generations" in stats
        assert "local_available" in stats

    @pytest.mark.asyncio
    async def test_director_snapshot(self, director):
        """Test snapshot includes local stats."""
        snapshot = await director.snapshot()

        assert "local_available" in snapshot
        assert "local_generations" in snapshot
        assert "delegated_generations" in snapshot
