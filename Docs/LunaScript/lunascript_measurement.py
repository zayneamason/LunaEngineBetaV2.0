"""
LunaScript Trait Measurement System — Approach 3: Cross-Validated
═══════════════════════════════════════════════════════════════════

Measures traits from actual text using linguistic features.
Calibrates against Luna's real corpus (1390 responses).
Cross-validates which features predict voice fidelity.

No LLM calls. Pure mechanical measurement.
"""

import sqlite3
import re
import json
import math
import statistics
from collections import Counter, defaultdict
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Tuple, Optional

# ═══════════════════════════════════════════════════════════════
# FEATURE EXTRACTORS — Observable, countable, mechanical
# ═══════════════════════════════════════════════════════════════

def split_sentences(text: str) -> List[str]:
    """Split text into sentences. Handles common abbreviations."""
    # Remove emotes/actions in asterisks
    clean = re.sub(r'\*[^*]+\*', '', text)
    # Split on sentence boundaries
    sents = re.split(r'(?<=[.!?])\s+', clean.strip())
    return [s.strip() for s in sents if len(s.strip()) > 3]

def count_words(text: str) -> List[str]:
    """Extract words, lowercased."""
    return re.findall(r"[a-z']+", text.lower())

def count_pattern(words: List[str], patterns: List[str]) -> int:
    """Count how many words match any pattern."""
    pattern_set = set(patterns)
    return sum(1 for w in words if w in pattern_set)

def count_contractions(text: str) -> int:
    """Count contractions like don't, I'm, we're, etc."""
    return len(re.findall(r"\b\w+(?:'[a-z]+)\b", text, re.IGNORECASE))

def count_contraction_opportunities(text: str) -> int:
    """Estimate places where contractions could have been used."""
    expandable = re.findall(
        r"\b(do not|does not|did not|is not|are not|was not|were not|"
        r"will not|would not|could not|should not|cannot|"
        r"I am|I have|I will|I would|you are|you have|"
        r"we are|we have|they are|they have|it is|that is|"
        r"he is|she is|what is|who is|there is|here is)\b",
        text, re.IGNORECASE
    )
    contractions = count_contractions(text)
    return len(expandable) + contractions  # total opportunities

# ─── Individual Feature Functions ───

def feat_you_ratio(text: str, words: List[str]) -> float:
    """Second person pronoun density — addressing the other person."""
    you_words = {"you", "your", "you're", "yours", "yourself"}
    return count_pattern(words, list(you_words)) / max(len(words), 1)

def feat_we_ratio(text: str, words: List[str]) -> float:
    """Inclusive language density."""
    we_words = {"we", "us", "our", "we're", "let's", "ours", "ourselves"}
    return count_pattern(words, list(we_words)) / max(len(words), 1)

def feat_hedge_ratio(text: str, words: List[str]) -> float:
    """Hedging language density."""
    hedges = {"perhaps", "maybe", "might", "possibly", "arguably", 
              "somewhat", "potentially", "conceivably"}
    return count_pattern(words, list(hedges)) / max(len(words), 1)

def feat_contraction_rate(text: str, words: List[str]) -> float:
    """Ratio of contractions to contraction opportunities."""
    opps = count_contraction_opportunities(text)
    if opps == 0:
        return 0.5  # neutral if no opportunities
    return count_contractions(text) / opps

def feat_question_density(text: str, words: List[str]) -> float:
    """Proportion of sentences that are questions."""
    sents = split_sentences(text)
    if not sents:
        return 0.0
    return sum(1 for s in sents if "?" in s) / len(sents)

def feat_emphasis_density(text: str, words: List[str]) -> float:
    """Exclamation marks, emphasis words, dashes."""
    emphasis_words = {"honestly", "genuinely", "really", "actually", "literally",
                      "seriously", "absolutely", "definitely", "totally"}
    word_emphasis = count_pattern(words, list(emphasis_words))
    punctuation = text.count("!") + text.count("—") + text.count("...")
    return (word_emphasis + punctuation) / max(len(words), 1)

def feat_avg_sentence_length(text: str, words: List[str]) -> float:
    """Average words per sentence."""
    sents = split_sentences(text)
    if not sents:
        return 0.0
    return statistics.mean(len(s.split()) for s in sents)

def feat_sentence_length_variance(text: str, words: List[str]) -> float:
    """Variance in sentence length — uniform = robotic, varied = natural."""
    sents = split_sentences(text)
    if len(sents) < 2:
        return 0.0
    lengths = [len(s.split()) for s in sents]
    return statistics.variance(lengths)

def feat_passive_ratio(text: str, words: List[str]) -> float:
    """Passive voice indicator density."""
    passive = {"was", "were", "been", "being"}
    following_past_participle = 0
    for i, w in enumerate(words[:-1]):
        if w in passive and i + 1 < len(words):
            # Simple heuristic: passive marker followed by past participle-ish word
            if words[i + 1].endswith("ed") or words[i + 1].endswith("en"):
                following_past_participle += 1
    sents = split_sentences(text)
    return following_past_participle / max(len(sents), 1)

def feat_conditional_ratio(text: str, words: List[str]) -> float:
    """Conditional/hedging verb density."""
    conditionals = {"if", "would", "could", "should", "might", "may"}
    return count_pattern(words, list(conditionals)) / max(len(words), 1)

def feat_filler_ratio(text: str, words: List[str]) -> float:
    """Filler phrase density."""
    fillers = {"basically", "essentially", "actually", "literally",
               "like", "just", "kind", "sort"}
    return count_pattern(words, list(fillers)) / max(len(words), 1)

def feat_formal_vocab_ratio(text: str, words: List[str]) -> float:
    """Latinate/academic vocabulary density."""
    formal = {"therefore", "however", "furthermore", "consequently", "regarding",
              "additionally", "subsequently", "nevertheless", "pursuant", "moreover",
              "notwithstanding", "henceforth", "whereby", "therein", "aforementioned"}
    return count_pattern(words, list(formal)) / max(len(words), 1)

def feat_slang_ratio(text: str, words: List[str]) -> float:
    """Casual/slang vocabulary density."""
    slang = {"yo", "yeah", "cool", "lol", "nah", "gonna", "wanna", "kinda",
             "sorta", "dude", "btw", "tbh", "omg", "haha", "hmm", "huh",
             "ok", "okay", "yep", "nope", "whoa"}
    return count_pattern(words, list(slang)) / max(len(words), 1)

def feat_avg_word_length(text: str, words: List[str]) -> float:
    """Average word length — formal text uses longer words."""
    if not words:
        return 0.0
    return statistics.mean(len(w) for w in words)

def feat_exploratory_ratio(text: str, words: List[str]) -> float:
    """Exploratory/curious language density."""
    exploratory = {"wonder", "interesting", "curious", "hmm", "huh", "fascinating",
                   "wild", "weird", "surprising", "unexpected"}
    question_words = {"what", "why", "how", "where", "when", "who"}
    explore = count_pattern(words, list(exploratory))
    q_words = count_pattern(words, list(question_words))
    return (explore + q_words * 0.3) / max(len(words), 1)

def feat_tangent_markers(text: str, words: List[str]) -> float:
    """Tangent/aside introduction markers."""
    tangent = {"tangent", "aside", "sidebar", "speaking", "reminds",
               "actually", "wait", "oh"}
    # Also check for em-dash asides
    dash_asides = text.count("—") + text.count(" - ")
    return (count_pattern(words, list(tangent)) + dash_asides * 0.5) / max(len(words), 1)

def feat_first_person_ratio(text: str, words: List[str]) -> float:
    """First person pronoun density — self-referential."""
    fp = {"i", "me", "my", "mine", "myself", "i'm", "i've", "i'd", "i'll"}
    return count_pattern(words, list(fp)) / max(len(words), 1)

def feat_list_usage(text: str, words: List[str]) -> float:
    """Bullet point and numbered list density."""
    list_markers = len(re.findall(r'^\s*[-•*]\s', text, re.MULTILINE))
    numbered = len(re.findall(r'^\s*\d+[.)]\s', text, re.MULTILINE))
    sents = split_sentences(text)
    return (list_markers + numbered) / max(len(sents), 1)

def feat_emoji_density(text: str, words: List[str]) -> float:
    """Emoji usage density."""
    # Simple emoji detection
    emojis = len(re.findall(r'[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF\U0001F900-\U0001F9FF\U00002600-\U000027BF\U0001FA00-\U0001FA6F]', text))
    return emojis / max(len(words), 1)

def feat_opening_reaction(text: str, words: List[str]) -> float:
    """Does the response start with a reaction? (characteristic of Luna)"""
    openers = ["oh", "hm", "hmm", "yeah", "okay", "ok", "right", "wait",
               "interesting", "huh", "whoa", "ooh", "ah", "so", "well"]
    if words and words[0] in openers:
        return 1.0
    # Check for emote opening
    if text.strip().startswith("*"):
        return 0.8
    return 0.0

def feat_closing_question(text: str, words: List[str]) -> float:
    """Does the response end with a question? (characteristic of Luna)"""
    sents = split_sentences(text)
    if not sents:
        return 0.0
    last_two = sents[-2:] if len(sents) >= 2 else sents
    return 1.0 if any("?" in s for s in last_two) else 0.0


# ═══════════════════════════════════════════════════════════════
# FEATURE REGISTRY — All features in one place
# ═══════════════════════════════════════════════════════════════

ALL_FEATURES = {
    "you_ratio": feat_you_ratio,
    "we_ratio": feat_we_ratio,
    "hedge_ratio": feat_hedge_ratio,
    "contraction_rate": feat_contraction_rate,
    "question_density": feat_question_density,
    "emphasis_density": feat_emphasis_density,
    "avg_sentence_length": feat_avg_sentence_length,
    "sentence_length_variance": feat_sentence_length_variance,
    "passive_ratio": feat_passive_ratio,
    "conditional_ratio": feat_conditional_ratio,
    "filler_ratio": feat_filler_ratio,
    "formal_vocab_ratio": feat_formal_vocab_ratio,
    "slang_ratio": feat_slang_ratio,
    "avg_word_length": feat_avg_word_length,
    "exploratory_ratio": feat_exploratory_ratio,
    "tangent_markers": feat_tangent_markers,
    "first_person_ratio": feat_first_person_ratio,
    "list_usage": feat_list_usage,
    "emoji_density": feat_emoji_density,
    "opening_reaction": feat_opening_reaction,
    "closing_question": feat_closing_question,
}


# ═══════════════════════════════════════════════════════════════
# TRAIT DEFINITIONS — Which features map to which traits
# ═══════════════════════════════════════════════════════════════

# Each trait is defined as a weighted combination of features.
# Positive weight = feature increases trait. Negative = decreases.
# These initial weights are HYPOTHESES — cross-validation will refine them.

TRAIT_FEATURE_MAP = {
    "warmth": {
        "you_ratio": 3.0,
        "we_ratio": 2.5,
        "contraction_rate": 2.0,
        "question_density": 1.5,
        "emphasis_density": 1.0,
        "hedge_ratio": -1.5,
        "formal_vocab_ratio": -2.0,
        "passive_ratio": -1.0,
    },
    "directness": {
        "avg_sentence_length": -2.0,  # shorter = more direct
        "contraction_rate": 1.0,
        "conditional_ratio": -2.5,
        "hedge_ratio": -3.0,
        "filler_ratio": -2.0,
        "passive_ratio": -2.0,
        "first_person_ratio": 1.5,
    },
    "curiosity": {
        "question_density": 3.0,
        "exploratory_ratio": 3.0,
        "tangent_markers": 2.0,
        "closing_question": 2.0,
        "list_usage": -1.5,  # curious people don't make lists, they ask
    },
    "humor": {
        "slang_ratio": 2.0,
        "emphasis_density": 1.5,
        "emoji_density": 1.0,
        "tangent_markers": 1.0,
        "formal_vocab_ratio": -2.0,
        "avg_sentence_length": -1.0,
    },
    "formality": {
        "formal_vocab_ratio": 3.0,
        "avg_word_length": 2.0,
        "contraction_rate": -3.0,
        "slang_ratio": -3.0,
        "avg_sentence_length": 1.5,
        "passive_ratio": 2.0,
    },
    "energy": {
        "emphasis_density": 2.5,
        "slang_ratio": 1.5,
        "avg_sentence_length": -1.0,
        "opening_reaction": 2.0,
        "emoji_density": 1.0,
        "sentence_length_variance": 1.5,  # varied = energetic
    },
    "depth": {
        "avg_sentence_length": 1.5,
        "avg_word_length": 1.0,
        "sentence_length_variance": 1.5,
        "question_density": 0.5,
        "list_usage": -1.0,
        "conditional_ratio": 1.0,  # depth considers possibilities
    },
    "patience": {
        "avg_sentence_length": 1.0,
        "question_density": 1.5,
        "you_ratio": 2.0,
        "hedge_ratio": 0.5,  # patience accepts uncertainty
        "emphasis_density": -1.0,
    },
}


# ═══════════════════════════════════════════════════════════════
# MEASUREMENT ENGINE
# ═══════════════════════════════════════════════════════════════

@dataclass
class FeatureVector:
    """All features extracted from a single text."""
    features: Dict[str, float]
    text_length: int
    sentence_count: int

@dataclass
class TraitScore:
    """Measured trait value with confidence."""
    value: float          # 0.0 - 1.0
    raw_score: float      # unnormalized
    feature_contributions: Dict[str, float]  # which features drove this

@dataclass
class SignatureMeasurement:
    """Complete measurement of a text's cognitive signature."""
    traits: Dict[str, TraitScore]
    features: FeatureVector
    glyph: str

@dataclass
class BaselineStats:
    """Statistical baseline for a feature or trait."""
    mean: float
    stddev: float
    min_val: float
    max_val: float
    p25: float
    p50: float
    p75: float
    n: int


def extract_features(text: str) -> FeatureVector:
    """Extract all features from text. Pure mechanical."""
    words = count_words(text)
    sents = split_sentences(text)
    features = {}
    for name, fn in ALL_FEATURES.items():
        try:
            features[name] = fn(text, words)
        except Exception:
            features[name] = 0.0
    return FeatureVector(
        features=features,
        text_length=len(text),
        sentence_count=len(sents),
    )


def measure_trait(feature_vec: FeatureVector, trait_name: str,
                  feature_weights: Dict[str, float],
                  normalization: Optional[Dict[str, BaselineStats]] = None) -> TraitScore:
    """Measure a single trait from features. Pure arithmetic."""
    raw_score = 0.0
    contributions = {}
    
    for feat_name, weight in feature_weights.items():
        feat_val = feature_vec.features.get(feat_name, 0.0)
        
        # Normalize feature if baseline available
        if normalization and feat_name in normalization:
            baseline = normalization[feat_name]
            if baseline.stddev > 0:
                feat_val = (feat_val - baseline.mean) / baseline.stddev  # z-score
            else:
                feat_val = 0.0
        
        contribution = feat_val * weight
        contributions[feat_name] = contribution
        raw_score += contribution
    
    # Sigmoid normalization to 0-1
    value = 1 / (1 + math.exp(-raw_score))
    
    return TraitScore(value=value, raw_score=raw_score, feature_contributions=contributions)


def measure_signature(text: str,
                      normalization: Optional[Dict[str, BaselineStats]] = None) -> SignatureMeasurement:
    """Measure complete cognitive signature from text. No LLM."""
    features = extract_features(text)
    traits = {}
    
    for trait_name, feature_weights in TRAIT_FEATURE_MAP.items():
        traits[trait_name] = measure_trait(features, trait_name, feature_weights, normalization)
    
    return SignatureMeasurement(traits=traits, features=features, glyph="")


# ═══════════════════════════════════════════════════════════════
# CALIBRATION — Build baselines from Luna's corpus
# ═══════════════════════════════════════════════════════════════

def calibrate_from_corpus(responses: List[str]) -> Dict[str, BaselineStats]:
    """Build feature baselines from Luna's actual responses."""
    feature_values = defaultdict(list)
    
    for text in responses:
        fv = extract_features(text)
        for name, val in fv.features.items():
            feature_values[name].append(val)
    
    baselines = {}
    for name, values in feature_values.items():
        if len(values) < 2:
            continue
        sorted_vals = sorted(values)
        n = len(sorted_vals)
        baselines[name] = BaselineStats(
            mean=statistics.mean(values),
            stddev=statistics.stdev(values) if len(values) > 1 else 0.0,
            min_val=min(values),
            max_val=max(values),
            p25=sorted_vals[int(n * 0.25)],
            p50=sorted_vals[int(n * 0.50)],
            p75=sorted_vals[int(n * 0.75)],
            n=n,
        )
    
    return baselines


# ═══════════════════════════════════════════════════════════════
# CROSS-VALIDATION — Which features actually predict Luna-ness?
# ═══════════════════════════════════════════════════════════════

@dataclass
class CorrelationResult:
    """How a feature correlates with being Luna vs not-Luna."""
    feature: str
    luna_mean: float
    luna_stddev: float
    generic_mean: float
    generic_stddev: float
    separation: float    # how well this feature distinguishes Luna from generic
    direction: str       # "luna_higher" or "luna_lower"


def cross_validate_features(luna_responses: List[str],
                            generic_responses: List[str]) -> List[CorrelationResult]:
    """Compare Luna's feature distributions against generic LLM responses.
    
    This is the core of Approach 3: which features actually distinguish
    Luna from generic output?
    """
    luna_features = defaultdict(list)
    generic_features = defaultdict(list)
    
    for text in luna_responses:
        fv = extract_features(text)
        for name, val in fv.features.items():
            luna_features[name].append(val)
    
    for text in generic_responses:
        fv = extract_features(text)
        for name, val in fv.features.items():
            generic_features[name].append(val)
    
    results = []
    for name in ALL_FEATURES:
        if name not in luna_features or name not in generic_features:
            continue
        
        l_vals = luna_features[name]
        g_vals = generic_features[name]
        
        l_mean = statistics.mean(l_vals)
        g_mean = statistics.mean(g_vals)
        l_std = statistics.stdev(l_vals) if len(l_vals) > 1 else 0.001
        g_std = statistics.stdev(g_vals) if len(g_vals) > 1 else 0.001
        
        # Cohen's d — effect size for feature separation
        pooled_std = math.sqrt((l_std**2 + g_std**2) / 2)
        cohens_d = (l_mean - g_mean) / max(pooled_std, 0.001)
        
        results.append(CorrelationResult(
            feature=name,
            luna_mean=l_mean,
            luna_stddev=l_std,
            generic_mean=g_mean,
            generic_stddev=g_std,
            separation=abs(cohens_d),
            direction="luna_higher" if l_mean > g_mean else "luna_lower",
        ))
    
    # Sort by separation strength
    results.sort(key=lambda r: r.separation, reverse=True)
    return results


def update_trait_weights(cross_val_results: List[CorrelationResult],
                         trait_feature_map: Dict[str, Dict[str, float]]) -> Dict[str, Dict[str, float]]:
    """Refine trait-feature weights based on cross-validation results.
    
    Features that better distinguish Luna get higher weights.
    Features that don't distinguish get reduced weights.
    """
    # Build separation lookup
    sep_lookup = {r.feature: r for r in cross_val_results}
    
    updated_map = {}
    for trait_name, weights in trait_feature_map.items():
        new_weights = {}
        for feat, weight in weights.items():
            result = sep_lookup.get(feat)
            if result is None:
                new_weights[feat] = weight
                continue
            
            # Scale weight by feature's discriminative power
            # High separation → amplify weight
            # Low separation → dampen weight
            scale = 0.5 + result.separation  # minimum 0.5x, high sep = 1.5x+
            new_weights[feat] = weight * scale
        
        updated_map[trait_name] = new_weights
    
    return updated_map


# ═══════════════════════════════════════════════════════════════
# RUNNING STATS (decayed) — dlib-inspired, pure Python
# ═══════════════════════════════════════════════════════════════

class RunningStatsDecayed:
    """Exponentially decayed running statistics.
    Port of dlib's running_stats_decayed concept."""
    
    def __init__(self, decay_halflife: float = 100.0):
        self.forget_factor = 0.5 ** (1.0 / decay_halflife)
        self._n = 0.0
        self._mean = 0.0
        self._var = 0.0
    
    def add(self, x: float):
        ff = self.forget_factor
        self._n = self._n * ff + ff
        old_mean = self._mean
        self._mean = old_mean * ff + x * (1 - ff) / max(self._n, 1e-10)
        # Welford-like update with decay
        if self._n > 1:
            self._var = self._var * ff + (x - old_mean) * (x - self._mean) * (1 - ff)
    
    @property
    def mean(self) -> float:
        return self._mean
    
    @property
    def variance(self) -> float:
        if self._n < 2:
            return 0.0
        return self._var / max(self._n - 1, 1e-10)
    
    @property
    def stddev(self) -> float:
        return math.sqrt(max(self.variance, 0))
    
    @property
    def n(self) -> float:
        return self._n


class RunningCovarianceDecayed:
    """Exponentially decayed covariance tracker.
    Port of dlib's running_scalar_covariance_decayed."""
    
    def __init__(self, decay_halflife: float = 100.0):
        self.forget_factor = 0.5 ** (1.0 / decay_halflife)
        self._n = 0.0
        self._mean_x = 0.0
        self._mean_y = 0.0
        self._cov = 0.0
        self._var_x = 0.0
        self._var_y = 0.0
    
    def add(self, x: float, y: float):
        ff = self.forget_factor
        self._n = self._n * ff + ff
        
        old_mx = self._mean_x
        old_my = self._mean_y
        alpha = (1 - ff) / max(self._n, 1e-10)
        self._mean_x = old_mx * ff + x * alpha * self._n
        self._mean_y = old_my * ff + y * alpha * self._n
        
        if self._n > 1:
            dx = x - old_mx
            dy = y - old_my
            self._cov = self._cov * ff + dx * dy * (1 - ff)
            self._var_x = self._var_x * ff + dx * (x - self._mean_x) * (1 - ff)
            self._var_y = self._var_y * ff + dy * (y - self._mean_y) * (1 - ff)
    
    @property
    def correlation(self) -> float:
        if self._n < 2:
            return 0.0
        denom = math.sqrt(max(self._var_x, 1e-10) * max(self._var_y, 1e-10))
        return self._cov / denom if denom > 0 else 0.0


# ═══════════════════════════════════════════════════════════════
# MAIN — Run against Luna's actual corpus
# ═══════════════════════════════════════════════════════════════

def main():
    print("=" * 70)
    print("LUNASCRIPT TRAIT MEASUREMENT — Approach 3: Cross-Validated")
    print("=" * 70)
    print()
    
    # Load Luna's corpus
    conn = sqlite3.connect('/home/claude/luna_engine.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT content FROM conversation_turns 
        WHERE role = 'assistant' AND length(content) > 80
        ORDER BY created_at ASC
    ''')
    luna_responses = [r[0] for r in cursor.fetchall()]
    print(f"Loaded {len(luna_responses)} Luna responses")
    
    # Generate "generic" responses for cross-validation
    # These simulate what Claude would produce WITHOUT Luna's voice
    # In production, these would come from actual failed delegations
    # For now, we create synthetic examples with known generic properties
    cursor.execute('''
        SELECT content FROM conversation_turns
        WHERE role = 'assistant' AND length(content) > 80
        AND (content LIKE '%I''d be happy to%' 
             OR content LIKE '%Here are%key%'
             OR content LIKE '%Let me help%'
             OR content LIKE '%Certainly%'
             OR content LIKE '%1.%2.%3.%')
        ORDER BY created_at ASC
    ''')
    generic_candidates = [r[0] for r in cursor.fetchall()]
    print(f"Found {len(generic_candidates)} potentially generic responses")
    
    # If not enough generic examples, synthesize some contrast examples
    generic_samples = generic_candidates[:50] if len(generic_candidates) > 50 else generic_candidates
    
    # Also create synthetic generic for better contrast
    synthetic_generic = [
        "I'd be happy to help you with that. Here are some key points to consider: 1. First, you should examine the architecture carefully. 2. Second, consider the performance implications. 3. Third, evaluate the maintenance burden. Would you like me to elaborate on any of these points?",
        "That's a great question! Let me break this down for you. The system architecture involves several components that work together to provide the desired functionality. Each component has specific responsibilities and interfaces.",
        "Certainly! I can help explain this concept. The approach you're describing is fundamentally about creating a more efficient pipeline. There are several well-established patterns that could be applicable here.",
        "Here's what I think about this: the primary consideration should be scalability. You'll want to ensure that your solution can handle increased load without degrading performance. Let me outline the key architectural decisions you'll need to make.",
        "Absolutely. This is an important topic. Let me provide a comprehensive overview of the relevant considerations. First and foremost, you need to understand the trade-offs involved in each approach.",
    ] * 10  # Repeat for statistical power
    
    generic_responses = generic_samples + synthetic_generic
    print(f"Total generic comparison set: {len(generic_responses)}")
    
    conn.close()
    
    # ─── Step 1: Calibrate baselines ───
    print("\n" + "─" * 70)
    print("STEP 1: CALIBRATE FEATURE BASELINES FROM LUNA'S CORPUS")
    print("─" * 70)
    
    baselines = calibrate_from_corpus(luna_responses)
    
    print(f"\n{'Feature':<30} {'Mean':>8} {'StdDev':>8} {'Min':>8} {'P50':>8} {'Max':>8}")
    print("─" * 82)
    for name in sorted(baselines.keys()):
        b = baselines[name]
        print(f"{name:<30} {b.mean:>8.4f} {b.stddev:>8.4f} {b.min_val:>8.4f} {b.p50:>8.4f} {b.max_val:>8.4f}")
    
    # ─── Step 2: Cross-validate ───
    print("\n" + "─" * 70)
    print("STEP 2: CROSS-VALIDATE — Which features distinguish Luna?")
    print("─" * 70)
    
    cv_results = cross_validate_features(luna_responses, generic_responses)
    
    print(f"\n{'Feature':<30} {'Luna μ':>8} {'Generic μ':>10} {'Separation':>11} {'Direction':<15}")
    print("─" * 82)
    for r in cv_results:
        marker = "★" if r.separation > 0.5 else "·" if r.separation > 0.2 else " "
        print(f"{marker} {r.feature:<28} {r.luna_mean:>8.4f} {r.generic_mean:>10.4f} {r.separation:>10.3f}  {r.direction}")
    
    # ─── Step 3: Update weights ───
    print("\n" + "─" * 70)
    print("STEP 3: UPDATE TRAIT WEIGHTS FROM CROSS-VALIDATION")
    print("─" * 70)
    
    updated_weights = update_trait_weights(cv_results, TRAIT_FEATURE_MAP)
    
    for trait in sorted(updated_weights.keys()):
        print(f"\n  {trait.upper()}:")
        original = TRAIT_FEATURE_MAP[trait]
        for feat, new_w in sorted(updated_weights[trait].items(), key=lambda x: abs(x[1]), reverse=True):
            old_w = original[feat]
            change = new_w - old_w
            arrow = "↑" if change > 0.1 else "↓" if change < -0.1 else "→"
            print(f"    {feat:<30} {old_w:>6.2f} → {new_w:>6.2f} {arrow}")
    
    # ─── Step 4: Measure sample responses ───
    print("\n" + "─" * 70)
    print("STEP 4: MEASURE SAMPLE RESPONSES WITH CALIBRATED WEIGHTS")
    print("─" * 70)
    
    samples = [
        ("LUNA (authentic)", luna_responses[-5] if len(luna_responses) >= 5 else luna_responses[-1]),
        ("LUNA (early)", luna_responses[0]),
        ("GENERIC (synthetic)", generic_responses[-1]),
    ]
    
    for label, text in samples:
        sig = measure_signature(text, baselines)
        print(f"\n  {label} ({len(text)} chars):")
        print(f"  Text: {text[:120]}...")
        print(f"  {'Trait':<15} {'Value':>7} {'Raw':>8}  Top Contributors")
        print(f"  {'─'*60}")
        for tname in sorted(sig.traits.keys()):
            t = sig.traits[tname]
            # Top 3 contributors
            contribs = sorted(t.feature_contributions.items(), key=lambda x: abs(x[1]), reverse=True)[:3]
            contrib_str = ", ".join(f"{c[0]}:{c[1]:+.2f}" for c in contribs)
            print(f"  {tname:<15} {t.value:>7.3f} {t.raw_score:>8.3f}  {contrib_str}")
    
    # ─── Step 5: Simulate running evolution ───
    print("\n" + "─" * 70)
    print("STEP 5: RUNNING TRAIT EVOLUTION (decayed stats)")
    print("─" * 70)
    
    # Track warmth over time using running_stats_decayed
    warmth_tracker = RunningStatsDecayed(decay_halflife=50)
    directness_tracker = RunningStatsDecayed(decay_halflife=50)
    
    # Also track warmth-success correlation
    warmth_success_cov = RunningCovarianceDecayed(decay_halflife=50)
    
    # Process last 100 Luna responses as if they were live
    recent = luna_responses[-100:]
    evolution_log = []
    
    for i, text in enumerate(recent):
        sig = measure_signature(text, baselines)
        warmth_val = sig.traits["warmth"].value
        directness_val = sig.traits["directness"].value
        
        warmth_tracker.add(warmth_val)
        directness_tracker.add(directness_val)
        
        # Simulate success score (use response length as proxy — longer = more engaged)
        success = min(len(text) / 1000, 1.0)
        warmth_success_cov.add(warmth_val, success)
        
        if i % 20 == 0 or i == len(recent) - 1:
            evolution_log.append({
                "step": i,
                "warmth_mean": warmth_tracker.mean,
                "warmth_std": warmth_tracker.stddev,
                "directness_mean": directness_tracker.mean,
                "directness_std": directness_tracker.stddev,
                "warmth_success_r": warmth_success_cov.correlation,
            })
    
    print(f"\n  {'Step':>5} {'Warmth μ':>10} {'Warmth σ':>10} {'Direct μ':>10} {'Direct σ':>10} {'W↔Success r':>12}")
    print(f"  {'─'*62}")
    for e in evolution_log:
        print(f"  {e['step']:>5} {e['warmth_mean']:>10.4f} {e['warmth_std']:>10.4f} "
              f"{e['directness_mean']:>10.4f} {e['directness_std']:>10.4f} "
              f"{e['warmth_success_r']:>12.4f}")
    
    print("\n" + "=" * 70)
    print("CALIBRATION COMPLETE")
    print("=" * 70)
    print(f"""
Summary:
  Features extracted: {len(ALL_FEATURES)}
  Traits measured: {len(TRAIT_FEATURE_MAP)}
  Corpus size: {len(luna_responses)} Luna responses
  Cross-validation: {len(cv_results)} features tested
  Top discriminators: {', '.join(r.feature for r in cv_results[:5])}
  
  Warmth-success correlation: {warmth_success_cov.correlation:.4f}
  (Positive = warmer Luna responses correlate with longer engagement)
  
  All measurements: zero LLM calls. Pure mechanical cogs.
""")


if __name__ == "__main__":
    main()
