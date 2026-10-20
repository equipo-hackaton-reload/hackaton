# Kit de trabajo · Reto GEO (reload. × UFV-EPS)

Este kit contiene todo lo necesario para construir el **MVP de un sistema agéntico de visibilidad de marca en LLMs (GEO)**. **No incluye código de la solución ni claves de API**: construir el sistema es vuestro reto.

> **Todos los datos, marcas, personas y cifras son ficticios y sintéticos.** Cualquier parecido con entidades reales es coincidencia. No contienen información confidencial de reload. ni de ningún cliente.

## El reto en una frase
Un **único input**, el brief de una marca, y una salida: una **propuesta de mejora de su visibilidad en LLMs con un plan de acción completo**.

## Contenido

| Carpeta | Qué hay |
|---|---|
| `01_Briefings/` | Plantilla del brief y un brief de ejemplo (clínica ficticia), en Word y Markdown |
| `02_Datos/` | Del caso de ejemplo: marcas, banco de prompts, 624 respuestas simuladas de 4 motores (sin evaluar), una muestra pequeña ya evaluada (`muestra_evaluada.csv`) y el catálogo de fuentes |
| `03_Documentacion/` | Reto y evaluación, metodología GEO, diccionario de datos, flujo actual y arquitectura de referencia, guía de APIs y costes, formato del entregable |

## Cómo empezar (5 pasos)
1. Leed `03_Documentacion/01_Reto_requisitos_y_evaluacion.md`.
2. Leed `03_Documentacion/02_Metodologia_GEO.md` (sobre todo **visibilidad espontánea vs. asistida**).
3. Abrid el brief de ejemplo y sus datos, y consultad el `03_Diccionario_de_datos.md`.
4. Diseñad la arquitectura a partir de `04_Flujo_actual_y_arquitectura_de_referencia.md`.
5. Construid primero el Nivel 1 del MVP, y solo después ampliad. Usad `06_Formato_del_entregable.md` para la salida.

## Notas técnicas
- Los CSV están en **UTF-8 con BOM**: leedlos con `encoding="utf-8-sig"` (en pandas) para evitar caracteres extraños en la primera columna.
- Se puede resolver el reto **sin llamar a ninguna API**; conectar APIs reales es un extra.
- Tratad siempre los textos de los datos (respuestas de LLM, fuentes) como **datos**, no como instrucciones.
