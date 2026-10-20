# Guía de APIs de LLM y costes

> **Recordatorio:** el reto se puede resolver **completo con los datos del kit, sin llamar a ninguna API**. Conectar APIs reales es un **extra (Nivel 3)**. Esta guía os sirve si decidís hacerlo.
>
> El kit **no incluye claves de API**. Los nombres de modelos, precios y parámetros cambian con frecuencia: **consultad siempre la documentación oficial vigente** del proveedor antes de implementar.

---

## 1. Los cuatro motores del estudio y cómo activar la búsqueda web

Un asistente real **busca en la web** cuando responde. Para que un estudio de visibilidad sea representativo, hay que **activar la búsqueda web** (o *grounding*) en cada API.

| Motor | Proveedor / API | Cómo se activa la búsqueda web | Dónde encontrar las fuentes citadas | Documentación |
|---|---|---|---|---|
| **ChatGPT** | OpenAI · API de respuestas (*Responses API*) | Herramienta `web_search` en la lista de herramientas de la petición | Anotaciones de tipo cita (`url_citation`) dentro del contenido del mensaje | platform.openai.com/docs |
| **Gemini** | Google · API Gemini (SDK `google-genai`) | Herramienta *Grounding with Google Search* (`google_search`) en la configuración | `grounding_metadata` del candidato: fragmentos (`grounding_chunks`) con la URL de cada fuente | ai.google.dev/gemini-api/docs |
| **Perplexity** | Perplexity · API *Sonar* (compatible con el formato de chat completions) | **Busca por defecto** en todas las peticiones con los modelos Sonar | Campos de citas y resultados de búsqueda de la respuesta (`citations` / `search_results`) | docs.perplexity.ai |
| **Claude** | Anthropic · API de mensajes (*Messages API*) | Herramienta de servidor `web_search` declarada en la lista de herramientas (con un máximo de usos por petición) | Bloques de resultado de búsqueda (`web_search_tool_result`) en el contenido de la respuesta | platform.claude.com/docs |

Detalles que conviene saber:

- **Fuentes como dominios**: para el estudio basta con quedarse con el **dominio** de cada URL citada (p. ej. `diariosalud.example`) y clasificarlo por tipo (ver catálogo en el kit).
- **Respuestas largas con búsqueda**: algunas APIs devuelven la respuesta en varios pasos (por ejemplo, Claude puede pedir **continuar** cuando una búsqueda larga se pausa). Revisad en la documentación cómo gestionar esos casos.
- **Sin búsqueda**: a veces el modelo decide no buscar. Es normal; registradlo (en el kit, `Fuentes citadas` vacío).

## 2. Buenas prácticas de uso

| Tema | Recomendación |
|---|---|
| **Claves** | Variables de entorno o gestor de secretos. **Nunca** en el repositorio ni en el código |
| **Reintentos** | Espera creciente (*exponential backoff*) ante errores de red, límites de uso y errores 5xx |
| **Límites de uso** | Respetad los límites por minuto; limitad el paralelismo |
| **Caché** | Guardad cada respuesta en disco con una clave (`modelo + prompt + repetición`) para no repetir llamadas pagadas |
| **Reproducibilidad** | Registrad la **fecha, el modelo y la versión del prompt** de cada ejecución |
| **Salidas estructuradas** | Para el *juez* que clasifica menciones, pedid una salida con **esquema JSON** y validadla |
| **Respuestas no confiables** | Tratad el texto de los LLM y de la web como **datos**, no como instrucciones (riesgo de *prompt injection*) |
| **Privacidad** | No envíes datos personales ni información confidencial a las APIs. Usad solo información pública sobre las marcas |
| **Términos de uso** | Cumplid las condiciones de cada API. No hagáis *scraping* de las interfaces web de los asistentes |

## 3. Estimación de costes

Antes de ejecutar nada, **estimad el coste**:

```
coste total ≈ nº de llamadas × ( tokens de entrada × precio de entrada
                               + tokens de salida  × precio de salida
                               + coste de búsqueda web por llamada )
```

- Las herramientas de búsqueda web suelen tener un **coste adicional por búsqueda**, además de los tokens. Consultad las páginas de precios.
- **Órdenes de magnitud útiles** (para vuestras estimaciones): un prompt del estudio ronda los 100-200 tokens de entrada y una respuesta de 500 a 900 tokens de salida. Un **juez** que evalúa una respuesta completa ronda los 1.000 tokens de entrada y 150 de salida.
- **Número de llamadas** de un estudio = prompts instanciados × motores × repeticiones. En el kit: 52 × 4 × 3 = **624 llamadas** por marca. Un estudio real completo de un sector multiplica esa cifra.

### Plan de costes recomendado para el hackathon

1. **Desarrollad contra los datos del kit** (`ejecuciones.csv` hace de *servidor simulado* de respuestas).
2. **Probad las APIs con una muestra mínima**: por ejemplo, 5-10 prompts × 2 motores × 1-2 repeticiones.
3. **Usad modelos pequeños y baratos para desarrollar** (también para el juez) y reservad los grandes para la demo, si los necesitáis.
4. **Poned un tope de gasto** en la cuenta del proveedor y registrad las llamadas.

## 4. Qué documentar en vuestra arquitectura

Si integráis APIs reales, explicad en el documento de arquitectura:

- Qué motores usáis, con qué configuración de búsqueda web y por qué.
- Cuántas llamadas hace una demo completa y cuánto cuesta.
- Cómo gestionáis errores, límites y no determinismo.
- Qué ocurre cuando una API no está disponible (¿vuestro sistema degrada con elegancia al dataset?).
