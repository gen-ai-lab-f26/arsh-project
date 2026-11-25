"""Turn a pitch deck into plain text, slide by slide.

Reads .pptx (slide text, tables and speaker notes), .pdf and plain text.
No model is involved: this is the text the checker and the baseline both see.
"""

from __future__ import annotations

from pathlib import Path


def read_deck(path: str | Path) -> str:
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix == ".pptx":
        return _read_pptx(path)
    if suffix == ".pdf":
        return _read_pdf(path)
    if suffix in {".txt", ".md"}:
        return path.read_text()
    raise ValueError(f"Can't read {suffix or 'this'} files. Use .pptx, .pdf or .txt.")


def _read_pptx(path: Path) -> str:
    from pptx import Presentation

    parts = []
    for number, slide in enumerate(Presentation(str(path)).slides, start=1):
        lines = [f"--- Slide {number} ---"]
        for shape in slide.shapes:
            lines.extend(_shape_text(shape))
        if slide.has_notes_slide:
            notes = slide.notes_slide.notes_text_frame
            if notes is not None and notes.text.strip():
                lines.append(f"[Speaker notes] {notes.text.strip()}")
        parts.append("\n".join(lines))
    return "\n\n".join(parts)


def _chart_text(chart) -> list[str]:
    """The numbers behind a chart, one line per series."""
    lines = []
    try:
        for plot in chart.plots:
            labels = [str(c) for c in plot.categories]
            for series in plot.series:
                points = ", ".join(f"{l}: {v}" for l, v in zip(labels, series.values))
                lines.append(f"[Chart] {series.name}: {points}")
    except Exception:  # an unusual chart type; say so instead of failing the deck
        lines.append("[Chart: its data could not be read]")
    return lines


def _shape_text(shape) -> list[str]:
    lines = []
    if getattr(shape, "has_chart", False) and shape.has_chart:
        lines.extend(_chart_text(shape.chart))
    elif shape.shape_type == 13:  # a picture; any numbers in it are not read
        lines.append("[Picture: not read]")
    elif getattr(shape, "has_table", False) and shape.has_table:
        for row in shape.table.rows:
            lines.append(" | ".join(cell.text.strip() for cell in row.cells))
    elif getattr(shape, "has_text_frame", False) and shape.has_text_frame:
        text = shape.text_frame.text.strip()
        if text:
            lines.append(text)
    elif hasattr(shape, "shapes"):  # a group of shapes
        for inner in shape.shapes:
            lines.extend(_shape_text(inner))
    return lines


def _read_pdf(path: Path) -> str:
    from pypdf import PdfReader

    parts = []
    for number, page in enumerate(PdfReader(str(path)).pages, start=1):
        text = (page.extract_text() or "").strip()
        parts.append(f"--- Page {number} ---\n{text}")
    return "\n\n".join(parts)
