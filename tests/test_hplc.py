from xml.etree import ElementTree

import pytest

from proteinhub.domain.errors import DomainError
from proteinhub.infrastructure.hplc.chromatogram import (
    HPLCBlock,
    plate_position_from_filename,
    read_hplc_vial_fc_csv,
    render_hplc_chromatogram_svg,
)


def test_plate_position_from_filename_extracts_embedded_unique_position() -> None:
    assert (
        plate_position_from_filename("20260711 183616D1F-A1-result.dx_DAD1A.CSV")
        == "A01"
    )

    with pytest.raises(DomainError, match="multiple well positions"):
        plate_position_from_filename("run-A1-B2.dx_DAD1A.CSV")


def test_read_hplc_vial_fc_csv_allows_zero_width_fraction_windows() -> None:
    vial_fc_csv = (
        "样品 名称,20260712 014301D1F-D10\n"
        "编号,位置,开始时间 (min),结束时间 (min),体积 (mL)\n"
        "1,P1-M3,1.500,1.660,0.11\n"
        "2,P1-M4,2.694,2.866,0.12\n"
        "3,P1-M5,3.490,3.763,0.18\n"
        "4,P1-M6,3.767,3.767,0.00\n"
        "\"参比检测器 = DAD1 (起始延迟时间: 0.096 min, 结束延迟时间: 0.096 min)\"\n"
    ).encode("utf-8")

    blocks_by_sample = read_hplc_vial_fc_csv(("vial_fc.csv", "text/csv", vial_fc_csv))

    blocks = blocks_by_sample["20260712 014301D1F-D10"]
    assert [block.position for block in blocks] == ["P1-M3", "P1-M4", "P1-M5", "P1-M6"]
    assert blocks[-1].start == blocks[-1].end == 3.767
    assert blocks[-1].volume == 0.0


def test_render_hplc_chromatogram_svg_skips_tiny_fraction_windows() -> None:
    svg = render_hplc_chromatogram_svg(
        sample_key="20260712 014301D1F-D10",
        plate_position="D10",
        points=[
            (0.0, -2.9),
            (0.5, -2.7),
            (1.0, -2.5),
            (1.5, -2.4),
            (2.0, -2.6),
            (2.5, -2.5),
            (3.0, -2.3),
            (3.5, -2.2),
            (4.0, -2.4),
        ],
        blocks=[
            HPLCBlock(index=1, position="P1-M3", start=1.500, end=1.660, volume=0.11),
            HPLCBlock(index=2, position="P1-M4", start=2.694, end=2.866, volume=0.12),
            HPLCBlock(index=3, position="P1-M5", start=3.490, end=3.763, volume=0.18),
            HPLCBlock(index=4, position="P1-M6", start=3.767, end=3.767, volume=0.00),
            HPLCBlock(index=5, position="P1-M7", start=3.780, end=3.789, volume=0.00),
        ],
    ).decode("utf-8")

    root = ElementTree.fromstring(svg)
    block_titles = []
    for element in root.iter():
        title = next((child for child in element if child.tag.endswith("title")), None)
        if title is not None and title.text:
            block_titles.append(title.text)

    assert any("P1-M3 1.500-1.660" in title for title in block_titles)
    assert not any("P1-M6" in title for title in block_titles)
    assert not any("P1-M7" in title for title in block_titles)
    assert "HPLC D10" in svg
