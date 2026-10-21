# Arquitectura de posiq.

**posiq.** (*posicionamiento + IQ*) es un sistema agéntico que, a partir del brief de una marca, mide su visibilidad en asistentes de IA (ChatGPT, Gemini, Perplexity y Claude), la compara con sus competidores y genera una propuesta con un plan de acción por fases. La propuesta es la puerta de entrada; el producto recurrente es el **seguimiento con método**: línea base, re-medición con el mismo banco de preguntas y los mismos motores, y solo se informa de los cambios que salen del margen de error, comparados con los competidores.

Revisado contra `develop` (`1798244`, PR #37) el 2026-10-21. Lo que aún no está cableado en la API o la web se marca **PENDIENTE**.

---

## 1. Principio: capa de verdad determinista, capa de lenguaje acotada

Regla 1 del proyecto: **toda cifra la calcula código determinista de `domain/`** (puro, sin I/O, probado sin red). Los modelos de lenguaje interpretan el brief, clasifican matices de las respuestas y redactan, pero solo reciben cifras ya calculadas y devuelven siempre un modelo Pydantic validado (`LLM.structured`). El texto que llega de los motores o de la web es **dato**: viaja en el `state` y nunca se interpola en instrucciones. La propuesta es la «capa de verdad»: cada `Finding` lleva sus `evaluation_ids` y cada `Action` sus `finding_ids`, y lo valida el esquema.

```
 ┌──────────────────────────────────────────────────────────────────────────┐
 │ INTERFACES   FastAPI (cuentas Bearer, estudios, export)  ·  React + Vite │
 └───────────────────────────────────┬──────────────────────────────────────┘
 ┌───────────────────────────────────▼──────────────────────────────────────┐
 │ APLICACIÓN   Grafo LangGraph · checkpointer SQLite · 2 revisiones humanas │
 │              estimación de coste · presupuesto por estudio · trazas      │
 └──────┬─────────────────────────────┬─────────────────────────────┬───────┘
 ┌──────▼──────────────┐  ┌───────────▼────────────────┐  ┌──────────▼──────────────┐
 │ PUERTOS (ports.py)  │  │ DOMINIO PURO (domain/)      │  │ ADAPTADORES             │
 │ LLM · Engine · Judge│  │ schemas · detección · score │  │ DeepSeek / FixtureLLM   │
 │ StudyRepo · Exporter│  │ métricas · hallazgos        │  │ 4 motores reales · kit  │
 │                     │  │ stats (IC) · simulación     │  │ Jev + fallback · reglas │
 │                     │  │ escenarios · fuentes        │  │ SQLite (estudios,       │
 │                     │  │ exactitud · competidores    │  │   cuentas) · Word / PDF │
 │                     │  │ cobertura brief · serie     │  │                         │
 └─────────────────────┘  └─────────────────────────────┘  └─────────────────────────┘
```

## 2. Flujo de un estudio

```
Brief ─► intake ─► market ─► [revisión 1: competidores] ─► prompts ─► run ─► judge ─► analyze
      ─► plan (+ simulación, PlanGuard) ─► [revisión 2: plan] ─► write ─► Propuesta (Word / PDF)
Re-medición: POST /studies/{id}/remeasure ─► arranca en prompts con el brief y el mercado confirmados
```

- **intake / market:** el LLM extrae el `BriefSummary` (objetivos, ciudades, equipo, presupuesto, restricciones) y propone el mercado. Una persona confirma los competidores **antes de gastar** en motores.
- **prompts / run:** banco de preguntas por fase del embudo (descubrimiento, comparación, validación, decisión), perfil y ciudad; en modo kit, las 624 respuestas del reto (52 prompts × 4 motores × 3 repeticiones).
- **judge:** aparición y posición por reglas; matiz (tipo de mención, fuerza, sentimiento, fuentes) con Jev o su fallback (ver §3).
- **analyze:** métricas con visibilidad espontánea y asistida **siempre separadas**, Score de Citación 0–100 y 7 reglas de hallazgos con evidencias.
- **plan:** acciones por fases con palanca, responsable, plazo, entregable y KPI; validación contra presupuesto y restricciones del brief; simulación de impacto (`simulate_plan`) y PlanGuard.
- **write:** el LLM redacta (`write.v2`) y enlaza cada punto del brief con acciones o hallazgos; `domain/brief_coverage.py` valida la cobertura y el Word abre con **«2. Lo que nos habéis pedido»** (11 secciones; ADR 0013).

## 3. Capa determinista frente a no determinista (ADR 0003 y 0014)

| Capa | Qué decide | ¿Determinista? |
|---|---|---|
| **Reglas** (`domain/detection.py`) | Aparición y posición por alias. Es el suelo del score y audita al juez | Sí |
| **Jev** (TypeSafe System One, fijado a `jev-1.13`) | Tipo de mención, fuerza, sentimiento, apoyo en fuentes, con confianza por pregunta | No, acotado: versión fijada y caché por estado y versión de las preguntas |
| **Fallback LLM** (DeepSeek) | Las mismas preguntas (`domain/judge_questions.py`) cuando Jev duda (< 0,55) | No; solo actúa bajo umbral |
| **Persona** | Toda evaluación con `necesita_revision` (confianza 0,55–0,80 o discrepancia reglas–juez) | — |

Si Jev contradice a las reglas sobre la aparición, la evaluación va al fallback y sale **siempre** a revisión humana; aparición y posición siguen siendo las de las reglas, así que el juez nunca sube el score inventando una mención. *«Las reglas ponen el suelo y auditan, Jev aporta la semántica calibrada y, si discrepan, revisa un humano.»*

## 4. Rigor estadístico y seguimiento con método (ADR 0008 y 0016)

- **Intervalos:** Wilson al 95 % para tasas; bootstrap percentil (semilla fija, 2.000 réplicas) para el score; Newcombe para diferencias. Un cambio es significativo si su IC excluye 0. Alborada (kit): **Score 25,9 [21,6–30,1]**, 8.ª de 10; 6 de los 7 hallazgos admiten contraste y los 6 son significativos.
- **Límites declarados:** las repeticiones de un prompt no son independientes (remuestreando prompts, el IC pasa a [19,7–31,8] y la caída del embudo deja de ser significativa); los IC no cubren el error del juez; el kit es sintético.
- **Serie temporal** (`domain/tracking.py`): cada punto se compara con el anterior solo si coinciden metodología, versión del score, huella SHA-256 del banco y conjunto de motores; si cambia el modelo de un motor, se avisa. Se informa de score, aparición por motor, puesto y diferencia frente a la media de competidores, y el resumen solo recoge lo significativo. El kit medido dos veces da exactamente «Sin cambios fuera del margen de error».
- **Indicadores adelantados:** cuota de citas a la web propia (Alborada 5,85 %), presencia en las 5 fuentes más citadas (74,1 %), inexactitudes (0) y afirmaciones a revisar por la clínica (21).

## 5. Cifras canónicas de la demo (golden)

| Cifra | Valor | Dónde se fija |
|---|---|---|
| Score de Citación de Alborada (etiquetas del kit) | **25,93** (25,87 con juez solo por reglas; 25,9 con un decimal) | `tests/golden/test_demo_canonico.py` |
| Puesto | **8.ª de 10** (líder: Grupo Hospitalario Valdecruz, 66,46) | ídem |
| Proyección del plan (9 acciones, 4 fases, 42 semanas, 22.000 €) | **25,9 → 30,8** [27,8–34,0] | ídem y `tests/e2e/test_demo_canonica_api.py` |
| Visibilidad espontánea / asistida | 38,8 % (93/240) / 100 % (108/108) | `compute_metrics` sobre el kit |

## 6. Cuentas, costes y trazas

- **Cuentas (ADR 0015):** registro con código de verificación, contraseñas con scrypt, tokens Bearer opacos (solo su sha256 en la base, 7 días). Cada estudio pertenece a quien lo crea; uno ajeno responde 404. La re-medición hereda el propietario: es la base de la suscripción por cliente. Sin proveedor de correo todavía (el código va al log).
- **Trazas:** toda llamada externa registra nodo, modelo, versión de prompt, tokens, coste y duración en una `Trace`, también las que fallan (ADR 0018), y cuentan contra `BUDGET_EUR_MAX` (5 € por defecto).
- **Coste por medición** (`application/estimate.py`, `GET /estimate`): modo kit, **0 €** siempre. Modo real con Jev, tamaño del kit (624 llamadas): **≈ 11,25 € estimados** (motores ≈ 10,56 €, juez ≈ 0,67 €, LLM de los nodos ≈ 0,02 €); una re-medición, ≈ 11,25 € (no repite intake ni market). Son órdenes de magnitud con precios provisionales de `settings.py` sin contrastar y superan el tope por defecto de 5 €. **Coste real de una medición: PENDIENTE** (no se ha hecho aún ninguna medición real completa).

## 7. Modelo de negocio que soporta la arquitectura

| Producto | Qué lo hace posible |
|---|---|
| **Estudio inicial** (diagnóstico + propuesta) | Grafo completo, revisiones humanas, Word con cobertura del brief |
| **Suscripción de re-mediciones** (trimestral) | `remeasure`, serie con comparabilidad, solo cambios fuera del margen, cuentas por cliente |
| **Vigilancia de lo que la IA dice de la marca** | `domain/accuracy.py` (afirmaciones verificadas contra el brief, lista de riesgo regulatorio) |
| **Plan re-priorizado** | `domain/scenarios.py` (preajustes mínimo viable, equilibrado y completo, re-simulados) |

Precio de la suscripción: **PENDIENTE** (el coste variable por medición aún es una estimación).

## 8. Decisiones (ADR)

| ADR | Decisión |
|---|---|
| 0001 | `domain/` puro, sin I/O |
| 0002 | `study_id` en todo resultado (multiestudio, re-medición) |
| 0003 | Juez Jev con fallback LLM y umbrales en código |
| 0004 | Word con docxtpl reproducible; prompts versionados `<nodo>.vN.md` |
| 0005 | LangGraph con `interrupt()`, checkpointer SQLite y modo fixture |
| 0006 | 4 motores reales con búsqueda web, caché y presupuesto |
| 0007 | Simulación con rendimientos decrecientes y PlanGuard |
| 0008 | Rigor estadístico: Wilson, bootstrap, Newcombe, consenso del juez |
| 0009 | Escenarios del plan y recubrimiento mínimo |
| 0010 | Mapa de fuentes del sector y oportunidades |
| 0011 | Exactitud de marca con verificación conservadora |
| 0012 | Competidores declarados frente a los que pone la IA |
| 0013 | Trazabilidad brief → propuesta |
| 0014 | Capa determinista frente a no determinista |
| 0015 | Cuentas de usuario y propiedad de los estudios |
| 0016 | Seguimiento con método: serie temporal |
| 0018 | Modo kit sin coste, trazas de los fallos y estimación completa |

## 9. Estado de integración y limitaciones

- **En `domain/` y con golden, PENDIENTE de cablear en la API y la web:** intervalos (`rigor` sale `null` en `GET /studies/{id}`), escenarios, mapa de fuentes, exactitud, brecha de competidores y serie de seguimiento. `ConsensusJudge` existe pero `build_judge` no lo usa (multiplicaría por N el coste del juez).
- **Datos del kit sintéticos:** ilustran el método, no el mercado real; el origen se declara en la portada del Word.
- **No determinismo de los motores:** se mide con repeticiones y se acota con IC; no se prometen posiciones.
- **Publicidad sanitaria:** el plan no promete resultados ni hace comparativas denigratorias; cada contenido necesita revisión médica y jurídica del cliente.
- **PDF:** depende de LibreOffice; sin él la API responde 503 y se entrega el `.docx`.
