"""Compila docs/arquitectura.md a docs/arquitectura.pdf usando Chrome o Edge headless."""

import os
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MD_PATH = ROOT / "docs" / "arquitectura.md"
HTML_PATH = ROOT / "docs" / "arquitectura.html"
PDF_PATH = ROOT / "docs" / "arquitectura.pdf"


def md_to_html(md_text: str) -> str:
    html = []
    in_table = False
    table_rows: list[str] = []
    in_code = False
    code_lines: list[str] = []

    for line in md_text.splitlines():
        line_str = line.rstrip()
        if line_str.startswith("```"):
            if in_code:
                in_code = False
                html.append("<pre><code>" + "\n".join(code_lines) + "</code></pre>")
                code_lines = []
            else:
                in_code = True
                code_lines = []
            continue
        if in_code:
            code_lines.append(
                line_str.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            )
            continue

        if line_str.startswith("|"):
            if not in_table:
                in_table = True
                table_rows = []
            table_rows.append(line_str)
            continue
        elif in_table:
            in_table = False
            t_html = ["<table>"]
            is_header = True
            for r in table_rows:
                if "---" in r:
                    is_header = False
                    continue
                cells = [c.strip() for c in r.split("|")[1:-1]]
                tag = "th" if is_header else "td"
                t_html.append("<tr>" + "".join(f"<{tag}>{c}</{tag}>" for c in cells) + "</tr>")
            t_html.append("</table>")
            html.append("\n".join(t_html))

        if not line_str:
            continue
        if line_str.startswith("# "):
            html.append(f"<h1>{line_str[2:]}</h1>")
        elif line_str.startswith("## "):
            html.append(f"<h2>{line_str[3:]}</h2>")
        elif line_str.startswith("### "):
            html.append(f"<h3>{line_str[4:]}</h3>")
        elif line_str.startswith("- "):
            html.append(f"<li>{line_str[2:]}</li>")
        elif line_str.startswith("---"):
            html.append("<hr>")
        else:
            html.append(f"<p>{line_str}</p>")

    if in_table:
        t_html = ["<table>"]
        is_header = True
        for r in table_rows:
            if "---" in r:
                is_header = False
                continue
            cells = [c.strip() for c in r.split("|")[1:-1]]
            tag = "th" if is_header else "td"
            t_html.append("<tr>" + "".join(f"<{tag}>{c}</{tag}>" for c in cells) + "</tr>")
        t_html.append("</table>")
        html.append("\n".join(t_html))

    body = "\n".join(html)
    body = re.sub(r"\*\*(.*?)\*\*", r"<strong>\1</strong>", body)
    body = re.sub(r"\*(.*?)\*", r"<em>\1</em>", body)
    body = re.sub(r"`(.*?)`", r"<code>\1</code>", body)
    return body


def main() -> None:
    if not MD_PATH.is_file():
        raise FileNotFoundError(f"No existe {MD_PATH}")

    content = MD_PATH.read_text(encoding="utf-8")
    body = md_to_html(content)

    css = """
  @page {
    size: A4;
    margin: 1.4cm 1.4cm;
  }
  body {
    font-family:
      -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
    font-size: 8.5pt;
    line-height: 1.35;
    color: #1a202c;
  }
  h1 {
    font-size: 14pt;
    color: #1f3a5f;
    margin-top: 0;
    margin-bottom: 4px;
    border-bottom: 2px solid #1f3a5f;
    padding-bottom: 3px;
  }
  h2 {
    font-size: 10.5pt;
    color: #1f3a5f;
    margin-top: 10px;
    margin-bottom: 4px;
    border-bottom: 1px solid #cbd5e1;
    padding-bottom: 2px;
  }
  h3 {
    font-size: 9pt;
    color: #2d3748;
    margin-top: 6px;
    margin-bottom: 2px;
  }
  p {
    margin-top: 3px;
    margin-bottom: 4px;
    text-align: justify;
  }
  hr {
    border: none;
    border-top: 1px solid #e2e8f0;
    margin: 6px 0;
  }
  li {
    margin-bottom: 2px;
  }
  pre {
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 4px;
    padding: 6px;
    font-size: 7.2pt;
    line-height: 1.2;
    margin: 4px 0;
    overflow-x: auto;
  }
  code {
    font-family: Consolas, 'Courier New', monospace;
    font-size: 7.8pt;
    background: #f1f5f9;
    padding: 1px 3px;
    border-radius: 3px;
  }
  table {
    width: 100%;
    border-collapse: collapse;
    font-size: 7.5pt;
    margin: 5px 0;
  }
  th, td {
    border: 1px solid #cbd5e1;
    padding: 3px 5px;
    text-align: left;
    vertical-align: top;
  }
  th {
    background-color: #f1f5f9;
    color: #1f3a5f;
    font-weight: 600;
  }
  tr:nth-child(even) {
    background-color: #f8fafc;
  }
"""

    html = f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<title>Arquitectura posiq.</title>
<style>{css}</style>
</head>
<body>
{body}
</body>
</html>"""

    HTML_PATH.write_text(html, encoding="utf-8")
    print(f"HTML generado en {HTML_PATH}")

    browsers = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    ]
    browser = next((b for b in browsers if os.path.isfile(b)), None)
    if not browser:
        print("No se encontró Chrome ni Edge para generar el PDF.")
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
        print(f"PDF generado exitosamente: {PDF_PATH} ({PDF_PATH.stat().st_size} bytes)")
    else:
        print(f"Error generando PDF: {res.stderr}")


if __name__ == "__main__":
    main()
