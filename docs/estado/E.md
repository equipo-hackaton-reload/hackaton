# Zona E · exportación, prompts y docs (`adapters/export/`, `prompts/`, `docs/`)

## En develop
- `DocxExporter` con plantilla reproducible y `PdfExporter` con LibreOffice (503 sin `soffice`).
- Prompts v1: `intake`, `market`, `prompts`, `plan`, `write`.
- ADR 0001–0007, ejemplo Word en `docs/ejemplos/`, evaluación en `docs/evaluacion/`, `docs/plan-b.md`.
- Trazabilidad brief → propuesta (zona A, ADR 0013): prompt `write.v2.md` (enlaza cada punto del
  brief con acciones o hallazgos en `cobertura_brief`) y sección del Word «2. Lo que nos habéis
  pedido» antes del contexto: listas literales del brief y tabla punto → dónde se trata, con
  «Pendiente». `SECCIONES` pasa a 11 (las diez del doc 06 + esta); plantilla regenerada.
- Prompt `intake.v2.md` (el nodo `intake` lo usa; v1 se conserva): extrae además
  `posicionamiento_deseado` y `atributos_deseados`, literales o resumen fiel del brief y vacíos si
  el brief no los trae. `FixtureLLM` devuelve para Alborada su propuesta de valor y sus tres
  «Diferenciales», solo si aparecen tal cual en el brief recibido (si no, vacíos).

## Coordinación con zona D
- La tarea web de simulación y re-medición actualizó `CHANGELOG.md` y este estado con autorización
  explícita; no modifica exportadores, prompts ni cifras de la propuesta.

## Falta
- Documento de arquitectura y presentación.
- Sección de simulación del plan en el Word cuando C la incluya en la propuesta.
- `CODEOWNERS` sigue con `@TODO`.

## Siguiente tarea
- `feature/E-presentacion`: guion de la demo apoyado en `docs/plan-b.md`.

## No tocar
- Cifras en plantillas: solo formatear lo que llega de `domain/`.
