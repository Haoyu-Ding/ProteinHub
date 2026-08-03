from __future__ import annotations

from datetime import UTC, datetime
from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile
from xml.sax.saxutils import escape, quoteattr


ROWS = "ABCDEFGH"
COLUMNS = range(1, 13)
MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"


def build_plate_workbook(batch: dict, wells: list[dict]) -> bytes:
    return _build_workbook("Plate 1", _plate_sheet_xml(batch, wells))


def build_summary_workbook(batch: dict, wells: list[dict]) -> bytes:
    return _build_workbook("Summary", _summary_sheet_xml(batch, wells))


def _build_workbook(sheet_name: str, sheet_xml: str) -> bytes:
    files = {
        "[Content_Types].xml": _content_types_xml(),
        "_rels/.rels": _root_relationships_xml(),
        "docProps/app.xml": _app_properties_xml(),
        "docProps/core.xml": _core_properties_xml(),
        "xl/workbook.xml": _workbook_xml(sheet_name),
        "xl/_rels/workbook.xml.rels": _workbook_relationships_xml(),
        "xl/styles.xml": _styles_xml(),
        "xl/worksheets/sheet1.xml": sheet_xml,
    }
    buffer = BytesIO()
    with ZipFile(buffer, "w", ZIP_DEFLATED) as archive:
        for path, content in files.items():
            archive.writestr(path, content)
    return buffer.getvalue()


def _plate_sheet_xml(batch: dict, wells: list[dict]) -> str:
    by_position = {well["position"]: well["protein_name"] for well in wells}
    rows_xml = []
    rows_xml.append(
        _row_xml(
            1,
            [_inline_cell("A1", _plate_title(batch), 1)]
            + [_number_cell(_cell_ref(column + 1, 1), column, 2) for column in COLUMNS],
            height=48,
        )
    )
    for row_index, row_name in enumerate(ROWS, start=2):
        cells = [_inline_cell(f"A{row_index}", row_name, 2)]
        for column in COLUMNS:
            position = f"{row_name}{column:02d}"
            protein_name = by_position.get(position, "")
            if protein_name:
                cells.append(_inline_cell(_cell_ref(column + 1, row_index), protein_name, 3))
        rows_xml.append(_row_xml(row_index, cells, height=54))

    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="{MAIN_NS}" xmlns:r="{REL_NS}">
  <dimension ref="A1:M9"/>
  <sheetViews>
    <sheetView workbookViewId="0"/>
  </sheetViews>
  <sheetFormatPr defaultRowHeight="54"/>
  <cols>
    <col min="1" max="1" width="9" customWidth="1"/>
    <col min="2" max="13" width="12" customWidth="1"/>
  </cols>
  <sheetData>
    {"".join(rows_xml)}
  </sheetData>
  <pageMargins left="0.7" right="0.7" top="0.75" bottom="0.75" header="0.3" footer="0.3"/>
</worksheet>"""


def _summary_sheet_xml(batch: dict, wells: list[dict]) -> str:
    lengths = [len(_summary_sequence(well)) for well in wells]
    min_length = min(lengths) if lengths else 0
    max_length = max(lengths) if lengths else 0
    length_range = f"{max_length}-{min_length}" if lengths else "0-0"

    rows_xml = [
        _row_xml(1, [_inline_cell("A1", "Batch Summary", 1)], height=28),
        _row_xml(
            2,
            [
                _inline_cell("A2", "Batch", 2),
                _inline_cell("B2", batch["name"], 3),
            ],
            height=24,
        ),
        _row_xml(
            3,
            [
                _inline_cell("A3", "Plate format", 2),
                _inline_cell("B3", f"{batch['plate_format']} wells", 3),
            ],
            height=24,
        ),
        _row_xml(
            4,
            [
                _inline_cell("A4", "Backbone", 2),
                _inline_cell("B4", _summary_text(batch.get("translation_backbone")), 3),
            ],
            height=24,
        ),
        _row_xml(
            5,
            [
                _inline_cell("A5", "Resistance", 2),
                _inline_cell("B5", _summary_text(batch.get("translation_resistance")), 3),
            ],
            height=24,
        ),
        _row_xml(
            6,
            [
                _inline_cell("A6", "Total seqs", 2),
                _number_cell("B6", len(wells), 3),
            ],
            height=24,
        ),
        _row_xml(
            7,
            [
                _inline_cell("A7", "Max length", 2),
                _number_cell("B7", max_length, 3),
            ],
            height=24,
        ),
        _row_xml(
            8,
            [
                _inline_cell("A8", "Min length", 2),
                _number_cell("B8", min_length, 3),
            ],
            height=24,
        ),
        _row_xml(
            9,
            [
                _inline_cell("A9", "Length range (max-min)", 2),
                _inline_cell("B9", length_range, 3),
            ],
            height=24,
        ),
        _row_xml(
            11,
            [
                _inline_cell("A11", "Position", 2),
                _inline_cell("B11", "Protein", 2),
                _inline_cell("C11", "AA length", 2),
            ],
            height=24,
        ),
    ]
    for row_index, well in enumerate(wells, start=12):
        sequence = _summary_sequence(well)
        rows_xml.append(
            _row_xml(
                row_index,
                [
                    _inline_cell(f"A{row_index}", well["position"], 3),
                    _inline_cell(f"B{row_index}", well["protein_name"], 3),
                    _number_cell(f"C{row_index}", len(sequence), 3),
                ],
                height=24,
            )
        )

    last_row = max(11, len(wells) + 11)
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="{MAIN_NS}" xmlns:r="{REL_NS}">
  <dimension ref="A1:C{last_row}"/>
  <sheetViews>
    <sheetView workbookViewId="0"/>
  </sheetViews>
  <sheetFormatPr defaultRowHeight="24"/>
  <cols>
    <col min="1" max="1" width="22" customWidth="1"/>
    <col min="2" max="2" width="40" customWidth="1"/>
    <col min="3" max="3" width="14" customWidth="1"/>
  </cols>
  <sheetData>
    {"".join(rows_xml)}
  </sheetData>
  <pageMargins left="0.7" right="0.7" top="0.75" bottom="0.75" header="0.3" footer="0.3"/>
</worksheet>"""


def _plate_title(batch: dict) -> str:
    lines = [batch["name"]]
    if batch.get("description"):
        lines.append(batch["description"])
    lines.append("Plate 1")
    return "\n".join(lines)


def _summary_sequence(well: dict) -> str:
    return (
        well.get("translated_aa_sequence")
        or well.get("source_aa_sequence")
        or well.get("protein_sequence")
        or ""
    )


def _summary_text(value: str | None) -> str:
    return value or "未设置"


def _row_xml(index: int, cells: list[str], *, height: int) -> str:
    return f'<row r="{index}" ht="{height}" customHeight="1">{"".join(cells)}</row>'


def _inline_cell(ref: str, value: str, style: int) -> str:
    return (
        f'<c r="{ref}" s="{style}" t="inlineStr"><is>'
        f'<t xml:space="preserve">{escape(str(value))}</t>'
        "</is></c>"
    )


def _number_cell(ref: str, value: int, style: int) -> str:
    return f'<c r="{ref}" s="{style}"><v>{value}</v></c>'


def _cell_ref(column: int, row: int) -> str:
    letters = ""
    while column:
        column, remainder = divmod(column - 1, 26)
        letters = chr(65 + remainder) + letters
    return f"{letters}{row}"


def _styles_xml() -> str:
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="{MAIN_NS}">
  <fonts count="2">
    <font><sz val="8"/><name val="Arial"/></font>
    <font><b/><sz val="8"/><name val="Arial"/></font>
  </fonts>
  <fills count="3">
    <fill><patternFill patternType="none"/></fill>
    <fill><patternFill patternType="gray125"/></fill>
    <fill><patternFill patternType="solid"><fgColor rgb="FFFFFF00"/><bgColor indexed="64"/></patternFill></fill>
  </fills>
  <borders count="2">
    <border><left/><right/><top/><bottom/><diagonal/></border>
    <border>
      <left style="thin"><color indexed="64"/></left>
      <right style="thin"><color indexed="64"/></right>
      <top style="thin"><color indexed="64"/></top>
      <bottom style="thin"><color indexed="64"/></bottom>
      <diagonal/>
    </border>
  </borders>
  <cellStyleXfs count="1">
    <xf numFmtId="0" fontId="0" fillId="0" borderId="0"/>
  </cellStyleXfs>
  <cellXfs count="4">
    <xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>
    <xf numFmtId="0" fontId="1" fillId="2" borderId="1" xfId="0" applyFont="1" applyFill="1" applyBorder="1" applyAlignment="1"><alignment horizontal="center" vertical="center" wrapText="1"/></xf>
    <xf numFmtId="0" fontId="1" fillId="0" borderId="1" xfId="0" applyFont="1" applyBorder="1" applyAlignment="1"><alignment horizontal="center" vertical="center" wrapText="1"/></xf>
    <xf numFmtId="0" fontId="0" fillId="0" borderId="1" xfId="0" applyBorder="1" applyAlignment="1"><alignment horizontal="center" vertical="center" wrapText="1"/></xf>
  </cellXfs>
  <cellStyles count="1">
    <cellStyle name="Normal" xfId="0" builtinId="0"/>
  </cellStyles>
</styleSheet>"""


def _content_types_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>
  <Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>
  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
  <Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
  <Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>
</Types>"""


def _root_relationships_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>
  <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>
</Relationships>"""


def _workbook_xml(sheet_name: str) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="{MAIN_NS}" xmlns:r="{REL_NS}">
  <sheets>
    <sheet name={quoteattr(sheet_name)} sheetId="1" r:id="rId1"/>
  </sheets>
</workbook>"""


def _workbook_relationships_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>"""


def _app_properties_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">
  <Application>ProteinHub</Application>
</Properties>"""


def _core_properties_xml() -> str:
    created_at = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <dc:creator>ProteinHub</dc:creator>
  <cp:lastModifiedBy>ProteinHub</cp:lastModifiedBy>
  <dcterms:created xsi:type="dcterms:W3CDTF">{created_at}</dcterms:created>
  <dcterms:modified xsi:type="dcterms:W3CDTF">{created_at}</dcterms:modified>
</cp:coreProperties>"""
