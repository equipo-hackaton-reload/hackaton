# Zona E · exportación, prompts y docs (`adapters/export/`, `prompts/`, `docs/`)

## En develop
- `DocxExporter` con plantilla reproducible y `PdfExporter` con LibreOffice (503 sin `soffice`).
- Prompts v1: `intake`, `market`, `prompts`, `plan`, `write`.
- ADR 0001–0007, ejemplo Word en `docs/ejemplos/`, evaluación en `docs/evaluacion/`, `docs/plan-b.md`.
- Trazabilidad brief → propuesta (zona A, ADR 0013): prompt `write.v2.md` (enlaza cada punto del
  brief con acciones o hallazgos en `cobertura_brief`) y sección del Word «2. Lo que nos habéis
  pedido» antes del contexto: listas literales del brief y tabla punto → dónde se trata, con
  «Pendiente». `SECCIONES` pasa a 11 (las diez del doc 06 + esta); plantilla regenerada.

## En la PR #23 (`feature/E-entregable`, rebasada sobre `1798244`)
- `docs/arquitectura.md` (+ `.html` y `.pdf` con `scripts/build_architecture_pdf.py`): capa de verdad
  determinista, capa determinista/no determinista (ADR 0014), rigor (25,9 [21,6–30,1]), seguimiento
  con método (ADR 0016), cuentas (ADR 0015), coste por medición estimado (≈ 11,25 € en real, 0 € en
  kit; coste real PENDIENTE), modelo de negocio (estudio inicial + suscripción) y ADR 0001–0018.
- `docs/deck.md` (+ `.html` y `.pdf` con `scripts/build_deck_pdf.py`): 10 diapositivas con las cifras
  de los golden (25,93; 8.ª de 10; 25,9 → 30,8 [27,8–34,0]); sin marcadores `[SCORE]`.
- `docs/revision-word.md`: revisión del Word para el comité de la clínica (11 secciones).
- Textos del fixture de Alborada y del golden de exportación más cuidados para el cliente; el
  ejemplo `docs/ejemplos/propuesta_alborada_ejemplo.docx` se regenera con
  `uv run pytest tests/golden/test_export.py`.
- `.github/CODEOWNERS` con los handles reales de las cinco zonas.

## Coordinación con zona D
- La tarea web de simulación y re-medición actualizó `CHANGELOG.md` y este estado con autorización
  explícita; no modifica exportadores, prompts ni cifras de la propuesta.

## Falta
- Coste real de una medición y precio de la suscripción (PENDIENTE de la primera medición real).
- Rigor, escenarios, serie de seguimiento y exactitud en el Word cuando C los cablee en el estado.
- Sección de simulación del plan en el Word cuando la propuesta la incluya en `schemas.py`
  (`contract-change`).

## Siguiente tarea
- Ensayo general de la demo con la deck y el guion (`docs/deck.md`, `docs/demo/guion.md`,
  `docs/plan-b.md`).

## No tocar
- Cifras en plantillas: solo formatear lo que llega de `domain/`.
- `schemas.py` y `ports.py` sin PR de `contract-change`.
