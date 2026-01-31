"""
Text preprocessing for TTS synthesis in Luna Engine.

Cleans text of special characters and formatting that TTS engines
would otherwise read aloud (e.g., "asterisk", "hash", "backtick").

This module handles:
- Markdown formatting (emphasis, headers, code blocks)
- Special characters that TTS engines verbalize
- Whitespace normalization
- URL and link handling

Architecture note:
    This sits between response generation and TTS synthesis.
    The TTSManager calls preprocess() before passing text to providers.
"""
import logging
import re
from dataclasses import dataclass, field
from typing import List, Pattern, Tuple

logger = logging.getLogger(__name__)


@dataclass
class PreprocessingRule:
    """A single text preprocessing rule."""
    name: str
    pattern: Pattern
    replacement: str
    flags: int = 0
    description: str = ""


@dataclass
class PreprocessingConfig:
    """Configuration for text preprocessing behavior."""
    # Strip markdown formatting
    strip_markdown: bool = True

    # Strip code blocks entirely (vs keeping content)
    strip_code_blocks: bool = True

    # Keep content inside inline code (`code` -> code)
    keep_inline_code_content: bool = True

    # Strip URLs from links (keep link text only)
    strip_link_urls: bool = True

    # Normalize whitespace (collapse multiple spaces)
    normalize_whitespace: bool = True

    # Custom patterns to strip (compiled regex patterns)
    custom_strip_patterns: List[str] = field(default_factory=list)


class TextPreprocessor:
    """
    Preprocesses text for TTS synthesis.

    Removes or transforms formatting and special characters that
    TTS engines would read aloud. Designed to be configurable
    for different use cases (full cleanup vs. minimal).

    Example:
        preprocessor = TextPreprocessor()
        clean_text = preprocessor.preprocess("*Hello* world!")
        # Returns: "Hello world!"
    """

    def __init__(self, config: PreprocessingConfig = None):
        """
        Initialize preprocessor with configuration.

        Args:
            config: PreprocessingConfig or None for defaults
        """
        self.config = config or PreprocessingConfig()
        self._rules = self._build_rules()

    def _build_rules(self) -> List[PreprocessingRule]:
        """Build preprocessing rules based on configuration."""
        rules = []

        if self.config.strip_markdown:
            rules.extend(self._markdown_rules())

        if self.config.strip_link_urls:
            rules.extend(self._link_rules())

        # Always apply special character cleanup
        rules.extend(self._special_char_rules())

        if self.config.normalize_whitespace:
            rules.extend(self._whitespace_rules())

        return rules

    def _markdown_rules(self) -> List[PreprocessingRule]:
        """Rules for stripping markdown formatting."""
        rules = []

        # Code blocks (```...```) - remove entirely or keep content
        if self.config.strip_code_blocks:
            rules.append(PreprocessingRule(
                name="code_blocks",
                pattern=re.compile(r'```[\s\S]*?```'),
                replacement="",
                description="Remove fenced code blocks"
            ))

        # Inline code (`code`) - optionally keep content
        if self.config.keep_inline_code_content:
            rules.append(PreprocessingRule(
                name="inline_code",
                pattern=re.compile(r'`([^`]+)`'),
                replacement=r'\1',
                description="Strip backticks, keep content"
            ))
        else:
            rules.append(PreprocessingRule(
                name="inline_code",
                pattern=re.compile(r'`[^`]+`'),
                replacement="",
                description="Remove inline code entirely"
            ))

        # Strikethrough ~~text~~
        rules.append(PreprocessingRule(
            name="strikethrough",
            pattern=re.compile(r'~~([^~]+)~~'),
            replacement=r'\1',
            description="Remove strikethrough markers"
        ))

        # Bold **text** and __text__
        rules.append(PreprocessingRule(
            name="bold_asterisk",
            pattern=re.compile(r'\*\*([^*]+)\*\*'),
            replacement=r'\1',
            description="Remove bold asterisks"
        ))
        rules.append(PreprocessingRule(
            name="bold_underscore",
            pattern=re.compile(r'__([^_]+)__'),
            replacement=r'\1',
            description="Remove bold underscores"
        ))

        # Italic *text* and _text_
        rules.append(PreprocessingRule(
            name="italic_asterisk",
            pattern=re.compile(r'\*([^*]+)\*'),
            replacement=r'\1',
            description="Remove italic asterisks"
        ))
        rules.append(PreprocessingRule(
            name="italic_underscore",
            pattern=re.compile(r'(?<!\w)_([^_]+)_(?!\w)'),
            replacement=r'\1',
            description="Remove italic underscores"
        ))

        # Headers (# ## ### etc.)
        rules.append(PreprocessingRule(
            name="headers",
            pattern=re.compile(r'^#{1,6}\s*', re.MULTILINE),
            replacement="",
            description="Remove markdown headers"
        ))

        # List markers (- * • at line start)
        rules.append(PreprocessingRule(
            name="list_markers",
            pattern=re.compile(r'^[\-\*•]\s+', re.MULTILINE),
            replacement="",
            description="Remove list markers"
        ))

        # Blockquotes (> at line start)
        rules.append(PreprocessingRule(
            name="blockquotes",
            pattern=re.compile(r'^>\s*', re.MULTILINE),
            replacement="",
            description="Remove blockquote markers"
        ))

        # Horizontal rules (---, ***, ___)
        rules.append(PreprocessingRule(
            name="horizontal_rules",
            pattern=re.compile(r'^[\-\*_]{3,}\s*$', re.MULTILINE),
            replacement="",
            description="Remove horizontal rules"
        ))

        return rules

    def _link_rules(self) -> List[PreprocessingRule]:
        """Rules for handling links."""
        return [
            # Markdown links [text](url) -> text
            PreprocessingRule(
                name="markdown_links",
                pattern=re.compile(r'\[([^\]]+)\]\([^)]+\)'),
                replacement=r'\1',
                description="Keep link text, remove URL"
            ),
            # Image markdown ![alt](url) -> alt text or nothing
            PreprocessingRule(
                name="images",
                pattern=re.compile(r'!\[([^\]]*)\]\([^)]+\)'),
                replacement=r'\1',
                description="Keep image alt text, remove URL"
            ),
            # Bare URLs - remove or describe
            PreprocessingRule(
                name="bare_urls",
                pattern=re.compile(r'https?://[^\s<>\[\]]+'),
                replacement="",
                description="Remove bare URLs"
            ),
        ]

    def _special_char_rules(self) -> List[PreprocessingRule]:
        """Rules for special characters TTS would read aloud."""
        return [
            # Single tilde emphasis ~text~ (not double strikethrough)
            PreprocessingRule(
                name="single_tilde",
                pattern=re.compile(r'(?<![~])~([^~]+)~(?![~])'),
                replacement=r'\1',
                description="Remove single tilde emphasis"
            ),
            # Hash before numbers (#1, #42) - TTS would say "hash one"
            PreprocessingRule(
                name="hash_number",
                pattern=re.compile(r'#(\d)'),
                replacement=r'\1',
                description="Remove hash before numbers"
            ),
            # Standalone special chars (not part of words)
            PreprocessingRule(
                name="standalone_specials",
                pattern=re.compile(r'(?<!\w)[*#~`^|\\](?!\w)'),
                replacement="",
                description="Remove standalone special characters"
            ),
            # Angle bracket placeholders <something>
            PreprocessingRule(
                name="angle_brackets",
                pattern=re.compile(r'<[^>]+>'),
                replacement="",
                description="Remove angle bracket placeholders"
            ),
            # Pipe characters (tables)
            PreprocessingRule(
                name="pipes",
                pattern=re.compile(r'\|'),
                replacement=" ",
                description="Replace pipes with spaces"
            ),
            # Backslash escapes
            PreprocessingRule(
                name="backslashes",
                pattern=re.compile(r'\\([^\s])'),
                replacement=r'\1',
                description="Remove escape backslashes"
            ),
            # Multiple dashes (em-dash style) -> single pause
            PreprocessingRule(
                name="multiple_dashes",
                pattern=re.compile(r'--+'),
                replacement=" - ",
                description="Normalize multiple dashes"
            ),
            # Ellipsis normalization
            PreprocessingRule(
                name="ellipsis",
                pattern=re.compile(r'\.{3,}'),
                replacement="...",
                description="Normalize ellipsis"
            ),
        ]

    def _whitespace_rules(self) -> List[PreprocessingRule]:
        """Rules for whitespace normalization."""
        return [
            # Multiple spaces -> single space
            PreprocessingRule(
                name="multiple_spaces",
                pattern=re.compile(r'[ \t]+'),
                replacement=" ",
                description="Collapse multiple spaces"
            ),
            # Multiple newlines -> double newline
            PreprocessingRule(
                name="multiple_newlines",
                pattern=re.compile(r'\n{3,}'),
                replacement="\n\n",
                description="Normalize multiple newlines"
            ),
        ]

    def preprocess(self, text: str) -> str:
        """
        Preprocess text for TTS synthesis.

        Applies all configured rules to clean the text of
        formatting and special characters.

        Args:
            text: Raw text possibly containing markdown/special chars

        Returns:
            Cleaned text suitable for speech synthesis
        """
        if not text:
            return text

        original_len = len(text)

        # Apply each rule in order
        for rule in self._rules:
            text = rule.pattern.sub(rule.replacement, text)

        # Final trim
        text = text.strip()

        # Log if significant changes were made
        if len(text) < original_len * 0.8:
            logger.debug(
                f"Preprocessing removed {original_len - len(text)} chars "
                f"({100 - (len(text) / original_len * 100):.1f}%)"
            )

        return text

    def add_rule(self, rule: PreprocessingRule) -> None:
        """
        Add a custom preprocessing rule.

        Args:
            rule: PreprocessingRule to add
        """
        self._rules.append(rule)
        logger.debug(f"Added custom preprocessing rule: {rule.name}")


# Module-level default instance for convenience
_default_preprocessor = None


def get_preprocessor(config: PreprocessingConfig = None) -> TextPreprocessor:
    """
    Get a TextPreprocessor instance.

    Args:
        config: Optional configuration. If None, returns default instance.

    Returns:
        TextPreprocessor instance
    """
    global _default_preprocessor

    if config is not None:
        return TextPreprocessor(config)

    if _default_preprocessor is None:
        _default_preprocessor = TextPreprocessor()

    return _default_preprocessor


def preprocess_for_speech(text: str) -> str:
    """
    Convenience function for preprocessing text for TTS.

    Uses default configuration. For custom configuration,
    use TextPreprocessor directly.

    Args:
        text: Raw text to preprocess

    Returns:
        Cleaned text for speech synthesis
    """
    return get_preprocessor().preprocess(text)
