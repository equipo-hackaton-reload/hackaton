# Plan de proyecto: Business Model Canvas y tres niveles

Plan de trabajo propuesto a partir de los requisitos del kit. Las decisiones de producto, el calendario y los umbrales internos de este documento son propuestas del equipo, no requisitos adicionales de la organización.

## 1. Business Model Canvas

El canvas describe nuestro producto GEO, no el modelo de negocio de la clínica. La clínica es el caso de demostración.

**Propuesta en una frase:** convertir el brief de una marca en un diagnóstico verificable de su visibilidad en IA y un plan de mejora ejecutable, con seguimiento de resultados.

| Bloque | Propuesta inicial | Cómo validarla |
|---|---|---|
| Segmentos de clientes | Cliente inicial: agencias de marketing que preparan estudios y propuestas para varias marcas. Segundo segmento: departamentos de marketing con capacidad de ejecutar el plan. Usuarios: consultores y analistas; comprador: dirección de agencia o marketing. | Entrevistar a usuarios y compradores sobre su proceso actual y quién decide el presupuesto. |
| Propuesta de valor | Reducir trabajo manual entre brief, diagnóstico y propuesta; ofrecer cifras auditables, acciones justificadas y seguimiento. | Comparar tiempo de preparación y calidad de una propuesta manual con la generada por el prototipo. No afirmar un ahorro hasta medirlo. |
| Canales | Pilotos con agencias, demostraciones directas y alianzas con consultoras de marketing. | Conseguir una revisión de la demo por un usuario del segmento y registrar objeciones. |
| Relación con clientes | Incorporación guiada, revisión humana de la propuesta y seguimiento periódico. | Comprobar si un consultor entiende los resultados y puede corregir el brief y las prioridades. |
| Fuentes de ingresos | Hipótesis: diagnóstico inicial de pago y suscripción por marcas activas y frecuencia de seguimiento; posible servicio de revisión experta. | Preguntar disposición a pagar y comparar ingresos previstos con costes por estudio. Precio pendiente de validación. |
| Recursos clave | Evaluador, motor de métricas, banco de prompts, orquestación, almacenamiento de evidencias y conocimiento GEO. | Medir reproducibilidad de métricas, calidad de evaluación y utilidad del informe. |
| Actividades clave | Interpretar briefs, diseñar estudios, evaluar respuestas, generar planes y repetir mediciones. | Medir tiempo, coste, fallos y necesidad de corrección humana en cada etapa. |
| Socios clave | Proveedores de modelos y búsqueda, agencias piloto, especialistas GEO y revisores sectoriales cuando proceda. | Confirmar acceso técnico a proveedores y disponibilidad de revisión del dominio. No asumir acuerdos existentes. |
| Estructura de costes | Desarrollo, alojamiento, almacenamiento, llamadas de generación y evaluación, búsqueda web, soporte y revisión humana. | Registrar coste por estudio y horas de revisión; estimar margen antes de fijar precio. |

### Hipótesis de negocio prioritarias

1. El problema principal del cliente es el tiempo y la dificultad de pasar de métricas a acciones concretas.
2. La trazabilidad y la revisión humana son necesarias para que confíe en el informe.
3. Hay interés en una medición recurrente, no solo en un diagnóstico puntual.
4. El cliente puede ejecutar las acciones con su presupuesto y equipo.

**Entregable de esta fase:** canvas, descripción del usuario y una historia principal: «Como consultor, quiero cargar un brief y obtener un diagnóstico con evidencias y un plan revisable para presentarlo al cliente».

**Criterio de salida:** acordar cliente inicial, problema, valor, alcance de la demo e hipótesis pendientes. Se puede desarrollar con estas hipótesis sin presentarlas como negocio validado.

## 2. Producto y alcance

Flujo principal:

`Brief → ficha estructurada → estudio → respuestas → evaluaciones → métricas → hallazgos → plan → propuesta → seguimiento`

Dos modos de datos:

- **Kit sintético:** caso Alborada, cuatro motores simulados y dataset suministrado. Base reproducible de la demo.
- **Estudio real:** marca pública real y consultas a dos proveedores con búsqueda web. Datos separados del kit y etiquetados por origen.

Alborada y sus dominios son ficticios: consultar APIs sobre ella no demuestra visibilidad real. Para el estudio real se usará otro brief de una marca real con información pública, sin atribuirle datos del kit. Esto también permite demostrar soporte multimarca.

### Restricciones de Alborada que debe aplicar el sistema

- Prioridad: cirugía refractiva y control de miopía infantil.
- Madrid como mercado principal y Barcelona como expansión.
- Presupuesto de esta iniciativa: 18.000–27.000 €/año, derivado del 20–30 % de 90.000 €.
- Equipo limitado: marketing, comunicación a media jornada y agencia.
- Horizonte de primeros resultados a 6 meses y objetivo de negocio a 12 meses.
- Tono riguroso y restricciones sanitarias descritas en el brief.
- El +25 % de primeras visitas es un objetivo del cliente; no un resultado garantizado ni deducible de un aumento del score.

## 3. Arquitectura que permite crecer por niveles

| Componente | Responsabilidad | Implementación funcional |
|---|---|---|
| Orquestador | Ejecutar etapas, guardar estado, errores y trazas | Flujo controlado por código; incorporar un framework solo si aporta valor |
| Agente de brief y estudio | Extraer objetivos y restricciones; proponer preguntas y competidores | LLM con salida estructurada y validación |
| Adaptador de datos | Leer el kit o consultar proveedores | Código con una interfaz común para ambas fuentes |
| Evaluador | Detectar nombres y posición; clasificar recomendación, sentimiento y fuentes | Código para detección y posición; reglas o juez LLM para clasificación |
| Motor de métricas | Calcular score, tasas y comparativas | Código determinista |
| Agente de estrategia y plan | Proponer hallazgos y acciones sobre métricas ya calculadas | LLM con referencias a evidencias y restricciones del brief |
| Validador | Revisar estructura, cifras, referencias, presupuesto y campos obligatorios | Código y revisión humana; juicio cualitativo adicional en nivel 3 |
| Interfaz e informe | Mostrar resultados, evidencias, plan y exportación | Aplicación con vistas de brief, diagnóstico, plan y seguimiento |

Se pueden usar modelos y frameworks existentes. La aportación del equipo será el flujo, las herramientas, el evaluador, las métricas, las evidencias y la calidad del plan. No hace falta entrenar un modelo.

Contratos mínimos compartidos: `Brief`, `Study`, `Execution`, `BrandEvaluation`, `Metrics`, `Finding`, `Action`, `Report`. Cada resultado conservará el identificador del estudio y su origen; cada hallazgo tendrá evidencias y cada acción enlazará sus hallazgos.

## 4. Nivel 1: MVP completo sobre el kit

**Objetivo:** cargar el brief de Alborada y obtener una propuesta completa basada en las 624 respuestas.

| ID | Trabajo | Entregable | Comprobación |
|---|---|---|---|
| N1.1 | Cargar brief en texto o Markdown y permitir revisar sus campos | Ficha de marca | Conserva prioridades, ciudades, equipo, presupuesto y horizonte |
| N1.2 | Importar CSV en UTF-8 con BOM y cruzar identificadores | Cargador y datos normalizados | 10 marcas, 25 plantillas, 624 ejecuciones, 25 fuentes y 133 filas de muestra |
| N1.3 | Detectar marca y alias sin distinguir acentos o mayúsculas; calcular primera aparición | Evaluaciones de presencia y posición | Evita contar alias solapados dos veces y calcula posición entre las marcas presentes del sector |
| N1.4 | Clasificar tipo de mención, fuerza, sentimiento y fuente | Registro evaluado | Respeta `Marcas a evaluar`; se esperan 2.928 filas para el kit completo |
| N1.5 | Calcular Score de Citación y tasas | Tablas por marca, motor, intención y ciudad | Fórmula documentada; denominadores explícitos; espontánea y asistida separadas |
| N1.6 | Construir 3–7 hallazgos y acciones ligadas a ellos | Diagnóstico y plan por fases | Cada cifra apunta a datos calculados y cada acción tiene responsable, plazo, entregable y KPI |
| N1.7 | Integrar las vistas del producto | Demo de principio a fin | Un usuario puede revisar brief, resultados, evidencia y propuesta |

### Reglas metodológicas

- Espontánea: prompts `generico` y `ciudad`; asistida: `marca` y `par`.
- Evaluar solo las marcas elegibles en cada ejecución; las ausencias en evaluaciones elegibles cuentan en los denominadores.
- Sin observaciones en un segmento: mostrar «sin datos», no un 0 % de visibilidad.
- Las fuentes citadas pertenecen a la ejecución; el tipo de fuente atribuido a una marca requiere evidencia específica. Si no se puede resolver, marcar la incertidumbre.
- Mostrar por separado la mención por desconocimiento, la advertencia negativa y la recomendación activa.
- Los grupos comparados deben tener cobertura comparable; no mezclar prompts asistidos de marcas foco con ausencia de prompts propios de marcas de contexto.
- Toda la salida del caso Alborada debe indicar que los datos son sintéticos.

**Puerta de salida:** demo completa que genera una propuesta utilizable; revisión de ejemplos de score y de casos límite contra la muestra. Guardar una versión estable antes de ampliar.

## 5. Nivel 2: agentes explícitos y evaluación validada

**Objetivo:** hacer visible y verificable cómo se prepara el estudio y se genera una propuesta de calidad.

| ID | Trabajo | Entregable | Comprobación |
|---|---|---|---|
| N2.1 | Formalizar agente de brief/estudio y agente de estrategia/plan con herramientas y contratos | Orquestación con trazas | Se pueden consultar entradas, salidas, errores y evidencias de cada etapa |
| N2.2 | Generar preguntas a partir de servicios, públicos, ciudades y cuatro fases | Banco nuevo de prompts | Incluye tipo de instanciación, marca objetivo, intención y propósito |
| N2.3 | Añadir juez LLM estructurado y respaldo ante fallos | Evaluador híbrido | Una llamada por respuesta para todas sus marcas elegibles; validación de tipos y rangos |
| N2.4 | Comparar con la muestra y revisar errores | Informe de calibración | Concordancia de presencia/posición, matriz de confusión de clases y error absoluto medio de fuerza |
| N2.5 | Priorizar por impacto, esfuerzo y restricciones | Plan priorizado | Cada acción tiene explicación de prioridad, dependencia, coste estimado y responsable |
| N2.6 | Exportar a uno de los formatos admitidos | PDF, Word o presentación | Cifras iguales a las de la aplicación, fuentes visibles y documento legible |

Los prompts nuevos no tienen respuestas en el CSV. En este nivel se pueden generar y revisar; solo se calculan métricas sobre respuestas existentes. Se ejecutarán preguntas nuevas al conectar APIs en el nivel 3.

Para validar, separar las 15 ejecuciones por `Ejecucion_ID`, nunca aleatoriamente por filas de marca. Por ejemplo, 10 ejecuciones para calibrar y 5 reservadas para revisar al final. Documentar que son pocas y ampliar revisión manual a otras respuestas, con negativos, ausencia de fuentes, alias y ciudades. No usar las etiquetas esperadas como entrada del juez.

**Objetivos internos propuestos:** al menos 95 % de acuerdo en presencia y error absoluto medio de fuerza de recomendación ≤ 0,5 en la revisión reservada. Son metas del equipo; publicar los resultados reales y los fallos aunque no se alcancen. Revisar por separado posición y clases con pocas observaciones.

**Puerta de salida:** agentes trazables, banco generado, evaluador contrastado, prioridades justificadas y propuesta exportada. Mantener funcionando la demo de nivel 1.

## 6. Nivel 3: datos reales, evolución y evaluación del sistema

Este nivel contiene varios extras. Para cubrir todos los puntos del documento del reto, planificar los seis bloques siguientes.

| ID | Trabajo | Implementación prevista | Criterio de aceptación |
|---|---|---|---|
| N3.1 | Consultas reales a dos APIs con búsqueda web | Dos adaptadores con formato común de respuesta, citas, motor, versión, fecha y estado de búsqueda | Ejecutar el mismo banco en ambos, conservar respuestas y URLs, e informar cuándo el modelo no busca |
| N3.2 | Descubrir competidores | Extraer entidades de respuestas, resolver alias y filtrar por sector/geografía; proponer candidatos con fragmentos y fuentes para revisión | Incorporar al menos un candidato válido que no estuviera en la lista inicial, si las respuestas lo aportan; no fabricarlo si no aparece |
| N3.3 | Re-medición y evolución | Guardar estudios por fecha y comparar versiones compatibles | Mostrar dos mediciones reales con cobertura comparable; etiquetar una repetición cercana como repetibilidad, no como mejora por el plan |
| N3.4 | Simular impacto | Escenarios explícitos de aparición, fuerza y fuente; recalcular el score con la misma fórmula | Mostrar supuestos, score simulado y diferencia respecto a la base; aclarar que no predice visitas ni garantiza resultados |
| N3.5 | Evaluar la calidad del sistema | Revisar hallazgos y planes con rúbrica humana y juez adicional contrastado con esa revisión | Registrar discrepancias; medir soporte de afirmaciones, relevancia, viabilidad y cumplimiento del brief |
| N3.6 | Soporte multimarca | Separar briefs, catálogos y estudios por identificador; procesar Alborada y una marca real | Generar dos informes independientes sin cruzar datos ni restricciones; no hace falta multisector para demostrar multimarca |

### Piloto real y control de costes

1. Elegir una marca real y revisar un brief basado en datos públicos.
2. Escoger dos proveedores según acceso del equipo, disponibilidad de búsqueda y coste verificado en documentación oficial al implementar. No fijar versiones o tarifas con la guía del kit como única referencia.
3. Usar inicialmente 8 preguntas que cubran las cuatro intenciones, 2 motores y 2 repeticiones: **32 respuestas por medición**. Registrar cuántas son espontáneas y asistidas.
4. Para dos mediciones, presupuestar 64 consultas, más evaluación, generación de brief/plan y búsquedas. Si el juez se ejecuta una vez por respuesta, añadir hasta 64 llamadas de evaluación, sin contar reintentos.
5. Fijar un límite explícito de gasto antes de lanzar; estimar tokens, búsquedas y reintentos. El presupuesto de marketing del brief no es el presupuesto de APIs del hackathon.
6. Cachear respuestas. Una re-medición nueva debe generar una nueva captura con nuevo identificador; una consulta de resultados existentes sí debe reutilizar la caché.
7. Guardar resultados parciales, aplicar espera creciente y marcar fallos. Los fallos de red no cuentan como ausencia de marca.
8. Si una API falla, permitir enseñar el kit o capturas previas con su origen y fecha visibles; no sustituir silenciosamente datos reales por sintéticos.

### Comparación temporal honesta

Comparar banco, tipos de prompt, marcas elegibles, motores, configuración y repeticiones equivalentes. Si cambia la versión del modelo o el banco, señalarlo y limitar la comparación al subconjunto común. Guardar el catálogo y evaluador de cada estudio. Ante nuevos competidores, reevaluar de manera comparable cuando sea posible.

Dos capturas durante el hackathon demuestran el mecanismo de seguimiento, no un efecto causal de acciones de marketing. Medir resultados de negocio requiere un seguimiento posterior y datos que el kit no incluye.

**Puerta de salida:** piloto documentado con dos APIs, candidatos a competidores, histórico comparable, escenarios etiquetados, revisión de calidad y dos marcas separadas.

## 7. Organización del equipo

Reparto propuesto para cinco personas; asignar nombres según experiencia y disponibilidad.

| Rol | Responsabilidad principal | Primera entrega |
|---|---|---|
| Producto y negocio | Canvas, alcance, restricciones del brief, narrativa y presentación | Canvas y lista de aceptación del MVP |
| Datos y métricas | Cargadores, alias, posición, score y agregaciones | Registro evaluado y métricas verificables |
| Agentes y evaluación | Extracción de brief, juez, estrategia y validación | Contratos estructurados y primera propuesta |
| Interfaz e informes | Navegación, evidencias, visualizaciones y exportación | Pantallas conectadas al contrato de datos |
| Integración y calidad | Orquestación, persistencia, APIs, costes y reproducción | Flujo ejecutable y comprobación de integración |

Cada tarea tiene una persona responsable y otra revisora. Acordar primero los contratos para poder desarrollar partes en paralelo sin esperar al producto completo. Integrar al cerrar cada bloque y revisar código antes de incorporarlo a la versión estable.

## 8. Calendario adaptable

No se conoce la duración oficial del hackathon. Este ejemplo usa **30 horas de trabajo del equipo con tareas simultáneas**; no representa 30 horas-persona ni una fecha comprometida. Ajustar al calendario real y al acceso a claves.

| Bloque | Ventana orientativa | Trabajo | Resultado |
|---|---|---|---|
| A | Horas 0–2 | Canvas, historia principal, contratos y muestra de informe | Alcance acordado |
| B | Horas 2–12 | Nivel 1; interfaz y datos avanzan simultáneamente | Demo completa guardada como versión estable |
| C | Horas 12–19 | Nivel 2, validación, trazas y exportación | Propuesta verificable y presentable |
| D | Horas 19–27 | Nivel 3; conectores y almacenamiento pueden prepararse antes | Extras demostrables y limitaciones documentadas |
| E | Horas 27–30 | Correcciones, arquitectura, instrucciones y ensayo | Entrega reproducible |

Si un nivel no supera su puerta de salida, usar primero el tiempo de extras para estabilizarlo. Si el calendario es menor, reducir el tamaño del piloto y el acabado visual antes de sacrificar el flujo completo, la trazabilidad o la propuesta. Cubrir los tres niveles es el objetivo; la viabilidad temporal se revisará al completar cada bloque.

## 9. Entrega final y guion de demo

- Repositorio con instrucciones de instalación y ejecución, dependencias fijadas y ejemplo de configuración sin secretos.
- Documento de arquitectura de 1–2 páginas: diagrama, decisiones, código frente a LLM, coste, errores y limitaciones.
- Propuesta de Alborada con resumen ejecutivo, diagnóstico, competencia, hallazgos, estrategia, acciones, seguimiento y recursos.
- Informe de validación del evaluador y de la calidad del plan, con resultados medidos y errores conocidos.
- Evidencias de nivel 3: consultas reales, candidatos a competidores, dos capturas, escenarios y segundo brief.
- Presentación y demo ajustadas al tiempo oficial cuando se conozca.

Guion: problema y canvas → cargar Alborada → diagnóstico espontáneo/asistido → abrir una evidencia → revisar una acción y su presupuesto → exportar → mostrar estudio real de segunda marca → histórico y simulación → cerrar con validación, costes y limitaciones.

## 10. Primeras tareas para empezar

- [ ] Acordar los nueve bloques del canvas y distinguir hipótesis de hechos.
- [ ] Asignar los cinco roles y revisar disponibilidad de claves y presupuesto técnico.
- [ ] Definir esquemas de datos y un ejemplo de propuesta final antes de construir pantallas.
- [ ] Implementar la carga del kit y comprobar sus recuentos.
- [ ] Resolver detección y posición en las 15 ejecuciones de muestra.
- [ ] Completar el recorrido del nivel 1 antes de ampliar el alcance.

## Fuentes locales

- [Requisitos y evaluación](01_Reto_requisitos_y_evaluacion.md)
- [Metodología GEO y fórmula del score](02_Metodologia_GEO.md)
- [Diccionario de datos](03_Diccionario_de_datos.md)
- [Flujo y arquitectura de referencia](04_Flujo_actual_y_arquitectura_de_referencia.md)
- [Guía de APIs y costes](05_Guia_de_APIs_y_costes.md)
- [Formato de la propuesta](06_Formato_del_entregable.md)
- [Brief de Alborada](../01_Briefings/Brief_de_ejemplo_Clinica_Alborada.md)
