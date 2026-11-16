"""Render the executive summary and verify its three-page PDF layout."""
import csv
import json
from pathlib import Path
import re

import markdown
from pypdf import PdfReader
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

OUT = Path(__file__).resolve().parent


def main():
    source = (OUT / "RESUMEN_EJECUTIVO.md").read_text(encoding="utf-8")
    with (OUT / "results.csv").open(newline="", encoding="utf-8") as stream:
        measurements = [row for row in csv.DictReader(stream) if row["ok"] == "True"]
    historical = []
    if not any(row["tier"] in ("simple", "medium") for row in measurements):
        loc = {}
        for line in (OUT / "HISTORICO_SIMPLE_MEDIO.md").read_text(encoding="utf-8").splitlines():
            if line.startswith(("| simple |", "| medium |")):
                cells = [part.strip() for part in line.strip("|").split("|")]
                loc[(cells[0], cells[1])] = cells[3]
        for line in (OUT / "RESULTADOS_REALES.md").read_text(encoding="utf-8").splitlines():
            if line.startswith(("| simple |", "| medium |")):
                cells = [part.strip() for part in line.strip("|").split("|")]
                historical.append(dict(tier=cells[0], tool=cells[1], preview_s=cells[3],
                                       deploy_s=cells[4], destroy_s=cells[6], loc=loc[(cells[0], cells[1])]))
    measurements = historical + measurements
    expected_rows = []
    for row in measurements:
        expected_rows.append((row["tier"], row["tool"],
                              *[f"{float(row[field]):.2f}".replace(".", ",")
                                for field in ("preview_s", "deploy_s", "destroy_s")], row["loc"]))
    actual_rows = []
    for line in source.splitlines():
        if line.startswith(("| Simple |", "| Medio |", "| Intensivo |")):
            cells = [part.strip() for part in line.strip("|").split("|")]
            tier = {"Simple": "simple", "Medio": "medium", "Intensivo": "intensive"}[cells[0]]
            actual_rows.append((tier, cells[1].casefold(), *cells[2:]))
    if actual_rows != expected_rows:
        raise RuntimeError("Executive summary table differs from CSV measurements or historical report")
    sections = source.split("<!-- pagebreak -->")
    if len(sections) != 3:
        raise RuntimeError("Expected three explicitly separated summary sections")
    body = "\n".join("<section>" + markdown.markdown(part, extensions=["tables"]) + "</section>"
                     for part in sections)
    css = """
@page {
  size: A4;
  margin: 16mm 18mm 17mm;
  @bottom-center {
    content: "IaC en AWS | Resumen ejecutivo | " counter(page) " / " counter(pages);
    font: 8pt Arial, sans-serif;
    color: #526171;
  }
}
* { box-sizing: border-box; }
body { margin: 0; color: #172b3a; font: 10.4pt/1.34 "Segoe UI", Arial, sans-serif; }
section + section { break-before: page; }
h1 { color: #123b50; font-size: 22pt; margin: 0 0 4pt; line-height: 1.05; }
h2 { font-size: 13.5pt; margin: 0 0 9pt; font-weight: 600; }
h3 { color: #123b50; font-size: 11.5pt; margin: 11pt 0 5pt; border-bottom: 0.5pt solid #becdd4; padding-bottom: 3pt; }
h1, h2, h3 { break-after: avoid; }
p { margin: 0 0 6pt; orphans: 2; widows: 2; }
strong { font-weight: 650; }
code { font: 9pt Consolas, monospace; overflow-wrap: anywhere; }
a { color: #174e6a; text-decoration: none; }
table { width: 100%; border-collapse: collapse; font-size: 9.2pt; margin: 8pt 0; break-inside: avoid; }
th { text-align: left; background: #eaf0f3; font-weight: 650; }
th, td { border-bottom: 0.5pt solid #cad5db; padding: 4pt 5pt; vertical-align: top; }
section:last-child h3:last-of-type ~ p { font-size: 9pt; line-height: 1.23; margin-bottom: 4pt; }
"""
    html = '<!doctype html><html lang="es"><meta charset="utf-8"><title>Resumen Ejecutivo - IaC en AWS</title>'
    html += f"<style>{css}</style><body>{body}</body></html>"
    html_path = OUT / "RESUMEN_EJECUTIVO.html"
    pdf_path = OUT / "RESUMEN_EJECUTIVO.pdf"
    html_path.write_text(html, encoding="utf-8")
    for name, file in (("Body", "segoeui.ttf"), ("Body-Bold", "segoeuib.ttf"), ("Code", "consola.ttf")):
        pdfmetrics.registerFont(TTFont(name, str(Path("C:/Windows/Fonts") / file)))
    pdfmetrics.registerFontFamily("Body", normal="Body", bold="Body-Bold", italic="Body", boldItalic="Body-Bold")
    normal = ParagraphStyle("body", fontName="Body", fontSize=10.4, leading=13.6,
                            textColor=colors.HexColor("#172b3a"), spaceAfter=6, alignment=TA_LEFT)
    heading = {1: ParagraphStyle("title", parent=normal, fontName="Body-Bold", fontSize=21, leading=24,
                                spaceAfter=5, keepWithNext=True),
               2: ParagraphStyle("subtitle", parent=normal, fontName="Body-Bold", fontSize=13, leading=16,
                                spaceAfter=8, keepWithNext=True),
               3: ParagraphStyle("section", parent=normal, fontName="Body-Bold", fontSize=11.5, leading=14,
                                spaceBefore=8, spaceAfter=5, keepWithNext=True)}
    cell = ParagraphStyle("cell", parent=normal, fontSize=9, leading=11.2, spaceAfter=0)
    reference = ParagraphStyle("reference", parent=normal, fontSize=9, leading=11.1, spaceAfter=4)

    def inline(text):
        value = markdown.markdown(text).removeprefix("<p>").removesuffix("</p>")
        return value.replace("<code>", '<font name="Code" size="9">').replace("</code>", "</font>")

    story = []
    width = A4[0] - 36 * mm
    for section_no, section in enumerate(sections):
        if section_no:
            story.append(PageBreak())
        lines = section.strip().splitlines()
        cursor = 0
        references = False
        while cursor < len(lines):
            line = lines[cursor]
            if not line.strip():
                cursor += 1
                continue
            if line.startswith("#"):
                level = len(line) - len(line.lstrip("#"))
                title = line[level:].strip()
                references = title == "Referencias Bibliográficas"
                story.append(Paragraph(inline(title), heading[level]))
                cursor += 1
            elif line.startswith("|"):
                rows = []
                while cursor < len(lines) and lines[cursor].startswith("|"):
                    cells = [part.strip() for part in lines[cursor].strip("|").split("|")]
                    if not all(re.fullmatch(r":?-+:?", part) for part in cells):
                        rows.append([Paragraph(inline(part), cell) for part in cells])
                    cursor += 1
                fractions = [0.18, 0.30, 0.52] if len(rows[0]) == 3 else [0.13, 0.23, 0.16, 0.16, 0.16, 0.16]
                table = Table(rows, colWidths=[width * fraction for fraction in fractions], repeatRows=1)
                table.setStyle(TableStyle([
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eaf0f3")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LINEBELOW", (0, 0), (-1, -1), 0.4, colors.HexColor("#cad5db")),
                    ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                    ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ]))
                story.extend([table, Spacer(1, 7)])
            else:
                paragraph = []
                while cursor < len(lines) and lines[cursor].strip() and not lines[cursor].startswith(("#", "|")):
                    paragraph.append(lines[cursor])
                    cursor += 1
                story.append(Paragraph(inline("\n".join(paragraph)), reference if references else normal))

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont("Body", 8)
        canvas.setFillColor(colors.HexColor("#526171"))
        canvas.drawCentredString(A4[0] / 2, 10 * mm, f"IaC en AWS | Resumen ejecutivo | {doc.page} / 3")
        canvas.restoreState()

    document = SimpleDocTemplate(str(pdf_path), pagesize=A4, rightMargin=18 * mm, leftMargin=18 * mm,
                                 topMargin=16 * mm, bottomMargin=17 * mm,
                                 title="Resumen Ejecutivo - IaC en AWS",
                                 author="Joaquin Ballara, Facundo Dutra y Mauro Machado")
    document.build(story, onFirstPage=footer, onLaterPages=footer)
    reader = PdfReader(pdf_path)
    texts = [page.extract_text() for page in reader.pages]
    expected = ["Resumen Ejecutivo", "Método Y Resultados", "Conclusión Y Recomendación"]
    if len(reader.pages) != 3 or any(title not in text for title, text in zip(expected, texts)):
        raise RuntimeError(f"Unexpected pagination: {len(reader.pages)} pages; check section overflow")
    evidence = dict(pages=len(reader.pages), page_format="A4", source="RESUMEN_EJECUTIVO.md",
                    html=html_path.name, renderer="ReportLab",
                    pdf=pdf_path.name, words_by_page=[len(re.findall(r"\S+", text)) for text in texts],
                    expected_sections=expected, csv_rows_verified=len(measurements) - len(historical),
                    total_measurement_rows_verified=len(actual_rows),
                    historical_report_rows_verified=len(historical),
                    new_csv_rows_verified=len(measurements) - len(historical),
                    external_pdf_links=sum(1 for page in reader.pages for annotation in page.get("/Annots", [])
                                           if annotation.get_object().get("/A", {}).get("/URI", "").startswith("https://")),
                    markdown_version=markdown.__version__)
    (OUT / "executive-summary-validation.json").write_text(json.dumps(evidence, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(evidence, indent=2))


if __name__ == "__main__":
    main()
