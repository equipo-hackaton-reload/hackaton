# Calibración del juez

Esta guía explica cómo medir el juez (Jev y el fallback LLM) contra las 133 filas etiquetadas por
personas de `data/kit/02_Datos/caso_oftalmologia/muestra_evaluada.csv`. Cada ejecución guarda aquí
un informe con el nombre `<fecha>_<juez>.md`.

> **Estado: PENDIENTE.** Todavía no se ha hecho la calibración real con Jev ni con el fallback
> porque faltan las claves.

## 1. Variables necesarias

Defínelas en `.env`, en la raíz del repo. El fichero está en `.gitignore`: nunca lo subas.

| Variable | Para qué | Obligatoria |
|---|---|---|
| `TYPESAFE_API_KEY` | Juez Jev | Sí, para calibrar Jev |
| `JEV_MODEL` | Modelo de Jev (por defecto `jev-1.13`, fijado; `jev-latest` es un alias móvil) | No |
| `DEEPSEEK_API_KEY` | Juez de fallback (LLM) | Sí, para calibrar el fallback |
| `DEEPSEEK_MODEL`, `DEEPSEEK_BASE_URL` | Modelo y endpoint del fallback (por defecto `deepseek-chat` en `https://api.deepseek.com`) | No |
| `JUDGE_CONFIDENCE_ACCEPT`, `JUDGE_CONFIDENCE_FALLBACK` | Umbrales de la política (0,80 y 0,55) | No |
| `BUDGET_EUR_MAX` | Tope de gasto del estudio (5 €) | No |

Si falta una clave, el juez se construye igual, pero al evaluar lanza `MissingCredentialError` con el
nombre de la variable que falta.

## 2. Comandos

```sh
uv sync

# Jev, en bruto y sin fallback (requiere TYPESAFE_API_KEY)
uv run python scripts/calibrate_judge.py --judge jev --no-cache

# Fallback LLM (requiere DEEPSEEK_API_KEY)
uv run python scripts/calibrate_judge.py --judge llm --no-cache

# Test golden: se salta solo si no hay TYPESAFE_API_KEY
uv run pytest tests/golden/test_judge_calibration.py -v -s
```

`--no-cache` obliga a hacer llamadas nuevas. Sin esa opción, una segunda ejecución reutiliza las
respuestas guardadas en `.cache/` y sale gratis.

Antes de ejecutar, el script muestra el coste estimado. Para Jev, las 133 llamadas cuestan unos
0,005 € con aproximadamente 1.000 tokens de entrada por llamada.

## 3. Umbrales que debe pasar

| Métrica | Umbral | Dónde |
|---|---|---|
| Acuerdo en `aparece` | ≥ 0,90 | test golden |
| Acuerdo en `tipo_mencion` (filas donde la persona ve la marca) | ≥ 0,80 | test golden |
| MAE de fuerza en la reserva | ≤ 0,5 | objetivo interno del doc 07 |

**Si no se alcanzan, no se bajan los umbrales.** Se mira qué preguntas fallan (la matriz de tipo
de mención y la tabla de discrepancias del informe) y se proponen cambios en las instrucciones o
los criterios de `src/posiq/domain/judge_questions.py`. Ese fichero es de la Zona A: se proponen
en un PR suyo, no se cambian desde la Zona B.

## 4. Qué guardar

- El informe `docs/calibracion/<fecha>_<juez>.md`, uno por juez (Jev y LLM), versionado en git.
- En el PR o en el CHANGELOG:
  - el acuerdo total y el de la reserva;
  - cuántas filas se aceptan, cuántas van a revisión y cuántas a fallback con los umbrales
    actuales;
  - el coste real (tokens y €);
  - la versión de las preguntas (`QUESTIONS_VERSION`) y el modelo usado.
- Si se cambian preguntas o umbrales, una nueva calibración con fecha. Las anteriores no se
  borran.

## 5. Cómo se mide

- **Juez en bruto:** se llama a `ajudge`, sin política ni fallback, para medir lo que acierta el juez
  por sí solo.
- **Muestra:** se separa por `Ejecucion_ID`. Las 10 primeras ejecuciones son de calibración y las 5
  últimas, de reserva (doc 07). Las etiquetas humanas nunca se envían al juez.
- **Qué se compara:** la aparición y la posición las fija la detección por reglas, así que el
  acuerdo en `aparece` mide sobre todo las reglas (1,0 en la muestra). Tipo de mención, fuerza
  (exacta y ±1) y sentimiento se comparan solo en las filas donde la persona ve la marca.
