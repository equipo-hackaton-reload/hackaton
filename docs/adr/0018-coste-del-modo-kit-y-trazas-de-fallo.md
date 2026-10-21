# ADR 0018 · Modo kit sin coste, trazas de los fallos y estimación completa

- **Estado:** aceptado
- **Fecha:** 2026-10-21
- **Zona:** C (toca B: `adapters/llm/openai_compat.py`, `adapters/errors.py`, `adapters/engines`)

## Contexto

Una auditoría encontró cuatro maneras de gastar dinero sin que se viera:

1. El modo kit usaba el LLM de pago. `LLM_PROVIDER` vale `deepseek` por defecto, así que enviar el
   brief en modo kit llamaba dos veces a DeepSeek (intake y market) antes de la revisión de
   competidores.
2. El juez del kit dependía de las claves: con `TYPESAFE_API_KEY` o `DEEPSEEK_API_KEY` en el
   entorno, el kit evaluaba los 2.928 pares con Jev o DeepSeek y pasaba PlanGuard.
3. Se pagaban llamadas sin dejar `Trace`:
   - los intentos de `OpenAICompatLLM` que acababan en `LLMOutputError`;
   - las llamadas del fallback de DeepSeek dentro de `JevJudge`, que viven en `fallback.traces`, y
     el nodo `judge` solo recogía `juez.traces`;
   - lo ya pagado en un nodo que falla después: el reintento de `plan` o `write`, PlanGuard con
     `BudgetExceeded`, o la traza que cruza el tope.
4. `GET /estimate` solo contaba motores y juez. Dejaba fuera intake, market, prompts, plan,
   redacción, PlanGuard y el fallback.

Además, `ANTHROPIC_API_KEY` definida como variable de usuario de Windows la recogía `Settings`, y el
aviso «falta X en .env» confundía.

## Decisión

- **El modo kit es siempre gratis.** `wiring.build_deps` le da `FixtureLLM`, `FixtureJudge` con
  `kit_dir`, que devuelve las etiquetas humanas del kit y da la cifra canónica 25,93, y ningún
  PlanGuard, haya las claves que haya. La única excepción es pedirlo con `KIT_IA_REAL=true`
  (`settings.kit_ia_real`, por defecto `false`). El modo real se comporta igual que antes.
  Consecuencia: el kit sin opt-in solo admite el brief de Alborada, igual que la demo de fixture,
  que es el único caso que tiene datos.
- **Todo lo pagado deja traza, aunque falle.**
  - `LLMOutputError.trace` lleva los tokens y el coste de todos los intentos. Si la API falla
    después de algún intento ya cobrado, ese error también se envuelve en `LLMOutputError` con su
    traza.
  - `deps.structured` apunta la traza en el presupuesto. Si se supera, `BudgetExceeded` la lleva
    consigo.
  - Las trazas pendientes viajan en la excepción (`deps.adjuntar_trazas` y `trazas_si_falla`):
    las del reintento de plan y redacción, las de PlanGuard y las del juez.
  - `StudyRunner._drive` las recoge (`trazas_de_fallo`), las suma al checkpoint (`traces` y
    `coste_acumulado_eur`) y las guarda en el repositorio. Así aparecen en `/traces` y en el coste
    del estudio.
  - El nodo `judge` recoge las trazas del juez, de su `fallback` y de los `jueces` de un consenso
    (`trazas_del_juez`), sin duplicados.
- **La estimación cuenta todo lo que se paga** (`application/estimate.py`, todo con los precios de
  `Settings`):

  | Concepto | Cómo se estima |
  |---|---|
  | LLM de los nodos | Tokens típicos por llamada en `LLM_TOKENS` (intake 1.500/600, market 2.500/800, prompts 2.500/6.000, plan 6.000/2.500, redacción 12.000/4.000). Plan y redacción cuentan dos llamadas por su reintento |
  | Juez | Una llamada por marca y ejecución. Con Jev se añade un 25 % de llamadas repetidas en el fallback de DeepSeek (`FRACCION_FALLBACK`) |
  | PlanGuard | 10 acciones (`ACCIONES_PLAN`) |

  - `prompts` solo se cuenta en modo real, porque el kit trae su banco de preguntas.
  - `remedicion=True` quita intake y market. Lo usará `GET /studies/{id}/remeasure/estimate`.
  - En modo kit todo vale 0 salvo `KIT_IA_REAL`, y entonces los motores siguen costando 0.
  - `CostEstimate` gana `coste_llm_eur`, `coste_plan_guard_eur` y `llamadas_llm`, y `juez` admite
    `"kit"`. Los cambios son aditivos y los campos que lee la web no cambian.
  - Los tokens típicos son una cota redondeada a partir del brief de Alborada, no una medición. Se
    corregirán con las `Trace` del primer estudio real.
- **Mensaje de clave:** «falta X (ni en el entorno ni en .env)», en `MissingCredentialError` y en
  el aviso de motores desactivados.

## Consecuencias

- Ensayar la demo con claves en el entorno ya no gasta nada ni cambia la cifra.
- `coste_acumulado_eur` y `/traces` reflejan lo que de verdad se ha cobrado, también en estudios
  con estado `error`.
- La estimación de un estudio real sube, sobre todo por la redacción y por el fallback del juez.
  Es más prudente que antes, pero sigue siendo un orden de magnitud.
