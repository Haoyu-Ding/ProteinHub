from __future__ import annotations

from datetime import date
from html import escape

import segno


LABEL_WIDTH_MM = 50
LABEL_HEIGHT_MM = 30
LABEL_WIDTH_UNITS = 500
LABEL_HEIGHT_UNITS = 300
QR_X = 318
QR_Y = 56
QR_SIZE = 164
QR_BORDER_MODULES = 2
DEFAULT_OWNER_NAME = "未命名负责人"
FONT_FAMILY = "Arial, 'PingFang SC', 'Noto Sans CJK SC', sans-serif"


def render_batch_label_svg(
    *,
    owner_name: str,
    batch_id: int,
    print_date: date,
    target_url: str,
) -> str:
    owner_label = _fit_label(owner_name.strip() or DEFAULT_OWNER_NAME, limit=18)
    escaped_url = escape(target_url, quote=True)
    qr_path = _qr_path(target_url)
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{LABEL_WIDTH_MM}mm" height="{LABEL_HEIGHT_MM}mm" viewBox="0 0 {LABEL_WIDTH_UNITS} {LABEL_HEIGHT_UNITS}" role="img" aria-labelledby="title desc">
  <title id="title">ProteinHub batch label {batch_id}</title>
  <desc id="desc">Batch detail URL: {escaped_url}</desc>
  <rect width="{LABEL_WIDTH_UNITS}" height="{LABEL_HEIGHT_UNITS}" rx="8" fill="#ffffff"/>
  <rect x="4" y="4" width="492" height="292" rx="8" fill="none" stroke="#111827" stroke-width="2"/>
  <line x1="298" y1="24" x2="298" y2="276" stroke="#d1d5db" stroke-width="2"/>
  <g font-family="{FONT_FAMILY}" fill="#111827">
    <text x="26" y="62" font-size="18" font-weight="600">项目负责人</text>
    <text x="26" y="96" font-size="25" font-weight="700">{escape(owner_label)}</text>
    <text x="26" y="144" font-size="18" font-weight="600">批次 ID</text>
    <text x="26" y="178" font-size="25" font-weight="700">{batch_id}</text>
    <text x="26" y="226" font-size="18" font-weight="600">打印日期</text>
    <text x="26" y="260" font-size="25" font-weight="700">{print_date.isoformat()}</text>
  </g>
  <rect x="{QR_X}" y="{QR_Y}" width="{QR_SIZE}" height="{QR_SIZE}" fill="#ffffff"/>
  <g shape-rendering="crispEdges" data-url="{escaped_url}">
    {qr_path}
  </g>
</svg>
"""


def _qr_path(target_url: str) -> str:
    qr = segno.make(target_url, error="m")
    matrix = tuple(tuple(row) for row in qr.matrix)
    module_count = len(matrix)
    total_modules = module_count + QR_BORDER_MODULES * 2
    module_size = QR_SIZE / total_modules
    path_segments = []
    module_size_text = _format_number(module_size)
    for row_index, row in enumerate(matrix):
        for column_index, is_dark in enumerate(row):
            if not is_dark:
                continue
            x = QR_X + (column_index + QR_BORDER_MODULES) * module_size
            y = QR_Y + (row_index + QR_BORDER_MODULES) * module_size
            path_segments.append(
                f"M{_format_number(x)} {_format_number(y)}"
                f"h{module_size_text}v{module_size_text}h-{module_size_text}z"
            )
    return f'<path d="{"".join(path_segments)}" fill="#111827"/>'


def _format_number(value: float) -> str:
    text = f"{value:.3f}".rstrip("0").rstrip(".")
    return text or "0"


def _fit_label(value: str, *, limit: int) -> str:
    compact = " ".join(value.split())
    if len(compact) <= limit:
        return compact
    return f"{compact[: max(limit - 3, 1)]}..."
