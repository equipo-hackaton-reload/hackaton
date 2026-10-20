"""Regenera la plantilla Word de la propuesta: `uv run python scripts/build_docx_template.py`."""

from posiq.adapters.export.template import build_template

if __name__ == "__main__":
    print(build_template())
