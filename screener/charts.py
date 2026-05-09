"""
screener/charts.py
Phronesis Screener — visualisations Plotly (100% gratuit)
"""

import plotly.graph_objects as go
import plotly.express as px
import pandas as pd

# Palette Phronesis
COLORS = {
    "green":      "#10B981",
    "red":        "#EF4444",
    "orange":     "#F97316",
    "blue":       "#3B82F6",
    "gray":       "#6B7280",
    "bg":         "#111827",
    "bg_paper":   "#1F2937",
    "grid":       "#1F2937",
    "text":       "#9CA3AF",
    "text_light": "#F9FAFB",
}

LAYOUT_BASE = dict(
    paper_bgcolor=COLORS["bg"],
    plot_bgcolor=COLORS["bg"],
    font=dict(color=COLORS["text"], size=12),
    margin=dict(l=10, r=10, t=30, b=10),
    xaxis=dict(gridcolor=COLORS["grid"], showgrid=True, zeroline=False),
    yaxis=dict(gridcolor=COLORS["grid"], showgrid=True, zeroline=False),
    legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(size=11)),
    hovermode="x unified",
)


def price_chart(dates: list, closes: list, ticker: str,
                fair_value: float = None, height: int = 280) -> go.Figure:
    """
    Graphique prix + ligne fair value si disponible.
    """
    if not dates or not closes:
        return go.Figure()

    color = COLORS["green"] if closes[-1] >= closes[0] else COLORS["red"]

    fig = go.Figure()

    # Zone remplie sous la courbe
    fig.add_trace(go.Scatter(
        x=dates, y=closes,
        mode="lines",
        name="Prix",
        line=dict(color=color, width=2),
        fill="tozeroy",
        fillcolor=f"rgba({_hex_to_rgb(color)}, 0.08)",
        hovertemplate="%{y:.2f}<extra></extra>",
    ))

    # Ligne fair value
    if fair_value and fair_value > 0:
        fig.add_hline(
            y=fair_value,
            line_dash="dash",
            line_color=COLORS["blue"],
            line_width=1.5,
            annotation_text=f"Fair Value: {fair_value:.2f}",
            annotation_font_color=COLORS["blue"],
            annotation_font_size=11,
        )

    fig.update_layout(
        **LAYOUT_BASE,
        height=height,
        title=dict(text=f"<b>{ticker}</b> — Prix 60 jours", font=dict(size=13), x=0),
        showlegend=False,
    )
    return fig


def score_radar(score_value: float, score_quality: float,
                score_momentum: float, score_risk: float,
                height: int = 280) -> go.Figure:
    """
    Radar chart des 4 composantes du Phronesis Score.
    """
    categories = ["Valeur", "Qualité", "Momentum", "Risque", "Valeur"]
    values     = [score_value, score_quality, score_momentum, score_risk, score_value]

    fig = go.Figure()
    fig.add_trace(go.Scatterpolar(
        r=values,
        theta=categories,
        fill="toself",
        fillcolor=f"rgba({_hex_to_rgb(COLORS['green'])}, 0.15)",
        line=dict(color=COLORS["green"], width=2),
        name="Score",
    ))
    fig.update_layout(
        **LAYOUT_BASE,
        height=height,
        polar=dict(
            bgcolor=COLORS["bg"],
            radialaxis=dict(
                visible=True, range=[0, 25],
                gridcolor=COLORS["grid"],
                color=COLORS["text"],
                tickfont=dict(size=10),
            ),
            angularaxis=dict(
                gridcolor=COLORS["grid"],
                color=COLORS["text_light"],
                tickfont=dict(size=11),
            ),
        ),
        showlegend=False,
        title=dict(text="Décomposition Phronesis Score", font=dict(size=13), x=0),
    )
    return fig


def score_distribution(df: pd.DataFrame, height: int = 220) -> go.Figure:
    """
    Histogramme de distribution des scores du screener.
    """
    if df.empty or "score" not in df.columns:
        return go.Figure()

    fig = px.histogram(
        df, x="score", nbins=20,
        color_discrete_sequence=[COLORS["green"]],
    )
    fig.update_layout(
        **LAYOUT_BASE,
        height=height,
        title=dict(text="Distribution des Phronesis Scores", font=dict(size=13), x=0),
        xaxis_title="Score",
        yaxis_title="Nb actifs",
        bargap=0.05,
    )
    # Ajouter zones colorées
    fig.add_vrect(x0=0,  x1=30, fillcolor=COLORS["red"],    opacity=0.06, layer="below", line_width=0)
    fig.add_vrect(x0=30, x1=45, fillcolor=COLORS["orange"],  opacity=0.06, layer="below", line_width=0)
    fig.add_vrect(x0=60, x1=100, fillcolor=COLORS["green"],  opacity=0.06, layer="below", line_width=0)
    return fig


def top_opportunities_bar(df: pd.DataFrame, n: int = 8,
                           height: int = 260) -> go.Figure:
    """
    Bar chart horizontal des meilleures opportunités.
    """
    if df.empty:
        return go.Figure()

    top = df[df["upside_pct"] > 0].nlargest(n, "upside_pct")[
        ["ticker", "upside_pct", "signal"]
    ]
    if top.empty:
        return go.Figure()

    colors = [COLORS["green"] if u >= 20 else COLORS["blue"]
              for u in top["upside_pct"]]

    fig = go.Figure(go.Bar(
        x=top["upside_pct"],
        y=top["ticker"],
        orientation="h",
        marker_color=colors,
        text=[f"+{v:.0f}%" for v in top["upside_pct"]],
        textposition="outside",
        textfont=dict(color=COLORS["text_light"], size=11),
        hovertemplate="%{y}: +%{x:.1f}%<extra></extra>",
    ))
        # Copie LAYOUT_BASE et fusionne avec les paramètres spécifiques
    layout = LAYOUT_BASE.copy()
    layout.update(
        height=height,
        title=dict(text="Top Opportunités — Upside estimé", font=dict(size=13), x=0),
        xaxis_title="Upside %",
        yaxis=dict(
            gridcolor=COLORS["grid"],
            tickfont=dict(size=12, color=COLORS["text_light"]),
        ),
    )
    fig.update_layout(**layout)
    return fig


# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------

def _hex_to_rgb(hex_color: str) -> str:
    """Convertit #RRGGBB en 'R, G, B' pour rgba()."""
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"{r}, {g}, {b}"