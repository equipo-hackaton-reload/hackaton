# Zona E · exportación, prompts y docs (`adapters/export/`, `prompts/`, `docs/`)

## En develop
- `DocxExporter` con plantilla reproducible y `PdfExporter` con LibreOffice (503 sin `soffice`).
- Prompts v1: `intake`, `market`, `prompts`, `plan`, `write`.
- ADR 0001–0007, ejemplo Word en `docs/ejemplos/`, evaluación en `docs/evaluacion/`, `docs/plan-b.md`.

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
