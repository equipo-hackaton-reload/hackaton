"""Compila docs/deck.md a docs/deck.pdf en formato diapositivas 16:9 con Chrome o Edge headless."""

import os
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MD_PATH = ROOT / "docs" / "deck.md"
HTML_PATH = ROOT / "docs" / "deck.html"
PDF_PATH = ROOT / "docs" / "deck.pdf"


def parse_slides(md_text: str) -> list[dict[str, str]]:
    slides = []
    # Dividir por "## Slide "
    raw_slides = re.split(r"\n(?=## Slide \d+:)", md_text)
    for raw in raw_slides:
        raw = raw.strip()
        if not raw:
            continue
        lines = raw.splitlines()
        header = lines[0].replace("## ", "").strip()
        body_lines = lines[1:]

        # Extraer título si existe
        title = ""
        content_lines = []
        notes = ""
        in_notes = False

        for line in body_lines:
            if line.startswith("### Título"):
                continue
            if line.startswith("**") and not title and not in_notes:
                title = line.strip("*").strip()
                continue
            if line.startswith("> **Guion del presentador"):
                in_notes = True
                notes += line + "\n"
                continue
            if in_notes:
                notes += line + "\n"
            else:
                content_lines.append(line)

        slides.append(
            {
                "header": header,
                "title": title or header,
                "content": "\n".join(content_lines).strip(),
                "notes": notes.strip(),
            }
        )
    return slides


def format_markdown(text: str) -> str:
    html = []
    in_list = False
    for line in text.splitlines():
        line = line.strip()
        if not line:
            if in_list:
                html.append("</ul>")
                in_list = False
            continue
        if line.startswith("- "):
            if not in_list:
                html.append("<ul>")
                in_list = True
            item_text = line[2:]
            html.append(f"<li>{item_text}</li>")
        elif line.startswith("### "):
            if in_list:
                html.append("</ul>")
                in_list = False
            html.append(f"<h4>{line[4:]}</h4>")
        else:
            if in_list:
                html.append("</ul>")
                in_list = False
            html.append(f"<p>{line}</p>")
    if in_list:
        html.append("</ul>")

    res = "\n".join(html)
    res = re.sub(r"\*\*(.*?)\*\*", r"<strong>\1</strong>", res)
    res = re.sub(r"\*(.*?)\*", r"<em>\1</em>", res)
    res = re.sub(r"`(.*?)`", r"<code>\1</code>", res)
    return res


def main() -> None:
    if not MD_PATH.is_file():
        raise FileNotFoundError(f"No existe {MD_PATH}")

    content = MD_PATH.read_text(encoding="utf-8")
    slides = parse_slides(content)

    slide_html_blocks = []
    for i, s in enumerate(slides, start=1):
        formatted_content = format_markdown(s["content"])
        notes_clean = (
            s["notes"]
            .replace("> **Guion del presentador (Demo):**", "")
            .replace(">", "")
            .replace("*", "")
            .strip()
        )
        notes_html = (
            f'<div class="speaker-notes"><strong>Guion Demo:</strong> {notes_clean}</div>'
            if notes_clean
            else ""
        )
        block = f"""
    <div class="slide">
        <div class="slide-header">
            <span class="slide-badge">{s["header"]}</span>
            <span class="brand-tag">posiq. · Hackathon GEO</span>
        </div>
        <h2 class="slide-title">{s["title"]}</h2>
        <div class="slide-body">
            {formatted_content}
        </div>
        {notes_html}
        <div class="slide-footer">
            <span>posiq. — Sistema Agéntico de Visibilidad GEO</span>
            <span>Diapositiva {i} de {len(slides)}</span>
        </div>
    </div>
"""
        slide_html_blocks.append(block)

    css = """
  @page {
    size: 297mm 210mm; /* A4 horizontal / landscape */
    margin: 0;
  }
  * {
    box-sizing: border-box;
  }
  body {
    margin: 0;
    padding: 0;
    font-family:
      -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
    color: #1e293b;
    background: #f8fafc;
  }
  .slide {
    width: 297mm;
    height: 210mm;
    page-break-after: always;
    padding: 16mm 20mm;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    background: #ffffff;
    position: relative;
    overflow: hidden;
  }
  .slide-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    border-bottom: 2px solid #e2e8f0;
    padding-bottom: 8px;
    margin-bottom: 12px;
  }
  .slide-badge {
    background: #1f3a5f;
    color: #ffffff;
    font-size: 11pt;
    font-weight: 700;
    padding: 4px 12px;
    border-radius: 4px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }
  .brand-tag {
    color: #64748b;
    font-size: 10pt;
    font-weight: 600;
  }
  .slide-title {
    color: #0f172a;
    font-size: 19pt;
    line-height: 1.25;
    margin: 0 0 14px 0;
    font-weight: 800;
  }
  .slide-body {
    flex: 1;
    font-size: 11pt;
    line-height: 1.45;
    color: #334155;
  }
  .slide-body h4 {
    color: #1f3a5f;
    font-size: 12pt;
    margin: 8px 0 4px 0;
    font-weight: 700;
  }
  .slide-body p {
    margin: 4px 0;
  }
  .slide-body ul {
    margin: 4px 0;
    padding-left: 24px;
  }
  .slide-body li {
    margin-bottom: 5px;
  }
  .speaker-notes {
    background: #f1f5f9;
    border-left: 4px solid #3b82f6;
    padding: 8px 12px;
    font-size: 9pt;
    color: #475569;
    border-radius: 0 4px 4px 0;
    margin-top: 10px;
    line-height: 1.35;
  }
  .slide-footer {
    display: flex;
    justify-content: space-between;
    align-items: center;
    border-top: 1px solid #e2e8f0;
    padding-top: 8px;
    margin-top: 12px;
    font-size: 9pt;
    color: #94a3b8;
  }
  code {
    background: #e2e8f0;
    padding: 2px 5px;
    border-radius: 3px;
    font-family: Consolas, monospace;
    font-size: 10pt;
  }
"""

    html = f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<title>Deck de Presentación posiq.</title>
<style>{css}</style>
</head>
<body>
{"".join(slide_html_blocks)}
</body>
</html>"""

    HTML_PATH.write_text(html, encoding="utf-8")
    print(f"HTML de deck generado en {HTML_PATH}")

    browsers = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    ]
    browser = next((b for b in browsers if os.path.isfile(b)), None)
    if not browser:
        print("No se encontró navegador para compilar a PDF.")
        return

    cmd = [
        browser,
        "--headless",
        "--disable-gpu",
        f"--print-to-pdf={PDF_PATH}",
        str(HTML_PATH),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode == 0 and PDF_PATH.is_file():
        print(f"Deck PDF generado exitosamente: {PDF_PATH} ({PDF_PATH.stat().st_size} bytes)")
    else:
        print(f"Error generando PDF: {res.stderr}")


if __name__ == "__main__":
    main()
