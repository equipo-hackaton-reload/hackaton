# Guion de la demo (≤ 3 min)

Recorrido de las 5 pantallas con el brief de **Clínica Alborada Visión** en **modo kit** y
`LLM_PROVIDER=fixture`. Sin red y sin claves. Si algo falla: [plan B](../plan-b.md).

Ensayo del 2026-10-21, sobre `develop` en `59745d5`, con Playwright headless (Chrome, 1280×800).
Hubo 3 pasadas y las dos que se cronometraron dieron lo mismo. Las cifras de abajo son las que se ven
en pantalla.

## Checklist previa (5 min antes)

- [ ] Puertos libres: API en **8000** y web en **5173**, los de por defecto (`netstat -ano | grep -E ":8000|:5173"`).
- [ ] `.env` de la raíz copiado de `.env.example` con **`LLM_PROVIDER=fixture`** (por defecto vale `deepseek`).
- [ ] `apps/web/.env.local` copiado de `apps/web/.env.example` con **`VITE_USE_MOCKS=false`** y
      `VITE_API_URL=http://localhost:8000`. Con `VITE_USE_MOCKS=true` la web usa MSW, y eso ya es el plan B.
- [ ] Borrar `posiq.db` (y `posiq.db-*`) de la raíz para que en «Mediciones de esta marca» no salgan los estudios del ensayo.
- [ ] Arranque, en dos terminales:

  ```sh
  # raíz del repo
  uv sync
  LLM_PROVIDER=fixture uv run uvicorn posiq.interfaces.api.main:app --port 8000
  # apps/web
  npm ci
  npm run dev            # http://localhost:5173
  ```

- [ ] `curl http://localhost:8000/health` → `{"status":"ok"}`. CORS acepta cualquier `localhost:<puerto>` (regex).
- [ ] Haz una pasada completa en seco y vuelve a `/`. Deja el navegador a pantalla completa y el
      Word de `docs/ejemplos/propuesta_alborada_ejemplo.docx` abierto en otra pestaña por si acaso.
- [ ] No pulses **Descargar PDF**: sin LibreOffice la API devuelve 503 y la web muestra un error.

## Tiempos medidos (lo que tarda el sistema)

| Paso | Tiempo |
|---|---|
| 1 → 2 · Analizar → aparece el mercado propuesto | 3,4 s |
| 2 → 3 · Confirmar y medir → diagnóstico listo | 6,4–6,9 s |
| 3 → 4 · Revisar el plan → plan | 0,2 s |
| 4 → 5 · Aprobar plan → propuesta | 3,4–3,9 s |
| Descargar Word (45 KB) | 0,4 s |
| **Total sin hablar** | **15,0 s** |

La web sondea cada 3 s, así que cada espera es de 1 o 2 ciclos. El resto de los 3 minutos es narración.

## Clic a clic

### 1 · Nuevo estudio (0:00–0:25)

- **Clic:** «Subir .md o .txt» → `data/kit/01_Briefings/Brief_de_ejemplo_Clinica_Alborada.md`
  (o «Usar el brief de ejemplo», que es el mismo). Modo **Kit** ya marcado → **Analizar**.
- **Decir:** «Partimos del brief de una clínica oftalmológica de Madrid y Barcelona. posiq. quiere
  saber cuánto la recomiendan ChatGPT, Gemini, Perplexity y Claude frente a su competencia. En modo
  kit usamos las 624 respuestas del reto, así que no gastamos nada».

### 2 · Competidores (0:25–0:50) · espera 3 s

- **Se ve:** «10 marcas · 4 foco · 5 contexto · 1 líder». El líder es Grupo Hospitalario Valdecruz.
- **Decir:** «El agente lee el brief y propone el mercado. Antes de medir, una persona lo revisa:
  puede añadir o quitar marcas y cambiar el líder. Es la primera revisión humana del grafo».
- **Clic:** **Confirmar y medir**.

### 3 · Diagnóstico (0:50–1:40) · espera 7 s

- **Se ve:** Score de Citación **25,87** de 100 · **8.ª de 10** · a **39,97 puntos** de Valdecruz (65,84).
  Desglose: aparición 11,62 · posición 4,72 · fuerza 3,88 · calidad de fuente 5,65.
  Por motor: ChatGPT 11,38 · Gemini 38,46 · Perplexity 43,96 · Claude 9,68. Hay 7 hallazgos.
- **Decir:** «Alborada saca 25,9 sobre 100 y es octava de diez. Los motores la conocen: cuando la
  pregunta la nombra aparece el 100 % de las veces, pero cuando no la nombra solo el 39 %. Claude la
  menciona en el 15 % de las respuestas y Perplexity en el 65 %. En Barcelona aparece en el 4 %. Toda
  cifra la calcula código, no el LLM, y cada hallazgo enlaza a sus evaluaciones».
- **Clic opcional:** «Ver evidencias» en un hallazgo, para enseñar la respuesta del motor y sus fuentes.
- **Ojo:** en pantalla sale **25,87** (API en fixture, juez por reglas). La cifra canónica es
  **25,93**, que en la deck es 25,9. Con un decimal las dos son 25,9, así que se **dice «25,9»**.
- **Clic:** **Revisar el plan**.

### 4 · Plan (1:40–2:20) · instantáneo

- **Se ve:** 4 fases en 42 semanas · 9 acciones · presupuesto estimado **22.000 €** (brief:
  18.000–27.000 €). Objetivo del Score: 25,9 → 35,0. Cada acción lleva «La justifican…» con sus hallazgos.
- **Decir:** «El plan respeta el presupuesto y las restricciones del brief (publicidad sanitaria, sin
  comparativas). Cada acción se apoya en hallazgos concretos y la persona puede editarla. Es la
  segunda revisión humana. Una simulación conservadora proyecta el Score de **25,9 a 30,8** al
  terminar la fase 3, en un rango de 27,8 a 34,0».
- **Ojo:** la **simulación no aparece en la web** (la API la devuelve, pero la web no la pinta) y la
  **calidad del plan tampoco**: en fixture, sin claves de juez, vale `null`. La proyección se cuenta
  de palabra o con la diapositiva de la deck. En fixture la API calcula 25,87 → 30,71 (27,72–33,88).
- **Clic:** **Aprobar plan**.

### 5 · Propuesta (2:20–2:55) · espera 4 s

- **Se ve:** el resumen ejecutivo, las limitaciones, el contexto (7 hallazgos · 9 acciones · 2 riesgos),
  coste **0,00 €** y las trazas: 5 llamadas (intake, market, judge, plan, write) con modelo y prompt.
- **Decir:** «La propuesta va dirigida al comité. Cada llamada a un modelo queda trazada con su
  versión de prompt, sus tokens y su coste. En modo kit el coste es cero».
- **Clic:** **Descargar Word** → `propuesta-<id>.docx`. Si da tiempo, ábrelo y enseña la tabla de
  objetivos y el Score 25,9.
- **Ojo:** el resumen empieza con «DEMO SIN IA: textos y plan de ejemplo». Es el texto del
  `FixtureLLM`, así que conviene anticiparlo: «en la demo el redactor es un fixture; en real lo
  escribe DeepSeek con las mismas cifras».

### Cierre (2:55–3:00)

«Brief, mercado, medición, plan y propuesta en menos de 20 segundos de máquina, con dos revisiones
humanas y todas las cifras trazables a su evidencia».

## Cuándo saltar al plan B

Ver [docs/plan-b.md](../plan-b.md).

| Síntoma en directo | Salto |
|---|---|
| `/health` no responde, o la API arranca con `LLM_PROVIDER=deepseek` y falla | Reiniciar con `LLM_PROVIDER=fixture`. Si sigue fallando, `uv run python scripts/demo_kit.py` |
| Una pantalla se queda en «Leyendo el brief», «Midiendo» o «Cargando estudio» más de 15 s | **F5**: la web relee el estado y sigue. Si a los 30 s no ha avanzado, pasar a la web con mocks |
| La web no arranca o da error de CORS | `VITE_USE_MOCKS=true` en `apps/web/.env.local` y `npm run dev` (MSW con las cifras del dominio, 25,93) |
| La descarga del Word falla | `GET /studies/{id}/export?formato=docx` o `docs/ejemplos/propuesta_alborada_ejemplo.docx` |
| Preguntan por la calidad del plan | `uv run python scripts/evaluate_system.py` e informe de `docs/evaluacion/` |
