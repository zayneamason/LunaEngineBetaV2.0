"""
iTerm2 inline image display for Persona Forge.

Uses iTerm2's imgcat protocol to display graphical visualizations
directly in the terminal.
"""

import base64
import io
import sys
import os
from pathlib import Path
from typing import Optional

try:
    import plotly.graph_objects as go
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False


def is_iterm2() -> bool:
    """Check if running in iTerm2."""
    term_program = os.environ.get("TERM_PROGRAM", "")
    return term_program == "iTerm.app"


def imgcat(data: bytes, width: str = "auto", height: str = "auto", name: str = "") -> None:
    """
    Display image data inline using iTerm2's imgcat protocol.

    Args:
        data: Image bytes (PNG, JPEG, etc.)
        width: Width specification (auto, N, Npx, N%)
        height: Height specification (auto, N, Npx, N%)
        name: Optional filename for display
    """
    if not is_iterm2():
        print("[Warning] Not running in iTerm2 - cannot display inline images")
        return

    # Encode image as base64
    b64_data = base64.b64encode(data).decode("ascii")

    # Build iTerm2 escape sequence
    # Format: ESC ] 1337 ; File = [args] : base64data BEL
    args = []
    args.append(f"size={len(data)}")
    args.append("inline=1")

    if width != "auto":
        args.append(f"width={width}")
    if height != "auto":
        args.append(f"height={height}")
    if name:
        args.append(f"name={base64.b64encode(name.encode()).decode()}")

    args_str = ";".join(args)

    # Write the escape sequence
    sys.stdout.write(f"\033]1337;File={args_str}:{b64_data}\007")
    sys.stdout.write("\n")
    sys.stdout.flush()


def display_spider_chart(
    profile: dict[str, float],
    target: Optional[dict[str, float]] = None,
    title: str = "Personality Profile",
    width: int = 600,
    height: int = 500,
) -> bool:
    """
    Display a spider/radar chart inline in iTerm2.

    Args:
        profile: Personality scores dict (8 dimensions, 0-1 values)
        target: Optional target profile for comparison
        title: Chart title
        width: Image width in pixels
        height: Image height in pixels

    Returns:
        True if displayed successfully, False otherwise
    """
    if not PLOTLY_AVAILABLE:
        print("[Error] Plotly not installed")
        return False

    if not is_iterm2():
        print("[Info] Not in iTerm2 - use CLI --personality-viz for HTML output")
        return False

    # Dimension config
    dimensions = ["warmth", "technical", "humor", "directness",
                  "creativity", "reflection", "relationship", "assertiveness"]

    display_names = {
        "warmth": "Warmth",
        "technical": "Technical",
        "humor": "Humor",
        "directness": "Directness",
        "creativity": "Creativity",
        "reflection": "Reflection",
        "relationship": "Relationship",
        "assertiveness": "Assertiveness",
    }

    categories = [display_names[d] for d in dimensions]
    categories.append(categories[0])  # Close polygon

    # Profile values
    values = [profile.get(d, 0) for d in dimensions]
    values.append(values[0])

    fig = go.Figure()

    # Add target if provided
    if target:
        target_values = [target.get(d, 0) for d in dimensions]
        target_values.append(target_values[0])

        fig.add_trace(go.Scatterpolar(
            r=target_values,
            theta=categories,
            fill='toself',
            fillcolor='rgba(135, 206, 250, 0.3)',
            line=dict(color='#87CEEB', width=2),
            name='Target',
        ))

    # Add profile
    fig.add_trace(go.Scatterpolar(
        r=values,
        theta=categories,
        fill='toself',
        fillcolor='rgba(255, 107, 107, 0.4)',
        line=dict(color='#FF6B6B', width=3),
        name='Dataset',
    ))

    fig.update_layout(
        polar=dict(
            radialaxis=dict(
                visible=True,
                range=[0, 1],
                tickvals=[0.25, 0.50, 0.75, 1.0],
                tickfont=dict(size=10),
            ),
            bgcolor='#1a1a2e',
        ),
        showlegend=True,
        title=dict(
            text=title,
            x=0.5,
            font=dict(size=16, color='white'),
        ),
        paper_bgcolor='#1a1a2e',
        plot_bgcolor='#1a1a2e',
        font=dict(color='white'),
        legend=dict(
            yanchor="top",
            y=0.99,
            xanchor="left",
            x=0.01,
            font=dict(size=10),
        ),
        margin=dict(l=60, r=60, t=60, b=60),
    )

    # Export to PNG bytes
    try:
        img_bytes = fig.to_image(format="png", width=width, height=height)
        imgcat(img_bytes, width="80%")
        return True
    except Exception as e:
        print(f"[Error] Failed to generate image: {e}")
        print("[Hint] Make sure kaleido is installed: pip install kaleido")
        return False


def display_alignment_gauge(
    alignment: float,
    target_llm: str = "Target",
    width: int = 400,
    height: int = 300,
) -> bool:
    """
    Display an alignment gauge inline in iTerm2.

    Args:
        alignment: Alignment score (0-1)
        target_llm: Target LLM name
        width: Image width in pixels
        height: Image height in pixels

    Returns:
        True if displayed successfully, False otherwise
    """
    if not PLOTLY_AVAILABLE:
        print("[Error] Plotly not installed")
        return False

    if not is_iterm2():
        return False

    pct = alignment * 100

    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=pct,
        title={'text': f"Alignment: {target_llm}", 'font': {'size': 14, 'color': 'white'}},
        number={'font': {'size': 28, 'color': 'white'}, 'suffix': '%'},
        gauge={
            'axis': {'range': [0, 100], 'tickwidth': 1, 'tickcolor': 'white'},
            'bar': {'color': "#FF6B6B" if pct < 70 else "#FFE66D" if pct < 85 else "#4ECDC4"},
            'bgcolor': "#16213e",
            'borderwidth': 2,
            'bordercolor': "#333",
            'steps': [
                {'range': [0, 70], 'color': '#2d1f3d'},
                {'range': [70, 85], 'color': '#3d2f1d'},
                {'range': [85, 100], 'color': '#1d3d2f'},
            ],
            'threshold': {
                'line': {'color': "white", 'width': 3},
                'thickness': 0.8,
                'value': 85
            }
        }
    ))

    fig.update_layout(
        paper_bgcolor='#1a1a2e',
        font=dict(color='white'),
        margin=dict(l=30, r=30, t=50, b=30),
    )

    try:
        img_bytes = fig.to_image(format="png", width=width, height=height)
        imgcat(img_bytes, width="50%")
        return True
    except Exception as e:
        print(f"[Error] Failed to generate gauge: {e}")
        return False


def display_dimension_bars(
    profile: dict[str, float],
    target: Optional[dict[str, float]] = None,
    width: int = 600,
    height: int = 400,
) -> bool:
    """
    Display dimension comparison bar chart inline in iTerm2.

    Args:
        profile: Personality scores dict
        target: Optional target profile
        width: Image width
        height: Image height

    Returns:
        True if successful
    """
    if not PLOTLY_AVAILABLE or not is_iterm2():
        return False

    dimensions = ["warmth", "technical", "humor", "directness",
                  "creativity", "reflection", "relationship", "assertiveness"]

    display_names = {
        "warmth": "Warmth ♥",
        "technical": "Technical ⚙",
        "humor": "Humor ☺",
        "directness": "Direct →",
        "creativity": "Creative ✦",
        "reflection": "Reflect ◐",
        "relationship": "Relation ♦",
        "assertiveness": "Assert ▲",
    }

    labels = [display_names[d] for d in dimensions]
    values = [profile.get(d, 0) for d in dimensions]

    fig = go.Figure()

    # Add target bars if provided
    if target:
        target_values = [target.get(d, 0) for d in dimensions]
        fig.add_trace(go.Bar(
            y=labels,
            x=target_values,
            orientation='h',
            name='Target',
            marker_color='rgba(135, 206, 250, 0.5)',
        ))

    # Add profile bars
    fig.add_trace(go.Bar(
        y=labels,
        x=values,
        orientation='h',
        name='Dataset',
        marker_color='#FF6B6B',
    ))

    fig.update_layout(
        title=dict(text="Personality Dimensions", x=0.5, font=dict(color='white')),
        xaxis=dict(range=[0, 1], title="Score", tickvals=[0, 0.25, 0.5, 0.75, 1.0]),
        yaxis=dict(autorange="reversed"),
        barmode='overlay',
        paper_bgcolor='#1a1a2e',
        plot_bgcolor='#16213e',
        font=dict(color='white'),
        legend=dict(orientation='h', y=1.1),
        margin=dict(l=100, r=30, t=80, b=50),
    )

    try:
        img_bytes = fig.to_image(format="png", width=width, height=height)
        imgcat(img_bytes, width="80%")
        return True
    except Exception as e:
        print(f"[Error] {e}")
        return False


# Quick test function
def test_display():
    """Test iTerm2 display with sample data."""
    print("Testing iTerm2 inline image display...")
    print(f"Running in iTerm2: {is_iterm2()}")

    sample_profile = {
        "warmth": 0.82,
        "technical": 0.65,
        "humor": 0.58,
        "directness": 0.75,
        "creativity": 0.68,
        "reflection": 0.72,
        "relationship": 0.88,
        "assertiveness": 0.70,
    }

    sample_target = {
        "warmth": 0.85,
        "technical": 0.70,
        "humor": 0.65,
        "directness": 0.80,
        "creativity": 0.70,
        "reflection": 0.75,
        "relationship": 0.90,
        "assertiveness": 0.75,
    }

    print("\n--- Spider Chart ---")
    display_spider_chart(sample_profile, sample_target, "Luna Personality Profile")

    print("\n--- Alignment Gauge ---")
    display_alignment_gauge(0.87, "Qwen 2.5-3B")

    print("\n--- Dimension Bars ---")
    display_dimension_bars(sample_profile, sample_target)


if __name__ == "__main__":
    test_display()
