"""
Personality visualization generation for Persona Forge.

Generates HTML visualizations for:
- Spider/radar graphs comparing dataset personality vs target
- Box plots showing personality variance across dataset
- Heatmaps showing personality by source type
"""

from pathlib import Path
from typing import Optional
from collections import defaultdict
import statistics
import math

try:
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False


# Dimension display names and colors
DIMENSION_CONFIG = {
    "warmth": {"name": "Warmth", "color": "#FF6B6B"},
    "technical": {"name": "Technical", "color": "#4ECDC4"},
    "humor": {"name": "Humor", "color": "#FFE66D"},
    "directness": {"name": "Directness", "color": "#95E1D3"},
    "creativity": {"name": "Creativity", "color": "#DDA0DD"},
    "reflection": {"name": "Reflection", "color": "#98D8C8"},
    "relationship": {"name": "Relationship", "color": "#F7DC6F"},
    "assertiveness": {"name": "Assertiveness", "color": "#BB8FCE"},
}

DIMENSIONS = list(DIMENSION_CONFIG.keys())


def generate_personality_visualizations(
    examples: list,
    assay,
    target_llm: str = "qwen2.5-7b-instruct",
    output_dir: Optional[Path] = None,
) -> dict[str, Path]:
    """
    Generate all personality visualizations for a dataset.

    Args:
        examples: List of TrainingExample objects with personality_scores
        assay: DatasetAssay object with personality_profile
        target_llm: Target LLM name for labeling
        output_dir: Output directory (defaults to current directory)

    Returns:
        Dictionary mapping visualization name to output path
    """
    if not PLOTLY_AVAILABLE:
        print("Warning: plotly not installed. Skipping visualizations.")
        print("Install with: pip install plotly")
        return {}

    if output_dir is None:
        output_dir = Path.cwd()
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    outputs = {}

    # 1. Spider graph (dataset vs target)
    if assay.personality_profile:
        fig = create_spider_graph(
            dataset_profile=assay.personality_profile,
            target_profile=assay.personality_profile,  # Use target from assayer
            target_llm=target_llm,
        )
        spider_path = output_dir / "persona_forge_spider.html"
        fig.write_html(str(spider_path))
        outputs["spider"] = spider_path
        print(f"  Created {spider_path}")

    # 2. Box plot (variance analysis)
    scored_examples = [e for e in examples if e.personality_scores]
    if scored_examples:
        fig = create_box_plot(scored_examples)
        box_path = output_dir / "persona_forge_variance.html"
        fig.write_html(str(box_path))
        outputs["variance"] = box_path
        print(f"  Created {box_path}")

    # 3. Source heatmap
    if scored_examples:
        fig = create_source_heatmap(scored_examples)
        if fig:
            heatmap_path = output_dir / "persona_forge_sources.html"
            fig.write_html(str(heatmap_path))
            outputs["sources"] = heatmap_path
            print(f"  Created {heatmap_path}")

    return outputs


def create_spider_graph(
    dataset_profile: dict[str, float],
    target_profile: dict[str, float],
    target_llm: str = "Target",
) -> "go.Figure":
    """
    Create a spider/radar graph comparing dataset vs target personality.

    Args:
        dataset_profile: Dataset's average personality scores
        target_profile: Target personality profile
        target_llm: Target LLM name for labeling

    Returns:
        Plotly Figure object
    """
    categories = [DIMENSION_CONFIG[d]["name"] for d in DIMENSIONS]
    categories.append(categories[0])  # Close the polygon

    dataset_values = [dataset_profile.get(d, 0) for d in DIMENSIONS]
    dataset_values.append(dataset_values[0])

    target_values = [target_profile.get(d, 0) for d in DIMENSIONS]
    target_values.append(target_values[0])

    fig = go.Figure()

    # Target profile (filled area)
    fig.add_trace(go.Scatterpolar(
        r=target_values,
        theta=categories,
        fill='toself',
        fillcolor='rgba(135, 206, 250, 0.3)',
        line=dict(color='#87CEEB', width=2),
        name=f'Target ({target_llm})',
    ))

    # Dataset profile (line)
    fig.add_trace(go.Scatterpolar(
        r=dataset_values,
        theta=categories,
        fill='toself',
        fillcolor='rgba(255, 107, 107, 0.3)',
        line=dict(color='#FF6B6B', width=3),
        name='Dataset',
    ))

    fig.update_layout(
        polar=dict(
            radialaxis=dict(
                visible=True,
                range=[0, 1],
                tickvals=[0.25, 0.50, 0.75, 1.0],
            ),
        ),
        showlegend=True,
        title=dict(
            text=f"Personality Profile: Dataset vs {target_llm}",
            x=0.5,
            font=dict(size=20),
        ),
        paper_bgcolor='#1a1a2e',
        plot_bgcolor='#1a1a2e',
        font=dict(color='white'),
        legend=dict(
            yanchor="top",
            y=0.99,
            xanchor="left",
            x=0.01,
        ),
    )

    return fig


def create_box_plot(examples: list) -> "go.Figure":
    """
    Create a box plot showing personality variance across dataset.

    Args:
        examples: List of TrainingExample objects with personality_scores

    Returns:
        Plotly Figure object
    """
    fig = go.Figure()

    for dim in DIMENSIONS:
        scores = [
            e.personality_scores[dim]
            for e in examples
            if e.personality_scores and dim in e.personality_scores
        ]

        if scores:
            config = DIMENSION_CONFIG[dim]
            fig.add_trace(go.Box(
                y=scores,
                name=config["name"],
                marker_color=config["color"],
                boxmean='sd',  # Show mean and standard deviation
            ))

    fig.update_layout(
        title=dict(
            text="Personality Variance Across Dataset",
            x=0.5,
            font=dict(size=20),
        ),
        yaxis_title="Score",
        yaxis=dict(range=[0, 1]),
        paper_bgcolor='#1a1a2e',
        plot_bgcolor='#16213e',
        font=dict(color='white'),
        showlegend=False,
    )

    return fig


def create_source_heatmap(examples: list) -> Optional["go.Figure"]:
    """
    Create a heatmap showing personality by source type.

    Args:
        examples: List of TrainingExample objects with personality_scores

    Returns:
        Plotly Figure object or None if not enough data
    """
    # Group by source type
    source_profiles: dict[str, dict[str, list]] = defaultdict(lambda: defaultdict(list))

    for e in examples:
        if e.personality_scores:
            source = e.source_type.value if hasattr(e.source_type, 'value') else str(e.source_type)
            for dim, score in e.personality_scores.items():
                source_profiles[source][dim].append(score)

    if len(source_profiles) < 2:
        return None  # Need at least 2 sources for comparison

    # Compute averages
    sources = sorted(source_profiles.keys())
    z_data = []

    for dim in DIMENSIONS:
        row = []
        for source in sources:
            scores = source_profiles[source].get(dim, [])
            avg = statistics.mean(scores) if scores else 0
            row.append(avg)
        z_data.append(row)

    fig = go.Figure(data=go.Heatmap(
        z=z_data,
        x=sources,
        y=[DIMENSION_CONFIG[d]["name"] for d in DIMENSIONS],
        colorscale='RdYlGn',
        zmin=0,
        zmax=1,
        text=[[f"{v:.2f}" for v in row] for row in z_data],
        texttemplate="%{text}",
        textfont={"size": 12},
        hovertemplate="Source: %{x}<br>Dimension: %{y}<br>Score: %{z:.2f}<extra></extra>",
    ))

    fig.update_layout(
        title=dict(
            text="Personality by Source Type",
            x=0.5,
            font=dict(size=20),
        ),
        xaxis_title="Source Type",
        yaxis_title="Personality Dimension",
        paper_bgcolor='#1a1a2e',
        plot_bgcolor='#16213e',
        font=dict(color='white'),
    )

    return fig


def create_alignment_gauge(alignment: float, target_llm: str = "Target") -> "go.Figure":
    """
    Create a gauge chart showing personality alignment.

    Args:
        alignment: Alignment score (0-1)
        target_llm: Target LLM name

    Returns:
        Plotly Figure object
    """
    fig = go.Figure(go.Indicator(
        mode="gauge+number+delta",
        value=alignment * 100,
        title={'text': f"Personality Alignment with {target_llm}"},
        delta={'reference': 85, 'increasing': {'color': "green"}},
        gauge={
            'axis': {'range': [0, 100], 'tickwidth': 1},
            'bar': {'color': "#FF6B6B"},
            'bgcolor': "white",
            'borderwidth': 2,
            'bordercolor': "gray",
            'steps': [
                {'range': [0, 50], 'color': '#FF6B6B'},
                {'range': [50, 70], 'color': '#FFE66D'},
                {'range': [70, 85], 'color': '#98D8C8'},
                {'range': [85, 100], 'color': '#4ECDC4'},
            ],
            'threshold': {
                'line': {'color': "white", 'width': 4},
                'thickness': 0.75,
                'value': 85
            }
        }
    ))

    fig.update_layout(
        paper_bgcolor='#1a1a2e',
        font=dict(color='white', size=16),
    )

    return fig
