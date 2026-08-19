from __future__ import annotations

import html
import math
from statistics import pstdev


SVG_WIDTH = 960
SVG_HEIGHT = 420
MARGIN_TOP = 50
MARGIN_RIGHT = 28
MARGIN_BOTTOM = 100
MARGIN_LEFT = 110
TICK_LABEL_SIZE = 25
AXIS_LABEL_SIZE = 25
PREFERRED_BAR_COLOR = "#bfdbfe"
PREFERRED_LINE_COLOR = "#1d4ed8"
GRID_COLOR = "#e2e8f0"
TEXT_COLOR = "#334155"
MUTED_TEXT_COLOR = "#64748b"


def render_score_density_svg(
    *,
    title: str,
    x_label: str,
    values: list[float],
    color: str = PREFERRED_LINE_COLOR,
) -> str:
    cleaned_values = [value for value in values if math.isfinite(value)]
    if not cleaned_values:
        raise ValueError("At least one numeric value is required")

    data_min = min(cleaned_values)
    data_max = max(cleaned_values)
    if data_min == data_max:
        padding = abs(data_min) * 0.1 or 1.0
        data_min -= padding
        data_max += padding
    else:
        padding = (data_max - data_min) * 0.08
        data_min -= padding
        data_max += padding

    plot_width = SVG_WIDTH - MARGIN_LEFT - MARGIN_RIGHT
    plot_height = SVG_HEIGHT - MARGIN_TOP - MARGIN_BOTTOM
    bins = min(20, max(5, int(round(math.sqrt(len(cleaned_values)))) or 5))
    bin_width = (data_max - data_min) / bins
    counts = [0 for _ in range(bins)]
    for value in cleaned_values:
        index = int((value - data_min) / bin_width) if bin_width else 0
        if index < 0:
            index = 0
        elif index >= bins:
            index = bins - 1
        counts[index] += 1

    kde_curve = _kde_curve(cleaned_values, data_min, data_max, bin_width)
    max_y = max(max(counts), max(kde_curve), 1.0)

    x_axis_y = SVG_HEIGHT - MARGIN_BOTTOM
    y_axis_x = MARGIN_LEFT
    title_x = MARGIN_LEFT + plot_width / 2
    title_y = 24
    x_label_y = SVG_HEIGHT - 16
    y_label_x = 20
    y_label_y = MARGIN_TOP + plot_height / 2

    elements: list[str] = [
        f'<rect x="0" y="0" width="{SVG_WIDTH}" height="{SVG_HEIGHT}" fill="#ffffff"/>'
    ]
    elements.append(
        _svg_text(
            title_x,
            title_y,
            title,
            size=18,
            weight=700,
            anchor="middle",
            fill=TEXT_COLOR,
        )
    )
    elements.append(
        _svg_text(
            title_x,
            42,
            f"n = {len(cleaned_values)}",
            size=12,
            anchor="middle",
            fill=MUTED_TEXT_COLOR,
        )
    )
    for tick in _y_ticks(max_y):
        y = _y_to_px(tick, max_y=max_y, plot_height=plot_height, x_axis_y=x_axis_y)
        elements.append(
            f'<line x1="{y_axis_x}" y1="{y}" x2="{SVG_WIDTH - MARGIN_RIGHT}" y2="{y}" '
            f'stroke="{GRID_COLOR}" stroke-width="1" opacity="0.8"/>'
        )
        elements.append(
            _svg_text(
                y_axis_x - 12,
                y + 8,
                _format_tick(tick),
                size=TICK_LABEL_SIZE,
                anchor="end",
                fill=MUTED_TEXT_COLOR,
            )
        )

    for tick in _x_ticks(data_min, data_max):
        x = _x_to_px(value=tick, data_min=data_min, data_max=data_max, plot_width=plot_width)
        elements.append(
            f'<line x1="{x}" y1="{MARGIN_TOP}" x2="{x}" y2="{x_axis_y}" '
            f'stroke="{GRID_COLOR}" stroke-width="1" opacity="0.45"/>'
        )
        elements.append(
            _svg_text(
                x,
                x_axis_y + 46,
                _format_tick(tick),
                size=TICK_LABEL_SIZE,
                anchor="middle",
                fill=MUTED_TEXT_COLOR,
            )
        )

    elements.append(
        f'<line x1="{y_axis_x}" y1="{MARGIN_TOP}" x2="{y_axis_x}" y2="{x_axis_y}" '
        f'stroke="{TEXT_COLOR}" stroke-width="1.2"/>'
    )
    elements.append(
        f'<line x1="{y_axis_x}" y1="{x_axis_y}" x2="{SVG_WIDTH - MARGIN_RIGHT}" y2="{x_axis_y}" '
        f'stroke="{TEXT_COLOR}" stroke-width="1.2"/>'
    )

    bar_gap = plot_width / bins * 0.18
    bar_width = plot_width / bins - bar_gap
    for index, count in enumerate(counts):
        x = MARGIN_LEFT + index * (plot_width / bins) + bar_gap / 2
        bar_height = (count / max_y) * plot_height
        y = x_axis_y - bar_height
        elements.append(
            f'<rect x="{x:.2f}" y="{y:.2f}" width="{bar_width:.2f}" height="{bar_height:.2f}" '
            f'rx="4" fill="{PREFERRED_BAR_COLOR}" stroke="{color}" stroke-opacity="0.35" />'
        )

    path_points = []
    for index, count in enumerate(kde_curve):
        x_value = data_min + (data_max - data_min) * index / max(len(kde_curve) - 1, 1)
        x = _x_to_px(value=x_value, data_min=data_min, data_max=data_max, plot_width=plot_width)
        y = _y_to_px(count, max_y=max_y, plot_height=plot_height, x_axis_y=x_axis_y)
        path_points.append(f"{x:.2f},{y:.2f}")
    if path_points:
        elements.append(
            f'<polyline points="{" ".join(path_points)}" fill="none" '
            f'stroke="{color}" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" />'
        )

    elements.append(
        _svg_text(
            SVG_WIDTH / 2,
            x_label_y,
            x_label,
            size=AXIS_LABEL_SIZE,
            anchor="middle",
            fill=TEXT_COLOR,
            weight=700,
        )
    )
    elements.append(
        f'<g transform="translate({y_label_x} {y_label_y}) rotate(-90)">'
        + _svg_text(
            0,
            0,
            "Count",
            size=AXIS_LABEL_SIZE,
            anchor="middle",
            fill=TEXT_COLOR,
            weight=700,
        )
        + "</g>"
    )

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {SVG_WIDTH} {SVG_HEIGHT}" '
        f'class="ph-score-density-svg" width="100%" style="max-width:100%;height:auto;display:block;" '
        f'role="img" aria-label="{html.escape(title, quote=True)}">'
        f"<title>{html.escape(title)}</title>"
        + "".join(elements)
        + "</svg>"
    )


def _kde_curve(
    values: list[float],
    data_min: float,
    data_max: float,
    bin_width: float,
    *,
    points: int = 160,
) -> list[float]:
    n = len(values)
    if n == 1:
        bandwidth = (data_max - data_min) / 6
    else:
        stdev = pstdev(values)
        bandwidth = 1.06 * stdev * (n ** (-1 / 5)) if stdev > 0 else (data_max - data_min) / 6
    bandwidth = max(bandwidth, (data_max - data_min) / 120, 1e-6)
    normalization = 1 / (n * bandwidth * math.sqrt(2 * math.pi))
    span = data_max - data_min
    curve = []
    for index in range(points):
        x = data_min + span * index / max(points - 1, 1)
        density = normalization * sum(
            math.exp(-0.5 * ((x - value) / bandwidth) ** 2) for value in values
        )
        curve.append(density * n * bin_width)
    return curve


def _x_to_px(*, value: float, data_min: float, data_max: float, plot_width: float) -> float:
    if data_max == data_min:
        return MARGIN_LEFT + plot_width / 2
    return MARGIN_LEFT + ((value - data_min) / (data_max - data_min)) * plot_width


def _y_to_px(value: float, *, max_y: float, plot_height: float, x_axis_y: float) -> float:
    if max_y <= 0:
        return x_axis_y
    return x_axis_y - (value / max_y) * plot_height


def _x_ticks(data_min: float, data_max: float, count: int = 4) -> list[float]:
    if count <= 0:
        return [data_min, data_max]
    span = data_max - data_min
    return [data_min + span * index / count for index in range(count + 1)]


def _y_ticks(max_y: float, count: int = 4) -> list[float]:
    if max_y <= 0:
        return [0.0]
    return [max_y * index / count for index in range(count + 1)]


def _format_tick(value: float) -> str:
    if abs(value) >= 1000 or (0 < abs(value) < 0.01):
        return f"{value:.1e}"
    if abs(value) >= 10:
        return f"{value:.0f}"
    return f"{value:.2f}".rstrip("0").rstrip(".")


def _svg_text(
    x: float,
    y: float,
    text: str,
    *,
    size: int,
    anchor: str = "start",
    fill: str = TEXT_COLOR,
    weight: int = 500,
) -> str:
    return (
        f'<text x="{x:.2f}" y="{y:.2f}" fill="{fill}" font-size="{size}" '
        f'font-weight="{weight}" text-anchor="{anchor}" '
        f'font-family="Inter, Arial, sans-serif">{html.escape(text)}</text>'
    )
