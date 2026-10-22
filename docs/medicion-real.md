# Medición real: pasos para esta tarde

Guía corta para pasar del kit (caso sintético) a una medición con los motores de verdad sin pasar
de **5 €**. Ensayada en seco por `tests/e2e/test_real_en_seco_api.py`: el mismo recorrido por la
API con clientes falsos (LLM, 4 motores, juez y PlanGuard), con trazas de coste, el tope que corta
y cero red.

> **Regla de oro.** El kit (Clínica Alborada Visión) es un caso **sintético**: Alborada no existe y
> **no se mide en modo real**. Las cifras canónicas del kit (25,93; 8.ª de 10; 25,9 → 30,8; 7
> hallazgos; 9 acciones) siguen saliendo solo del modo kit, que no gasta nada.

## 0. Antes de nada

- Elige una **marca real** (existe, tiene web y competidores reconocibles) y escribe su brief con
  la estructura de `data/kit/01_Briefings/Brief_de_ejemplo_Clinica_Alborada.md`: marca, sector,
  ciudades, servicios, públicos, competidores declarados, restricciones, presupuesto y objetivos.
- Un responsable del gasto. Una sola persona lanza las llamadas de pago.

## 1. Crear `.env`

```sh
cp .env.example .env
```

`.env` no se sube nunca (está en `.gitignore`). Cambia solo esto:

| Variable | Valor | Por qué |
|---|---|---|
| `LLM_PROVIDER` | `deepseek` | LLM de los nodos (intake, mercado, prompts, plan, redacción) |
| `DEEPSEEK_API_KEY` | la clave | LLM y fallback del juez |
| `TYPESAFE_API_KEY` | la clave | Juez Jev |
| `JEV_MODEL` | `jev-1.13` (no `jev-latest`) | Mismo juez en toda la serie |
| `OPENAI_API_KEY`, `GEMINI_API_KEY`, `PERPLEXITY_API_KEY` | las claves | Motores |
| `ANTHROPIC_API_KEY` | **vacía** de entrada | Ver el paso 3 |
| `BUDGET_EUR_MAX` | `5` | Tope por estudio |
| `REAL_MAX_PROMPTS` | `20` | El banco completo (52) no cabe en 5 € |
| `KIT_IA_REAL` | `false` | El kit sigue sin coste |
| `WEB_AUDIT` | `off` | Auditoría técnica web (ADR 0019); en kit, siempre fixture |
| `AUTH_DEV_CODES` | sin fijar | Con el LLM real los códigos van al log del servidor, no a la respuesta |

Con `LLM_PROVIDER=deepseek` no hay cuenta demo ni `codigo_dev`: al registrarte, el código de
verificación aparece en el log del servidor.

## 2. El mismo juez en toda la serie

La línea base y cada re-medición tienen que usar **el mismo juez y la misma versión**
(`JUDGE_PROVIDER`, `JEV_MODEL`, umbrales `JUDGE_CONFIDENCE_*`). Si cambias cualquiera, el delta
mezcla el cambio de la marca con el del juez y no vale. No toques el `.env` entre la línea base y
la re-medición salvo para reponer claves. `CACHE_ENABLED=true`: repetir una llamada idéntica no
vuelve a pagar.

## 3. Estimación previa con tope de 5 €

Arranca la API (puerto propio) y pide la estimación **antes** de crear el estudio:

```sh
python -m uv run uvicorn posiq.interfaces.api.main:app --port 8141
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8141/estimate?modo=real&n_prompts=20&n_motores=3&repeticiones=3"
```

Orden de magnitud con los precios de `.env.example` (Jev + DeepSeek):

| Prompts | Motores | Llamadas | Estimado |
|---|---|---|---|
| 52 | 4 | 624 | ~10,6 € (no cabe) |
| 20 | 4 | 240 | ~4,3 € |
| 20 | 3 (sin Claude) | 180 | ~3,3 € |
| 10 | 4 | 120 | ~2,2 € |

Coste medio estimado por llamada: ChatGPT ~0,010 €, Gemini ~0,032 €, Perplexity ~0,005 €, Claude
~0,021 €. **Claude es el motor caro de verdad**: con búsqueda web (`ANTHROPIC_ENGINE_MAX_SEARCHES`)
los resultados de búsqueda entran como tokens de entrada a 4 $/M y la llamada real puede costar
varias veces lo estimado. Por eso:

- Empieza **sin** `ANTHROPIC_API_KEY`. Añádela solo si el smoke (paso 4) muestra un coste por
  llamada que cabe.
- Si la añades, baja `REAL_MAX_PROMPTS` (10-12) y `ANTHROPIC_ENGINE_MAX_SEARCHES` (2-3).

**Cómo corta el tope.** El presupuesto se mira antes de cada llamada. Con hasta 8 llamadas en
vuelo, el gasto puede pasar el tope en unas pocas llamadas; al pasarlo, el estudio queda en
`error`, sin propuesta, y lo gastado queda en sus trazas. Un estudio cortado no da resultado:
**que la estimación quede holgada por debajo de 5 €** (≤ 4 €).

## 4. Smoke de los motores (céntimos)

```sh
python -m uv run python scripts/smoke_engines.py -n 1 --repeticiones 1
python -m uv run python scripts/smoke_engines.py -n 1 --repeticiones 1 --motores Claude  # solo si vas a usarlo
```

El smoke usa prompts del kit: solo comprueba conexión y coste; sus respuestas **no son una
medición** y no se usan en ningún material. Comprueba por motor: responde, trae fuentes y su **coste real por llamada**. Multiplica por
`REAL_MAX_PROMPTS × 3 repeticiones` y súmalo: si pasa de ~4 €, recorta prompts o quita un motor.

## 5. Línea base

1. Registro y login (código de verificación en el log del servidor).
2. `POST /studies` con el brief de la marca real y `"modo": "real"`.
3. Revisión de competidores: corrige el mercado que propone el LLM (foco, líder, competidores
   reales) y aprueba. A partir de aquí empieza el gasto de motores.
4. Revisión del plan y aprobación.
5. Comprueba en `GET /studies/{id}`: `estado = completado`, `coste_acumulado_eur` ≤ 5 y
   `errores` vacío. `GET /studies/{id}/traces` lista cada llamada con modelo, versión de prompt,
   tokens y coste; la suma es el coste del estudio.
6. Exporta el Word (`GET /studies/{id}/export?formato=docx`). Apunta el `study_id`.

## 6. Re-medición

Mismo `.env`, mismo juez. La re-medición reutiliza el banco de prompts y el mercado confirmado:

```sh
curl -H "Authorization: Bearer $TOKEN" http://localhost:8141/studies/$ID/remeasure/estimate
curl -X POST -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"confirmado": true, "coste_estimado_eur": <el de la estimación>}' \
  http://localhost:8141/studies/$ID/remeasure
```

Aprueba el plan nuevo. `metrics_delta` en `GET /studies/{nuevo}` y `GET /brands/{id}/serie` dan
la evolución. Re-medir el mismo día mide **repetibilidad** (variación de los motores), no el
efecto del plan: dilo así en la presentación.

## Comprobaciones finales

- Ninguna clave en el repo: `git status` no muestra `.env`.
- Gasto total de la tarde = suma de `coste_acumulado_eur` de los estudios + smoke.
- Las cifras del modo real no se mezclan con las del kit en ningún material.
