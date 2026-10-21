# ADR 0012 · Trazabilidad brief → propuesta

- **Estado:** aceptado
- **Fecha:** 2026-10-21
- **Zona:** A (`domain/brief_coverage.py`; contrato `Encargo` y `PuntoBrief` en `domain/schemas.py`)

## Contexto

La propuesta es la capa de verdad: en ella se ve si se ha entendido lo que pedía la empresa. Hasta
ahora el código solo comprobaba las restricciones y el tope de presupuesto. Nada comprobaba que los
objetivos, las ciudades, los servicios prioritarios, los públicos o los competidores declarados del
brief se trataran en algún sitio.

## Decisión

La IA redacta y propone enlaces; el código copia el brief y decide la cobertura.

- **Encargo literal.** `Proposal.encargo` copia del `BriefSummary`, sin LLM, los objetivos, las
  restricciones, los servicios prioritarios, las ciudades, los públicos, los competidores
  declarados y el presupuesto.
- **Puntos con id estable.** Cada elemento del brief es un `PuntoBrief`: `objetivo-1`,
  `restriccion-2`, `servicio-1`, `ciudad-2`, `publico-3`, `competidor-1`, `presupuesto`. Se numeran
  desde 1 en el orden del brief.
- **Enlaces del redactor.** `ProposalDraft.cobertura_brief` va de id de punto a ids de acciones o
  hallazgos. `evaluar_cobertura` separa los ids en acciones y hallazgos y descarta los que no
  existen (lo anota en `motivo`).
- **Reglas de cobertura:**
  - Objetivos, servicios, ciudades, públicos y competidores: cubiertos si queda al menos un id
    válido.
  - Restricciones: cubiertas si TODAS las acciones las declaran (`ignora_restriccion`, la misma
    regla que `validate_plan_against_brief`) y el plan no se declara incumplidor. Los enlaces del
    redactor no cuentan aquí: la prueba es el plan.
  - Presupuesto: cubierto si el presupuesto estimado del plan no supera el máximo del brief.
- **Lo que falta.** `carencias(encargo)` da una línea por punto pendiente. El nodo `write` reintenta
  una vez con esas carencias. Si siguen faltando, las declara en `contexto.limitaciones`.
- **El esquema lo garantiza.** Un punto `cubierto` sin enlaces solo vale para restricciones y
  presupuesto. `Proposal` rechaza un encargo con ids que no existen en el plan o en los hallazgos.

## Consecuencias

- La cobertura dice que un punto se trata, no que se trate bien. La calidad sigue siendo cosa de la
  revisión humana del plan y de PlanGuard.
- El encargo solo trae lo que trae el `BriefSummary`. `posicionamiento_deseado` y
  `atributos_deseados` existen, pero aún no son puntos de cobertura: los usará la comparación
  identidad deseada frente a percibida.
- Las propuestas antiguas tienen `encargo = None` y siguen siendo válidas.
