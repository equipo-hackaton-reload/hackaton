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
- Conceptos para la presentación y los entregables: índice `docs/conceptos/README.md` (orden de
  lectura y regla de oro kit sintético frente a real), `score-de-citacion.md`, `kit-vs-real.md`,
  `rigor-y-seguimiento.md`, `capas-determinista-y-no-determinista.md`, `propuesta-geo.md`,
  `docs/propuesta-valor.md` y `docs/glosario.md`. Términos unificados (el juez decide fuerza,
  tipo de mención, sentimiento y apoyo en fuentes; aparición y posición, siempre las reglas; tres
  jueces posibles y mismo juez en toda la serie, PENDIENTE en la comparabilidad). Al cambiar una
  cifra golden o el estado de una PR, actualizar estos documentos.

## En develop desde la PR #23 (`feature/E-entregable`)
- `docs/arquitectura.md` (+ `.html` y `.pdf` con `scripts/build_architecture_pdf.py`): capa de verdad
  determinista, capa determinista/no determinista (ADR 0014), rigor (25,9 [21,6–30,1]), seguimiento
  con método (ADR 0016), cuentas (ADR 0015), coste por medición estimado (≈ 11,25 € en real, 0 € en
  kit; coste real PENDIENTE), modelo de negocio (estudio inicial + suscripción) y ADR 0001–0018.
- `docs/deck.md` (+ `.html` y `.pdf` con `scripts/build_deck_pdf.py`): 10 diapositivas con las cifras
  de los golden (25,93; 8.ª de 10; 25,9 → 30,8 [27,8–34,0]); sin marcadores `[SCORE]`.
- `docs/revision-word.md`: revisión del Word para el comité de la clínica (11 secciones).
- Textos del fixture de Alborada y del golden de exportación más cuidados para el cliente (el
  resumen ejecutivo no promete cumplir la normativa: plan dentro de las restricciones del brief y
  revisión médica y jurídica de cada contenido antes de publicarse); el
  ejemplo `docs/ejemplos/propuesta_alborada_ejemplo.docx` se regenera con
  `uv run pytest tests/golden/test_export.py`.
- `.github/CODEOWNERS` con los handles reales de las cinco zonas.

- `plan.v2.md` (desde zona C, `feature/C-diferencial-grafo`): misma instrucción que v1, con la
  cabecera alineada con lo que manda el nodo (`brief`, `metricas`, `hallazgos`,
  `diferencia_anterior`, `market` y, en el reintento, `plan_anterior` y `violaciones`). `plan.v1`
  queda publicado sin uso. Regla nueva en `prompts/README.md`: las claves que manda el nodo son las
  de la cabecera; lo comprueba `tests/application/test_prompt_state.py`.

## Word con el diferencial (`feature/E-word-diferencial`, entregable 3)
- `adapters/export/diferencial.py`: `DatosDiferencial` (rigor, competidores, oportunidades_fuente,
  exactitud, mitigaciones, escenarios, simulacion, auditoria_web) con `del_estado(values)`, que
  ignora claves ausentes o que no validan (la exportación nunca falla por un bloque). Los
  formateadores pasan a `adapters/export/formato.py` (siguen importables desde `docx`).
- `DocxExporter.render(..., diferencial=None)` y `PdfExporter` igual; el puerto `Exporter` no
  cambia (parámetro opcional fuera del Protocol). Sin `diferencial`, cada bloque dice «No se
  calculó en este estudio.».
- `SECCIONES` pasa a 13: margen de error en «4. Diagnóstico» (score con IC, aparición por motor de
  los 4 motores con margen ± p. p. y score por motor con IC); «Contraste estadístico» en la ficha de
  cada hallazgo; competidores declarados frente a los de la IA y mapa de fuentes y oportunidades en
  «5. Competencia»; «7. Exactitud y lectura técnica de la marca» (resumen, hasta 12 afirmaciones a
  revisar sin repetir, mitigaciones; auditoría web solo si el estado trae `auditoria_web`);
  «10. Escenarios y simulación del plan» (proyecciones con supuestos, advertencia literal del
  dominio); «11. Seguimiento con método» sustituye a «Medición y seguimiento» (oferta del servicio,
  línea base con IC y posición, cambios fuera del margen solo en re-mediciones, KPI y cadencia de
  la propuesta).
- Estudios kit: «Caso sintético del reto: datos ficticios» en portada y pie.
- Golden de exportación sobre el plan canónico (9 acciones) y el diferencial calculado con las
  mismas funciones que los nodos; ejemplo regenerado. Prompt `write` sin cambios (no sube versión).
- **Para la Mitad B (docs):** `docs/revision-word.md` y `docs/arquitectura.md` hablan de 11
  secciones y de «Medición y seguimiento»; ahora son 13 y «Seguimiento con método».

## Coordinación con zona D
- La tarea web de simulación y re-medición actualizó `CHANGELOG.md` y este estado con autorización
  explícita; no modifica exportadores, prompts ni cifras de la propuesta.

## Falta
- Coste real de una medición y precio de la suscripción (PENDIENTE de la primera medición real).
- Serie de seguimiento (varias mediciones) en el Word: hoy solo la línea base y los deltas
  significativos de una re-medición.
- PDF del ejemplo: en esta máquina no hay LibreOffice (el test de PDF se salta).

## Siguiente tarea
- Ensayo general de la demo con la deck y el guion (`docs/deck.md`, `docs/demo/guion.md`,
  `docs/plan-b.md`).

## No tocar
- Cifras en plantillas: solo formatear lo que llega de `domain/`.
- `schemas.py` y `ports.py` sin PR de `contract-change`.
