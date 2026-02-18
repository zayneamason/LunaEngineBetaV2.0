"""
Math Utilities
==============
"""


def clamp(value: float, min_val: float, max_val: float) -> float:
    """Clamp value between min and max"""
    return max(min_val, min(max_val, value))


def lerp(a: float, b: float, t: float) -> float:
    """Linear interpolation between a and b"""
    return a + (b - a) * t


def map_range(value: float, in_min: float, in_max: float, out_min: float, out_max: float) -> float:
    """Map value from input range to output range"""
    return (value - in_min) * (out_max - out_min) / (in_max - in_min) + out_min


def ease_in_out(t: float) -> float:
    """Smooth ease in-out curve (0 to 1)"""
    return t * t * (3 - 2 * t)


def distance_2d(x1: float, y1: float, x2: float, y2: float) -> float:
    """2D Euclidean distance"""
    return ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5
