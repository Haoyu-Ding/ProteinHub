from __future__ import annotations

import html
import math
import re
from collections.abc import Callable
from dataclasses import dataclass
from io import BytesIO
from pathlib import PurePosixPath
from zipfile import BadZipFile, ZipFile
import xml.etree.ElementTree as ET

from proteinhub.domain.errors import DomainError


MATCH_COLUMN = "Single cycle kinetics 1 Solution"
SLIDE_PATH_RE = re.compile(r"^ppt/slides/slide(\d+)\.xml$")
KINETIC_TABLE_MARKERS = ("KD (M)", "kd (1/s)", "ka (1/Ms)", "Rmax (RU)")
RELATIONSHIP_ID_ATTR = (
    "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
)
NS = {
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "c": "http://schemas.openxmlformats.org/drawingml/2006/chart",
    "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "rel": "http://schemas.openxmlformats.org/package/2006/relationships",
}


@dataclass(frozen=True)
class SPRChart:
    sample_id: str
    slide_number: int
    svg: bytes


@dataclass(frozen=True)
class SPRChartSpec:
    series: list[dict]
    x_axis: str
    y_axis: str


@dataclass(frozen=True)
class SlidePart:
    number: int
    path: str


def read_spr_pptx(
    content: bytes,
    *,
    sample_annotation_for_id: Callable[[str], str | None] | None = None,
) -> list[dict]:
    try:
        with ZipFile(BytesIO(content)) as deck:
            table_rows = _read_table_rows(deck)
            table_by_sample = _table_rows_by_sample(table_rows)
            charts = _read_charts(
                deck,
                sample_ids=set(table_by_sample),
                sample_annotation_for_id=sample_annotation_for_id,
            )
    except BadZipFile as exc:
        raise DomainError("SPR result file must be a PowerPoint .pptx file") from exc
    except ET.ParseError as exc:
        raise DomainError("SPR result PowerPoint could not be parsed") from exc

    if not table_rows:
        raise DomainError("SPR PowerPoint must include SPR result tables")
    if not charts:
        raise DomainError("SPR PowerPoint must include result charts matching the result table")

    results = []
    for chart in charts:
        table_row = table_by_sample.get(chart.sample_id)
        results.append(
            {
                "sample_id": chart.sample_id,
                "slide_number": chart.slide_number,
                "table_row": table_row,
                "svg": chart.svg,
            }
        )
    return results


def _slide_parts(deck: ZipFile) -> list[SlidePart]:
    parts_by_path = {
        name: SlidePart(number=int(match.group(1)), path=name)
        for name in deck.namelist()
        if (match := SLIDE_PATH_RE.fullmatch(name))
    }
    ordered_paths = _ordered_slide_paths(deck)
    if not ordered_paths:
        return sorted(parts_by_path.values(), key=lambda part: part.number)

    ordered_parts = []
    seen_paths = set()
    for path in ordered_paths:
        part = parts_by_path.get(path)
        if part is None:
            continue
        ordered_parts.append(part)
        seen_paths.add(path)
    ordered_parts.extend(
        part
        for part in sorted(parts_by_path.values(), key=lambda item: item.number)
        if part.path not in seen_paths
    )
    return ordered_parts


def _ordered_slide_paths(deck: ZipFile) -> list[str]:
    names = set(deck.namelist())
    if "ppt/presentation.xml" not in names:
        return []
    relationships = _relationships_for_part(deck, "ppt/presentation.xml")
    if not relationships:
        return []

    root = ET.fromstring(deck.read("ppt/presentation.xml"))
    ordered_paths = []
    for slide_id in root.findall(".//p:sldIdLst/p:sldId", NS):
        relationship_id = slide_id.attrib.get(RELATIONSHIP_ID_ATTR)
        relationship = relationships.get(relationship_id)
        if not relationship:
            continue
        if not relationship.get("Type", "").endswith("/slide"):
            continue
        path = _resolve_part_path("ppt/presentation.xml", relationship.get("Target", ""))
        if SLIDE_PATH_RE.fullmatch(path):
            ordered_paths.append(path)
    return ordered_paths


def _read_charts(
    deck: ZipFile,
    *,
    sample_ids: set[str],
    sample_annotation_for_id: Callable[[str], str | None] | None = None,
) -> list[SPRChart]:
    charts = []
    names = set(deck.namelist())
    seen_sample_ids = set()
    for slide in _slide_parts(deck):
        slide_root = ET.fromstring(deck.read(slide.path))
        sample_id = _sample_id_from_slide(slide_root, sample_ids=sample_ids)
        if not sample_id:
            continue
        for chart_path in _chart_paths_for_slide(deck, slide.path, slide_root):
            if chart_path not in names:
                continue
            chart_root = ET.fromstring(deck.read(chart_path))
            series = _chart_series(chart_root)
            if not series:
                continue
            if sample_id in seen_sample_ids:
                raise DomainError(f"Duplicate SPR chart for {sample_id}")
            charts.append(
                SPRChart(
                    sample_id=sample_id,
                    slide_number=slide.number,
                    svg=render_spr_chart_svg(
                        sample_id=sample_id,
                        slide_number=slide.number,
                        series=series,
                        x_axis=_axis_title(chart_root, index=0) or "Time (s)",
                        y_axis=_axis_title(chart_root, index=1) or "Relative response (RU)",
                        header_text=(
                            sample_annotation_for_id(sample_id)
                            if sample_annotation_for_id is not None
                            else ""
                        )
                        or "",
                    ),
                )
            )
            seen_sample_ids.add(sample_id)
            break
    return charts


def _sample_id_from_slide(
    slide_root: ET.Element,
    *,
    sample_ids: set[str],
) -> str:
    fallback = ""
    for text in slide_root.findall(".//a:t", NS):
        value = (text.text or "").strip()
        if not value:
            continue
        sample_id = value.split(";", 1)[0].strip()
        if sample_id in sample_ids:
            return sample_id
        if not fallback:
            fallback = sample_id
    return fallback if fallback in sample_ids else ""


def _chart_paths_for_slide(
    deck: ZipFile,
    slide_path: str,
    slide_root: ET.Element,
) -> list[str]:
    relationships = _relationships_for_part(deck, slide_path)
    if not relationships:
        return []

    chart_paths = []
    for graphic_frame in slide_root.findall(".//p:graphicFrame", NS):
        for element in graphic_frame.iter():
            relationship_id = element.attrib.get(RELATIONSHIP_ID_ATTR)
            relationship = relationships.get(relationship_id)
            if not relationship:
                continue
            if relationship.get("TargetMode") == "External":
                continue
            if relationship.get("Type", "").endswith("/chart"):
                target = relationship.get("Target", "")
                path = _resolve_part_path(slide_path, target)
                if path:
                    chart_paths.append(path)
    return chart_paths


def _relationships_for_part(deck: ZipFile, source_path: str) -> dict[str | None, dict]:
    rel_path = (
        PurePosixPath(source_path).parent
        / "_rels"
        / f"{PurePosixPath(source_path).name}.rels"
    )
    if str(rel_path) not in deck.namelist():
        return {}
    rel_root = ET.fromstring(deck.read(str(rel_path)))
    return {
        rel.attrib.get("Id"): rel.attrib
        for rel in rel_root.findall("rel:Relationship", NS)
    }


def _resolve_part_path(source_path: str, target: str) -> str:
    target_path = PurePosixPath(target)
    if target_path.is_absolute():
        raw_path = str(target_path).lstrip("/")
    else:
        raw_path = str(PurePosixPath(source_path).parent / target_path)

    parts = []
    for part in PurePosixPath(raw_path).parts:
        if part in ("", "."):
            continue
        if part == "..":
            if parts:
                parts.pop()
            continue
        parts.append(part)
    return "/".join(parts)


def _chart_series(chart_root: ET.Element) -> list[dict]:
    series = []
    for index, ser in enumerate(chart_root.findall(".//c:scatterChart/c:ser", NS)):
        x_values = _num_cache_values(ser.find("c:xVal", NS))
        y_values = _num_cache_values(ser.find("c:yVal", NS))
        points = [
            (x, y)
            for x, y in zip(x_values, y_values, strict=False)
            if math.isfinite(x) and math.isfinite(y)
        ]
        if not points:
            continue
        series.append(
            {
                "label": _series_label(ser) or str(index + 1),
                "color": _series_color(ser, index),
                "points": _decimate(points, max_points=700),
            }
        )
    return series


def _num_cache_values(parent: ET.Element | None) -> list[float]:
    if parent is None:
        return []
    values = []
    for point in parent.findall(".//c:numCache/c:pt", NS):
        value_node = point.find("c:v", NS)
        if value_node is None or value_node.text is None:
            continue
        try:
            values.append(float(value_node.text))
        except ValueError:
            continue
    return values


def _series_label(ser: ET.Element) -> str:
    label = ser.find(".//c:tx//c:strCache/c:pt/c:v", NS)
    return (label.text or "").strip() if label is not None else ""


def _legend_label(label: str) -> str:
    if label == "1":
        return "raw data"
    if label == "2":
        return "fitted data"
    return label


def _series_color(ser: ET.Element, index: int) -> str:
    color = ser.find(".//c:spPr/a:ln/a:solidFill/a:srgbClr", NS)
    if color is not None:
        value = color.attrib.get("val", "")
        if len(value) == 6:
            return f"#{value}"
    palette = ("#2563eb", "#0f766e", "#f97316", "#7c3aed", "#dc2626", "#475569")
    return palette[index % len(palette)]


def _axis_title(chart_root: ET.Element, *, index: int) -> str:
    axes = chart_root.findall(".//c:valAx", NS)
    if index >= len(axes):
        return ""
    texts = [
        text.text.strip()
        for text in axes[index].findall(".//c:title//a:t", NS)
        if text.text and text.text.strip()
    ]
    return " ".join(texts)


def _decimate(points: list[tuple[float, float]], *, max_points: int) -> list[tuple[float, float]]:
    if len(points) <= max_points:
        return points
    step = math.ceil(len(points) / max_points)
    return points[::step]


def _chart_svg(
    *,
    sample_id: str,
    slide_number: int,
    series: list[dict],
    x_axis: str,
    y_axis: str,
    header_text: str = "",
) -> bytes:
    width = 960
    height = 560
    left = 82
    right = 28
    bottom = 72
    header_text = header_text.strip()
    top = 56 + (22 if header_text else 0)
    plot_width = width - left - right
    plot_height = height - top - bottom
    all_points = [point for line in series for point in line["points"]]
    min_x, max_x = _bounds([point[0] for point in all_points])
    min_y, max_y = _bounds([point[1] for point in all_points], include_zero=True)

    def x_coord(value: float) -> float:
        return left + (value - min_x) / (max_x - min_x) * plot_width

    def y_coord(value: float) -> float:
        return top + (max_y - value) / (max_y - min_y) * plot_height

    elements = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-label="{html.escape(sample_id)} SPR result">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        f'<text x="{left}" y="30" font-family="Arial, sans-serif" font-size="20" font-weight="700" fill="#0f172a">{html.escape(sample_id)} SPR result</text>',
        f'<text x="{width - right}" y="30" text-anchor="end" font-family="Arial, sans-serif" font-size="12" fill="#64748b">slide {slide_number}</text>',
    ]
    if header_text:
        elements.append(
            f'<text x="{left}" y="50" font-family="Arial, sans-serif" font-size="12" fill="#64748b">'
            f'{html.escape(header_text)}</text>'
        )
    for tick in range(6):
        ratio = tick / 5
        x_value = min_x + (max_x - min_x) * ratio
        x = left + plot_width * ratio
        elements.append(f'<line x1="{x:.2f}" y1="{top}" x2="{x:.2f}" y2="{top + plot_height}" stroke="#e2e8f0" stroke-width="1"/>')
        elements.append(f'<text x="{x:.2f}" y="{top + plot_height + 24}" text-anchor="middle" font-family="Arial, sans-serif" font-size="11" fill="#64748b">{_format_tick(x_value)}</text>')
    for tick in range(6):
        ratio = tick / 5
        y_value = min_y + (max_y - min_y) * ratio
        y = top + plot_height * (1 - ratio)
        elements.append(f'<line x1="{left}" y1="{y:.2f}" x2="{left + plot_width}" y2="{y:.2f}" stroke="#e2e8f0" stroke-width="1"/>')
        elements.append(f'<text x="{left - 10}" y="{y + 4:.2f}" text-anchor="end" font-family="Arial, sans-serif" font-size="11" fill="#64748b">{_format_tick(y_value)}</text>')
    elements.extend(
        [
            f'<line x1="{left}" y1="{top}" x2="{left}" y2="{top + plot_height}" stroke="#334155" stroke-width="1.3"/>',
            f'<line x1="{left}" y1="{top + plot_height}" x2="{left + plot_width}" y2="{top + plot_height}" stroke="#334155" stroke-width="1.3"/>',
            f'<text x="{left + plot_width / 2}" y="{height - 22}" text-anchor="middle" font-family="Arial, sans-serif" font-size="13" fill="#475569">{html.escape(x_axis)}</text>',
            f'<text x="20" y="{top + plot_height / 2}" transform="rotate(-90 20 {top + plot_height / 2})" text-anchor="middle" font-family="Arial, sans-serif" font-size="13" fill="#475569">{html.escape(y_axis)}</text>',
        ]
    )
    legend_y = top + 18
    for index, line in enumerate(series):
        points = " ".join(
            f"{x_coord(x):.2f},{y_coord(y):.2f}" for x, y in line["points"]
        )
        elements.append(
            f'<polyline points="{points}" fill="none" stroke="{line["color"]}" stroke-width="1.8" stroke-linejoin="round" stroke-linecap="round"/>'
        )
        if index < 8:
            y = legend_y + index * 18
            elements.append(f'<line x1="{width - 156}" y1="{y}" x2="{width - 130}" y2="{y}" stroke="{line["color"]}" stroke-width="2"/>')
            elements.append(
                f'<text x="{width - 124}" y="{y + 4}" font-family="Arial, sans-serif" font-size="11" fill="#475569">'
                f'{html.escape(_legend_label(line["label"]))}</text>'
            )
    elements.append("</svg>")
    return "\n".join(elements).encode("utf-8")


def render_spr_chart_svg(
    *,
    sample_id: str,
    slide_number: int,
    series: list[dict],
    x_axis: str,
    y_axis: str,
    header_text: str = "",
) -> bytes:
    return _chart_svg(
        sample_id=sample_id,
        slide_number=slide_number,
        series=series,
        x_axis=x_axis,
        y_axis=y_axis,
        header_text=header_text,
    )


def extract_spr_chart_spec(svg: bytes) -> SPRChartSpec:
    root = ET.fromstring(svg)
    series = _extract_svg_series(root)
    if not series:
        raise DomainError("SPR chart SVG did not include any series")
    x_axis = _extract_svg_axis_title(root, axis="x") or "Time (s)"
    y_axis = _extract_svg_axis_title(root, axis="y") or "Relative response (RU)"
    return SPRChartSpec(series=series, x_axis=x_axis, y_axis=y_axis)


def _extract_svg_series(root: ET.Element) -> list[dict]:
    svg_namespace = "{http://www.w3.org/2000/svg}"
    polylines = root.findall(f".//{svg_namespace}polyline")
    legend_labels = _extract_svg_legend_labels(root)
    series = []
    for index, polyline in enumerate(polylines):
        points_text = polyline.attrib.get("points", "").strip()
        points = []
        for pair in points_text.split():
            try:
                x_text, y_text = pair.split(",", 1)
                points.append((float(x_text), float(y_text)))
            except ValueError:
                continue
        if not points:
            continue
        series.append(
            {
                "label": legend_labels[index] if index < len(legend_labels) else str(index + 1),
                "color": polyline.attrib.get("stroke", "#2563eb"),
                "points": points,
            }
        )
    return series


def _extract_svg_legend_labels(root: ET.Element) -> list[str]:
    svg_namespace = "{http://www.w3.org/2000/svg}"
    width = float(root.attrib.get("width", "960"))
    legend_x = width - 124
    labels = []
    for text in root.findall(f".//{svg_namespace}text"):
        if text.attrib.get("transform"):
            continue
        try:
            x_value = float(text.attrib.get("x", "nan"))
        except ValueError:
            continue
        if abs(x_value - legend_x) > 0.5:
            continue
        label = "".join(text.itertext()).strip()
        if label:
            labels.append(label)
    return labels


def _extract_svg_axis_title(root: ET.Element, *, axis: str) -> str:
    svg_namespace = "{http://www.w3.org/2000/svg}"
    for text in root.findall(f".//{svg_namespace}text"):
        label = "".join(text.itertext()).strip()
        if not label:
            continue
        if axis == "x":
            if text.attrib.get("transform"):
                continue
            if text.attrib.get("font-size") == "13" and text.attrib.get("fill") == "#475569":
                return label
        else:
            transform = text.attrib.get("transform", "")
            if "rotate(-90" in transform:
                return label
    return ""


def _bounds(values: list[float], *, include_zero: bool = False) -> tuple[float, float]:
    if include_zero:
        values = [*values, 0.0]
    min_value = min(values)
    max_value = max(values)
    if min_value == max_value:
        pad = abs(min_value) * 0.1 or 1.0
        return min_value - pad, max_value + pad
    pad = (max_value - min_value) * 0.04
    return min_value - pad, max_value + pad


def _format_tick(value: float) -> str:
    if value == 0:
        return "0"
    if abs(value) >= 1000 or abs(value) < 0.01:
        return f"{value:.1e}"
    if abs(value) >= 10:
        return f"{value:.0f}"
    return f"{value:.2f}".rstrip("0").rstrip(".")


def _read_table_rows(deck: ZipFile) -> list[dict[str, str]]:
    rows = []
    seen_sample_ids = set()
    for slide in _slide_parts(deck):
        root = ET.fromstring(deck.read(slide.path))
        for table in root.findall(".//a:tbl", NS):
            for row in _spr_rows_from_table(table):
                sample_id = row[MATCH_COLUMN]
                if sample_id in seen_sample_ids:
                    raise DomainError(f"Duplicate SPR table row for {sample_id}")
                seen_sample_ids.add(sample_id)
                rows.append(row)
    return rows


def _spr_rows_from_table(table: ET.Element) -> list[dict[str, str]]:
    parsed_rows = _table_rows(table)
    for header_index, header in enumerate(parsed_rows):
        headers = [_normalize_header(value) for value in header]
        if not _is_spr_result_table(headers):
            continue
        rows = []
        for row in parsed_rows[header_index + 1 :]:
            if not any(row):
                continue
            padded = [*row, *([""] * (len(headers) - len(row)))]
            row_dict = {
                header: padded[index]
                for index, header in enumerate(headers)
                if header
            }
            sample_id = row_dict.get(MATCH_COLUMN, "").strip()
            if sample_id:
                row_dict[MATCH_COLUMN] = sample_id
                rows.append(row_dict)
        return rows
    return []


def _table_rows_by_sample(table_rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    table_by_sample = {}
    for row in table_rows:
        sample_id = row[MATCH_COLUMN]
        if sample_id in table_by_sample:
            raise DomainError(f"Duplicate SPR table row for {sample_id}")
        table_by_sample[sample_id] = row
    return table_by_sample


def _table_rows(table: ET.Element) -> list[list[str]]:
    rows = []
    for table_row in table.findall("a:tr", NS):
        cells = []
        for cell in table_row.findall("a:tc", NS):
            values = [
                text.text.strip()
                for text in cell.findall(".//a:t", NS)
                if text.text and text.text.strip()
            ]
            cells.append("\n".join(values))
        rows.append(cells)
    return rows


def _normalize_header(value: str) -> str:
    return " ".join(value.split())


def _is_spr_result_table(headers: list[str]) -> bool:
    if MATCH_COLUMN not in headers:
        return False
    return any(
        marker in header
        for marker in KINETIC_TABLE_MARKERS
        for header in headers
    )
