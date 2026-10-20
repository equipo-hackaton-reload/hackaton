# ADR 0004 · Exportación de la propuesta y prompts versionados

- **Estado:** propuesto
- **Fecha:** 2026-10-21
- **Zona:** E

## Contexto

La propuesta tiene que poder entregarse tal cual a un cliente (doc 06), en Word o PDF, con las diez
secciones del formato y con la marca de la agencia que la firma. Ninguna cifra puede inventarse:
todas salen del dominio. Los nodos LLM necesitan prompts versionados, que no mezclen instrucciones
con datos y cuya versión quede en la `Trace`.

## Decisión

**Puerto.** `Exporter.render(proposal, *, formato: "docx" | "pdf", marca_agencia=None) -> bytes`.
`AgencyBrandKit` (nombre, logo opcional, color primario y pie) vive en `adapters/export/branding.py`,
no en `schemas.py`: es presentación, no dominio. `ports.py` lo importa solo bajo `TYPE_CHECKING`.

**Word.** `DocxExporter` rellena con docxtpl la plantilla `templates/propuesta.docx`, que genera
`scripts/build_docx_template.py` con python-docx. Un test comprueba que la plantilla del repo
coincide con la que genera el script. `build_context` solo formatea: redondeo, porcentaje, separador
decimal español y etiquetas. La plantilla no hace aritmética. `None` se muestra como «s. d.», nunca
como 0. Se renderiza con `autoescape`, porque el texto viene de un LLM.

**PDF.** `PdfExporter` genera el docx y lo convierte con `soffice --headless --convert-to pdf`.
Cada conversión usa un perfil temporal propio. Si no hay LibreOffice, lanza `SofficeNotFoundError`
con instrucciones; el test de PDF se salta.

**Prompts.** Un `.md` por nodo con cabecera YAML (`name`, `version`, `schema`, `state`). El texto
nunca tiene llaves de interpolación: los datos van en `state`. `PromptSet` vive en
`posiq.prompts` porque `schemas.py` está cerrado. `load_prompt(nombre)` valida la cabecera y
`version_tag` da el valor de `Trace.prompt_version`.

## Consecuencias

- La cifra de cada hallazgo se imprime tal cual, junto a su `origen_cifra`. `Finding` no declara
  unidad (fracción, puntos o recuento) y adivinarla sería inventar. Lo legible lo aporta su
  `descripcion`.
- La propuesta solo trae ids de marca. Salvo la marca foco, cuyo nombre está en `contexto.marca`,
  los nombres se muestran a partir del id y pierden las tildes. Un `contract-change` futuro podría
  añadir `Market` o los nombres a `Proposal`.
- El PDF depende de un binario externo. En CI (Ubuntu) se puede instalar `libreoffice-writer`.
- `posiq.prompts` usa PyYAML, que hoy llega como dependencia transitiva de LangGraph. Conviene
  declararla explícitamente en `pyproject.toml`.
