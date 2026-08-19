from __future__ import annotations

import csv
import html
import math
import re
from dataclasses import dataclass
from io import StringIO
from pathlib import Path

from proteinhub.domain.errors import DomainError
from proteinhub.domain.plate_positions import extract_unique_plate_position


SVG_WIDTH = 960
SVG_HEIGHT = 460
MARGIN_TOP = 56
MARGIN_RIGHT = 28
MARGIN_BOTTOM = 88
MARGIN_LEFT = 92
TITLE_SIZE = 19
SUBTITLE_SIZE = 12
TICK_LABEL_SIZE = 12
AXIS_LABEL_SIZE = 15
GRID_COLOR = "#e2e8f0"
TEXT_COLOR = "#334155"
MUTED_TEXT_COLOR = "#64748b"
LINE_COLOR = "#0f766e"
BLOCK_COLORS = (
    "#bfdbfe",
    "#c7f9cc",
    "#fde68a",
    "#e9d5ff",
    "#fecaca",
    "#fbcfe8",
)
MIN_RENDERED_BLOCK_DURATION = 0.01
SAMPLE_SUFFIX_RE = re.compile(r"(?i)\.dx_[^.]+\.csv$")


@dataclass(frozen=True)
class HPLCBlock:
    index: int
    position: str
    start: float
    end: float
    volume: float | None = None


def sample_key_from_filename(filename: str) -> str:
    name = Path(filename.replace("\\", "/")).name.strip()
    if not name:
        raise DomainError("HPLC filename is required")
    stripped = SAMPLE_SUFFIX_RE.sub("", name)
    if stripped == name:
        stripped = Path(name).stem
    return stripped.strip()


def plate_position_from_filename(filename: str) -> str:
    sample_key = sample_key_from_filename(filename)
    return extract_unique_plate_position(sample_key, label="HPLC filename")


def read_hplc_chromatogram_csv(file: tuple[str, str, bytes]) -> list[tuple[float, float]]:
    filename, _content_type, content = file
    file_name = Path(filename.replace("\\", "/")).name
    if not file_name.lower().endswith(".csv"):
        raise DomainError("HPLC chromatogram must be a CSV file")
    text = _decode_utf8_csv(content, "HPLC chromatogram CSV")
    reader = csv.reader(StringIO(text))
    points = []
    for row in reader:
        if len(row) < 2:
            continue
        first = row[0].strip()
        second = row[1].strip()
        if not first or not second:
            continue
        try:
            points.append((float(first), float(second)))
        except ValueError:
            continue
    if not points:
        raise DomainError(
            f"HPLC chromatogram CSV {file_name} did not include numeric time and value columns"
        )
    return points


def read_hplc_vial_fc_csv(file: tuple[str, str, bytes]) -> dict[str, list[HPLCBlock]]:
    filename, _content_type, content = file
    file_name = Path(filename.replace("\\", "/")).name
    if file_name.lower() != "vial_fc.csv":
        raise DomainError("HPLC vial mapping file must be vial_fc.csv")
    text = _decode_utf8_csv(content, "HPLC vial mapping CSV")
    reader = csv.reader(StringIO(text))
    sections: dict[str, list[HPLCBlock]] = {}
    current_sample: str | None = None
    header_seen = False

    for row in reader:
        if not any(cell.strip() for cell in row):
            continue
        first = row[0].strip()
        if first == "样品 名称":
            if len(row) < 2 or not row[1].strip():
                raise DomainError("vial_fc.csv must include a sample name")
            current_sample = sample_key_from_filename(row[1])
            if current_sample in sections:
                raise DomainError(f"Duplicate vial_fc.csv section for {current_sample}")
            sections[current_sample] = []
            header_seen = False
            continue
        if first.startswith("参比检测器"):
            current_sample = None
            header_seen = False
            continue
        if current_sample is None:
            continue
        if not header_seen:
            headers = [cell.strip() for cell in row]
            expected = ["编号", "位置", "开始时间 (min)", "结束时间 (min)"]
            if len(headers) < 4 or headers[:4] != expected:
                raise DomainError("vial_fc.csv must include the fixed fraction table columns")
            header_seen = True
            continue
        sections[current_sample].append(_parse_hplc_block_row(row, current_sample))

    if not sections:
        raise DomainError("vial_fc.csv did not include any sample sections")
    return sections


def render_hplc_chromatogram_svg(
    *,
    sample_key: str,
    plate_position: str,
    points: list[tuple[float, float]],
    blocks: list[HPLCBlock],
) -> bytes:
    cleaned_points = [
        (x, y)
        for x, y in points
        if math.isfinite(x) and math.isfinite(y)
    ]
    if not cleaned_points:
        raise DomainError("HPLC chromatogram did not include numeric points")

    rendered_blocks = [
        block
        for block in blocks
        if block.end - block.start >= MIN_RENDERED_BLOCK_DURATION
    ]
    x_values = [x for x, _ in cleaned_points]
    x_values.extend(block.start for block in rendered_blocks)
    x_values.extend(block.end for block in rendered_blocks)
    y_values = [y for _, y in cleaned_points]
    x_min, x_max = _bounds(x_values)
    y_min, y_max = _bounds(y_values)

    plot_width = SVG_WIDTH - MARGIN_LEFT - MARGIN_RIGHT
    plot_height = SVG_HEIGHT - MARGIN_TOP - MARGIN_BOTTOM
    x_axis_y = SVG_HEIGHT - MARGIN_BOTTOM
    y_axis_x = MARGIN_LEFT
    title_x = MARGIN_LEFT + plot_width / 2

    elements: list[str] = [
        f'<rect x="0" y="0" width="{SVG_WIDTH}" height="{SVG_HEIGHT}" fill="#ffffff"/>'
    ]
    elements.append(
        _svg_text(
            title_x,
            24,
            f"HPLC {plate_position}",
            size=TITLE_SIZE,
            weight=700,
            anchor="middle",
            fill=TEXT_COLOR,
        )
    )
    elements.append(
        _svg_text(
            title_x,
            42,
            f"{sample_key} · {len(blocks)} fraction windows",
            size=SUBTITLE_SIZE,
            anchor="middle",
            fill=MUTED_TEXT_COLOR,
        )
    )

    for index, block in enumerate(rendered_blocks):
        left = _x_to_px(value=block.start, data_min=x_min, data_max=x_max, plot_width=plot_width)
        right = _x_to_px(value=block.end, data_min=x_min, data_max=x_max, plot_width=plot_width)
        color = BLOCK_COLORS[index % len(BLOCK_COLORS)]
        title = (
            f"{block.position} {block.start:.3f}-{block.end:.3f} min"
            + (f" · {block.volume:.2f} mL" if block.volume is not None else "")
        )
        width = max(right - left, 1.0)
        elements.append(
            f'<rect x="{left:.2f}" y="{MARGIN_TOP}" width="{width:.2f}" height="{plot_height}" '
            f'rx="4" fill="{color}" fill-opacity="0.24" stroke="{color}" stroke-opacity="0.45">'
            f"<title>{html.escape(title)}</title>"
            "</rect>"
        )

    for tick in _y_ticks(y_min, y_max):
        y = _y_to_px(value=tick, data_min=y_min, data_max=y_max, plot_height=plot_height)
        elements.append(
            f'<line x1="{y_axis_x}" y1="{y}" x2="{SVG_WIDTH - MARGIN_RIGHT}" y2="{y}" '
            f'stroke="{GRID_COLOR}" stroke-width="1" opacity="0.8"/>'
        )
        elements.append(
            _svg_text(
                y_axis_x - 12,
                y + 4,
                _format_tick(tick),
                size=TICK_LABEL_SIZE,
                anchor="end",
                fill=MUTED_TEXT_COLOR,
            )
        )

    for tick in _x_ticks(x_min, x_max):
        x = _x_to_px(value=tick, data_min=x_min, data_max=x_max, plot_width=plot_width)
        elements.append(
            f'<line x1="{x}" y1="{MARGIN_TOP}" x2="{x}" y2="{x_axis_y}" '
            f'stroke="{GRID_COLOR}" stroke-width="1" opacity="0.45"/>'
        )
        elements.append(
            _svg_text(
                x,
                x_axis_y + 28,
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

    path_points = [
        f"{_x_to_px(value=x, data_min=x_min, data_max=x_max, plot_width=plot_width):.2f},"
        f"{_y_to_px(value=y, data_min=y_min, data_max=y_max, plot_height=plot_height):.2f}"
        for x, y in cleaned_points
    ]
    elements.append(
        f'<polyline points="{" ".join(path_points)}" fill="none" '
        f'stroke="{LINE_COLOR}" stroke-width="2.4" stroke-linejoin="round" stroke-linecap="round"/>'
    )

    elements.append(
        _svg_text(
            SVG_WIDTH / 2,
            SVG_HEIGHT - 16,
            "Time (min)",
            size=AXIS_LABEL_SIZE,
            anchor="middle",
            fill=TEXT_COLOR,
            weight=700,
        )
    )
    elements.append(
        f'<g transform="translate(22 {MARGIN_TOP + plot_height / 2:.2f}) rotate(-90)">'
        + _svg_text(
            0,
            0,
            "Signal",
            size=AXIS_LABEL_SIZE,
            anchor="middle",
            fill=TEXT_COLOR,
            weight=700,
        )
        + "</g>"
    )

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {SVG_WIDTH} {SVG_HEIGHT}" '
        f'class="ph-hplc-svg" width="100%" style="max-width:100%;height:auto;display:block;" '
        f'role="img" aria-label="{html.escape(f"HPLC {plate_position}", quote=True)}">'
        f"<title>{html.escape(f'HPLC {plate_position}')}</title>"
        + "".join(elements)
        + "</svg>"
    ).encode("utf-8")


def _parse_hplc_block_row(row: list[str], sample_key: str) -> HPLCBlock:
    if len(row) < 4:
        raise DomainError(f"vial_fc.csv has an invalid fraction row for {sample_key}")
    try:
        index = int(row[0].strip())
        start = float(row[2].strip())
        end = float(row[3].strip())
    except ValueError as exc:
        raise DomainError(f"vial_fc.csv has an invalid fraction row for {sample_key}") from exc
    if end < start:
        raise DomainError(f"vial_fc.csv has a non-increasing fraction range for {sample_key}")
    position = row[1].strip()
    if not position:
        raise DomainError(f"vial_fc.csv has an invalid fraction position for {sample_key}")
    volume = None
    if len(row) > 4 and row[4].strip():
        try:
            volume = float(row[4].strip())
        except ValueError as exc:
            raise DomainError(f"vial_fc.csv has an invalid fraction row for {sample_key}") from exc
    return HPLCBlock(index=index, position=position, start=start, end=end, volume=volume)


def _decode_utf8_csv(content: bytes, label: str) -> str:
    try:
        return content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise DomainError(f"{label} must be UTF-8 CSV") from exc


def _bounds(values: list[float]) -> tuple[float, float]:
    min_value = min(values)
    max_value = max(values)
    if min_value == max_value:
        pad = abs(min_value) * 0.1 or 1.0
        return min_value - pad, max_value + pad
    pad = (max_value - min_value) * 0.04
    return min_value - pad, max_value + pad


def _x_to_px(*, value: float, data_min: float, data_max: float, plot_width: float) -> float:
    if data_max == data_min:
        return MARGIN_LEFT + plot_width / 2
    return MARGIN_LEFT + ((value - data_min) / (data_max - data_min)) * plot_width


def _y_to_px(*, value: float, data_min: float, data_max: float, plot_height: float) -> float:
    if data_max == data_min:
        return MARGIN_TOP + plot_height / 2
    return MARGIN_TOP + (1 - ((value - data_min) / (data_max - data_min))) * plot_height


def _x_ticks(data_min: float, data_max: float, count: int = 4) -> list[float]:
    if count <= 0:
        return [data_min, data_max]
    span = data_max - data_min
    return [data_min + span * index / count for index in range(count + 1)]


def _y_ticks(data_min: float, data_max: float, count: int = 4) -> list[float]:
    if count <= 0:
        return [data_min, data_max]
    span = data_max - data_min
    if span == 0:
        return [data_min]
    return [data_min + span * index / count for index in range(count + 1)]


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
