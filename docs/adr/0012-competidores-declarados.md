# ADR 0012 · Competidores que cree el cliente frente a los que pone la IA

- **Estado:** aceptado
- **Fecha:** 2026-10-21
- **Zona:** A (`domain/competitor_gap.py`; modelos en `domain/competitor_gap_schemas.py`)

## Contexto

El brief trae `competidores_declarados`, pero hasta ahora solo lo leía el LLM del nodo `market`.
Ningún código lo cruzaba con lo medido, así que no se podía decir «creías que tu rival era X, pero
la IA te compara con Y».

## Decisión

Una función pura, `brecha_competidores(brief, market, metrics) -> BrechaCompetidores`, que:

1. **Resuelve los nombres del brief** a un `brand_id`. Compara nombre, alias e id, sin acentos,
   mayúsculas ni puntuación. Si no hay coincidencia exacta, acepta una sola marca cuyo nombre o
   alias aparezca como palabras completas dentro del nombre declarado, o al revés. Si casan varias
   marcas, el nombre es ambiguo y va a `no_resueltos`. La marca foco nunca cuenta como competidor.
2. **Ordena según lo medido**: puesto en `Metrics.ranking`, Score de Citación, ventaja sobre la
   foco y tasa espontánea global.
3. **Señala dos diferencias**, que se convierten en `Finding` con los campos que ya existen:
   - `F-competidor-no-declarado`: marca no declarada que va por delante de la foco con
     **ventaja ≥ 5 puntos** de Score de Citación. Impacto **L si la ventaja es ≥ 10** y M si no.
     La cifra es la mayor ventaja, en `puntos`.
   - `F-declarado-poco-visible`: competidor declarado, con datos, cuya tasa espontánea global es
     **< max(10 %, 50 % de la tasa de la foco)**. Impacto S, porque corrige el radar del cliente y
     no su visibilidad. La cifra es la menor de esas tasas, en `fraccion`.
   - `evaluation_ids` son las evaluaciones espontáneas globales de las marcas que respaldan la
     cifra. La confianza sale de `findings.confidence_for(n)`.

## Por qué esos umbrales

- **5 puntos.** Por debajo, el orden entre marcas vecinas es ruido. En el kit, las cuatro marcas
  que rodean a Alborada están a menos de 2 puntos entre sí (25,9–27,6). Marcar a todas como
  «la IA te compara con ellas» diluiría el hallazgo. Con 5 puntos se exige una distancia que no
  depende de una o dos respuestas. 10 puntos es un tercio del umbral L de `brecha_lider`, pero
  aquí la marca no es el líder, sino alguien que el cliente ni vigilaba.
- **Tasa relativa a la foco.** «Apenas menciona» depende del sector: un 20 % es poco si la foco
  tiene un 60 % y mucho si tiene un 15 %. El mínimo absoluto del 10 % evita que, cuando la foco
  está casi a cero, ningún declarado resulte «poco visible».
- Cuando llegue `domain/stats` (ADR 0008), el umbral de 5 puntos se podrá sustituir por la
  significancia de la diferencia de scores.

## Consecuencias

- No se toca `schemas.py`. `Finding` basta: el hallazgo nombra las marcas en el texto y respalda
  la cifra con evaluaciones reales. Las listas de marcas viven en `BrechaCompetidores`. Para que la
  propuesta pudiera enlazar el hallazgo con las marcas sin parsear texto, haría falta un campo
  `Finding.brand_ids: list[str] = []` (aditivo, `contract-change`).
- Con el kit de Alborada, de sus tres declarados, Valdecruz queda 1.º, Tramuntana 2.º y Láser
  Nítida 4.º. Oftalmos Centro, que no declara, es 3.º con 13,1 puntos de ventaja → hallazgo L.
  Cervantes, Santa Eulalia y Vistalia también van por delante, pero por menos de 2 puntos.
- No está conectado al grafo. Lo engancha la zona C en `application/diferencial.py`.
