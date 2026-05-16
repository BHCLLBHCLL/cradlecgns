#!/usr/bin/env python3
"""Convert Markdown to PDF using fpdf2 (no system deps)."""

import re
import sys
from pathlib import Path

try:
    from fpdf import FPDF
except ImportError:
    print("pip install fpdf2")
    sys.exit(1)


def _get_font_path():
    import os
    for p in [
        os.path.expandvars(r"%SystemRoot%\Fonts\msyh.ttc"),
        os.path.expandvars(r"%SystemRoot%\Fonts\msyh.ttf"),
        os.path.expandvars(r"%SystemRoot%\Fonts\simsun.ttc"),
    ]:
        if os.path.exists(p):
            return p
    return None


class PDF(FPDF):
    def __init__(self):
        super().__init__()
        self.add_page()
        self.set_auto_page_break(auto=True, margin=15)
        self.set_margins(15, 15, 15)
        fp = _get_font_path()
        self._font = "Uni" if fp else "Helvetica"
        if fp:
            try:
                self.add_font("Uni", "", fp)
                self.add_font("Uni", "B", fp)
            except Exception:
                self._font = "Helvetica"
        self.set_font(self._font, "", 10)

    def md_line(self, line):
        line = line.rstrip()
        if not line:
            self.ln(4)
            return
        # Headers
        m = re.match(r"^(#{1,4})\s+(.+)$", line)
        if m:
            n, t = len(m.group(1)), m.group(2).strip()
            self.set_font(self._font, "B", 14 - n)
            self.multi_cell(0, 6, t)
            self.set_font(self._font, "", 10)
            self.ln(2)
            return
        # Horizontal rule
        if re.match(r"^[-*_]{3,}\s*$", line):
            self.ln(2)
            return
        # Code block
        if line.startswith("```"):
            self.set_font("Courier" if self._font == "Helvetica" else self._font, "", 9)
            return
        # List item
        if re.match(r"^[-*]\s+", line) or re.match(r"^\d+\.\s+", line):
            self.set_font(self._font, "", 10)
            txt = ("  " + line)[:500]  # truncate very long lines
            self.multi_cell(0, 5, txt)
            return
        # Table row (simple)
        if "|" in line and not line.strip().startswith("|---"):
            cells = [c.strip() for c in line.split("|")[1:-1]]
            if cells:
                w = 190 / len(cells)
                for c in cells:
                    self.cell(w, 5, (c[:24] + "..") if len(c) > 26 else c, border=1)
                self.ln()
            return
        # Normal paragraph
        self.multi_cell(0, 5, line)
        self.ln(1)


def main():
    if len(sys.argv) < 2:
        print("Usage: python md2pdf_simple.py <file.md> [output.pdf]")
        sys.exit(1)
    md_path = Path(sys.argv[1])
    pdf_path = Path(sys.argv[2]) if len(sys.argv) > 2 else md_path.with_suffix(".pdf")
    if not md_path.exists():
        print(f"Not found: {md_path}")
        sys.exit(1)

    text = md_path.read_text(encoding="utf-8", errors="replace")
    pdf = PDF()
    in_code = False
    for line in text.splitlines():
        if line.strip().startswith("```"):
            in_code = not in_code
            if in_code:
                pdf.set_font("Courier", "", 9)
            else:
                pdf.set_font(pdf._font, "", 10)
            continue
        if in_code:
            pdf.multi_cell(0, 5, line)
            continue
        pdf.md_line(line)

    pdf.output(str(pdf_path))
    print(f"Created: {pdf_path}")


if __name__ == "__main__":
    main()
