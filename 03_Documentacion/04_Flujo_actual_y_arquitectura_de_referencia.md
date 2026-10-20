# Flujo actual de reload. y arquitectura de referencia

Este documento tiene dos partes: **cómo trabajamos hoy** (para que entendáis el proceso real sobre el que se plantea el reto) y un **modelo de referencia** para pensar la arquitectura de vuestro sistema. El modelo es **orientativo, no obligatorio**: lo que valoramos es que justifiquéis vuestras decisiones.

---

## Parte 1 · Cómo lo hacemos hoy

### 1.1 El proceso de un estudio de visibilidad en LLMs

```
 ① Configurar        ② Banco de        ③ Instanciar     ④ Ejecutar en       ⑤ Evaluar        ⑥ Registrar    ⑦ Analizar y
    el sector           prompts           prompts           los motores         respuestas                       reportar
 ───────────────    ──────────────    ─────────────    ───────────────    ─────────────   ───────────   ───────────────
 Sectores, marcas   Prompts por       Marcas, pares    4 motores con      Detección de    Una fila por   Score, embudo,
 foco y contexto    fase del embudo   y ciudades       búsqueda web y     marcas + juez   marca y        motores, fuentes
 (hoja de cálculo)  y por perfil                       varias             que clasifica   ejecución      + informe Word
                                                       repeticiones       la mención      (Excel)        + análisis
                                                                                                         conversacional
```

| Paso | Qué hacemos | Cómo |
|---|---|---|
| ① Configurar | Definir por sector las marcas foco (con prompts propios) y las de contexto (detectadas en las mismas respuestas) | Hoja de cálculo |
| ② Banco de prompts | Diseñar prompts naturales por fase del embudo, por perfil de usuario, por precio, por fuentes y por geografía | Hoja de cálculo; 9 familias y prioridades P1-P3 |
| ③ Instanciar | Sustituir marcas, pares estratégicos y ciudades | Automático |
| ④ Ejecutar | Lanzar cada prompt a ChatGPT, Gemini, Perplexity y Claude, con búsqueda web, varias veces | Scripts que llaman a las API oficiales; reintentos con espera creciente; ejecución en paralelo; reanudación si se corta; estimación de coste previa; modo simulación sin coste |
| ⑤ Evaluar | Detectar marcas (con alias) y calcular posición; un **juez LLM** clasifica tipo de mención, fuerza, sentimiento y fuente en **una sola llamada por respuesta** (con reglas de respaldo si falla) | Python + LLM con salida estructurada |
| ⑥ Registrar | Volcar cada resultado como una fila de evaluación, con copia de seguridad | Hoja de cálculo |
| ⑦ Analizar y reportar | Calcular el Score de Citación y las tablas; generar un informe Word con narrativa redactada por IA **anclada a las cifras calculadas**; permitir preguntas en lenguaje natural sobre los datos | Python + aplicación web local + Word |

### 1.2 Principios que ya aplicamos (y que os recomendamos)

- **Las cifras las calcula el código, no el LLM.** El LLM redacta y razona **sobre** tablas ya calculadas. Esto evita que se inventen números.
- **Trazabilidad**: cada resultado guarda la respuesta íntegra y las fuentes; cualquier cifra se puede auditar.
- **Control de costes**: estimar antes de ejecutar; piloto con un sector antes del estudio completo.
- **Robustez**: reintentos, reanudación y copias de seguridad.

### 1.3 Qué sigue siendo (mayormente) manual → el espacio del reto

La **ejecución y medición** están muy automatizadas. El tramo que va **del brief al plan** sigue dependiendo de un consultor:

| Hoy lo hace una persona | Lo que queremos que haga el sistema |
|---|---|
| Leer el brief y entender el negocio, el público y las prioridades | **Interpretar el brief** y estructurarlo |
| Decidir qué sector, subsector y qué marcas son la competencia | **Identificar competidores** y actores del mercado |
| Adaptar el banco de prompts al negocio concreto (perfiles, ciudades, servicios prioritarios) | **Diseñar los prompts** del estudio a partir del brief |
| Interpretar el diagnóstico y decidir qué importa | **Detectar y priorizar hallazgos** con evidencias |
| Redactar la estrategia y el plan de acción (fases, entregables, tiempos, KPIs) | **Generar estrategia y plan** accionables |
| Adaptar el mensaje a la audiencia (comité, dirección, equipo) | **Adaptar el entregable a la audiencia** del brief |

---

## Parte 2 · Arquitectura de referencia (orientativa)

### 2.1 Modelo funcional

Un sistema agéntico no es necesariamente «muchos agentes»: es un sistema en el que **componentes con responsabilidades claras** (algunos basados en LLM, otros en código) colaboran, guiados por un **orquestador**, para lograr un objetivo. Este es un posible reparto de responsabilidades.

```
                     ┌──────────────────────────────────────┐
        Brief ───► │            ORQUESTADOR               │ ◄── Estado compartido y trazas
                     │  (flujo, reintentos, puntos de       │
                     │   revisión humana, costes)           │
                     └───┬──────────────────────────────────┘
                         │
   ┌─────────────────────┼───────────────────────────────────────────────────────┐
   │ 1 Intake            │ Interpreta el brief → ficha estructurada              │ LLM
   │ 2 Mercado           │ Identifica competidores y líder; foco vs contexto     │ LLM + datos
   │ 3 Prompts           │ Diseña y instancia el banco por embudo, perfil, ciudad│ LLM
   │ 4 Ejecutor          │ Consulta a los motores; control de coste y errores    │ Código
   │ 5 Evaluador         │ Detecta marcas y clasifica menciones                  │ Código + LLM
   │ 6 Analista          │ Calcula métricas y detecta hallazgos con evidencias   │ Código (+LLM)
   │ 7 Estratega         │ Convierte hallazgos en estrategia priorizada          │ LLM
   │ 8 Planificador      │ Fases, entregables, tiempos, responsables, KPIs       │ LLM + reglas
   │ 9 Redactor          │ Propuesta final adaptada a la audiencia; exportación         │ LLM + plantillas
   └─────────────────────┴───────────────────────────────────────────────────────┘
                         │
                         ▼
        Propuesta (documento / dashboard / presentación) + datos de soporte
```

Podéis fusionar, dividir o sustituir componentes. Un diseño con **menos agentes pero bien justificado** es mejor que uno con muchos y artificiales.

### 2.2 Principios de diseño recomendados

1. **Separad lo que calcula el código de lo que razona el LLM.** Métricas, agregaciones y scores: código determinista. Interpretación, hipótesis, priorización y redacción: LLM, **siempre sobre cifras ya calculadas**.
2. **Salidas estructuradas entre componentes.** Usad esquemas (por ejemplo JSON) para que cada paso reciba y entregue datos validables.
3. **Trazabilidad de evidencias.** Cada hallazgo y cada recomendación debe apuntar a las filas, respuestas o fuentes que lo sustentan.
4. **Control del no determinismo y del coste.** Repeticiones, caché de respuestas, registro de versiones de modelo y de prompts, límite de llamadas.
5. **Puntos de revisión humana.** Por ejemplo, confirmar los competidores identificados antes de ejecutar el estudio.
6. **Validación.** Revisad a mano una muestra de vuestras evaluaciones; si usáis un LLM como juez, validadlo contra una muestra revisada por una persona.
7. **Seguridad.** Las respuestas de los LLM y el contenido web son **datos no confiables**: pueden contener instrucciones maliciosas (*prompt injection*) o errores. Tratadlos como datos, no como órdenes. No incluyáis claves en el repositorio.
8. **Adaptación a la audiencia.** El tono, la profundidad y la estructura de la propuesta deben responder a quién la va a leer y a las restricciones del brief.

### 2.3 Flujo de datos mínimo

| Etapa | Entrada | Salida |
|---|---|---|
| Intake | Brief (texto o documento) | Ficha estructurada de la marca |
| Mercado | Ficha | Lista de marcas (foco y contexto) con rol |
| Prompts | Ficha + marcas | Banco de prompts instanciado |
| Ejecución | Prompts | Respuestas en bruto + fuentes |
| Evaluación | Respuestas | Registro evaluado (una fila por marca y ejecución) |
| Análisis | Registro | Métricas y hallazgos con evidencias |
| Estrategia y plan | Hallazgos + ficha | Estrategia y plan de acción estructurados |
| Redacción | Estrategia, plan y métricas | Propuesta final |

Con los **datos del kit**, la etapa de *Ejecución* ya viene resuelta (`ejecuciones.csv`). La *Evaluación* y todo lo que sigue es trabajo vuestro; `muestra_evaluada.csv` os sirve de ejemplo y de calibración.

### 2.4 Opciones de implementación

No exigimos ninguna tecnología. Podéis construir el sistema con código propio o apoyaros en frameworks de agentes y orquestación (por ejemplo LangGraph, CrewAI, AutoGen, o los SDK de agentes de los proveedores de LLM), con la interfaz que prefiráis (web, aplicación, dashboard o notebook). Elegid según lo que podáis **demostrar** y **justificar**.

### 2.5 Decisiones que esperamos ver justificadas en vuestro documento de arquitectura

- ¿Por qué esa estructura (agentes, pipeline determinista o híbrido)?
- ¿Qué hace el LLM y qué hace el código? ¿Cómo evitáis que se inventen cifras?
- ¿Cómo gestionáis el no determinismo y el coste?
- ¿Cómo garantizáis la trazabilidad de los hallazgos?
- ¿Cómo validáis la calidad de la detección, de la evaluación y del plan?
- ¿Cómo adapta el sistema la propuesta a las restricciones y la audiencia del brief?
- ¿Qué limitaciones y riesgos tiene vuestra solución?
