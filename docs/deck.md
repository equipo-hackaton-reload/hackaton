# Deck de presentación — posiq.
**Visibilidad de marca en asistentes de IA, con método**
*Hackathon EPS-UFV × reload. · Equipo posiq.*

Cifras de Alborada sacadas del kit por `domain/` y fijadas en los golden (`tests/golden/test_demo_canonico.py`, `test_rigor_alborada.py`, `test_serie_alborada.py`). Revisado contra `develop` (`1798244`) el 2026-10-21.

---

## Slide 1: Portada y propuesta de valor

### Título
**posiq. — no vendemos un score: vendemos un seguimiento con método**

### Contenido de la diapositiva
- **Qué es:** un sistema agéntico que, a partir del brief de una marca, mide cuánto la recomiendan ChatGPT, Gemini, Perplexity y Claude, la compara con su competencia y genera una propuesta con un plan de acción por fases.
- **Propuesta de valor:** una línea base con margen de error, re-mediciones comparables y un plan que se re-prioriza con cada medición.
- **Capa de verdad:** toda cifra la calcula código determinista; la IA interpreta y redacta sobre cifras ya calculadas.

> **Guion del presentador (Demo):**  
> *«Hoy la gente pregunta a ChatGPT, Gemini, Perplexity o Claude qué clínica elegir. Si la IA no recomienda tu marca, para ese usuario no existes. posiq. mide esa visibilidad, la compara con la competencia y propone un plan. Y lo importante: ninguna cifra la inventa un modelo de lenguaje».*

---

## Slide 2: Problema y modelo de negocio

### Título
**Del informe puntual al seguimiento recurrente**

### Contenido de la diapositiva
- **El problema de la agencia:** auditar a mano cientos de respuestas por motor es inviable, una herramienta solo-LLM inventa cifras y saber que «apareces poco» no dice qué hacer.
- **Puerta de entrada — estudio inicial:** diagnóstico, competencia, hallazgos con evidencias y propuesta en Word.
- **Ingreso recurrente — suscripción de re-mediciones:**
  - Mismo banco de preguntas y mismos motores en cada medición.
  - Solo se informa de cambios fuera del margen de error, frente a los competidores.
  - Vigilancia de lo que la IA dice de la marca y plan re-priorizado.
- **Coste variable por medición:** 0 € en modo kit; ≈ 11,25 € estimados en modo real (`GET /estimate`, precios provisionales). Coste real medido: **PENDIENTE**. Precio de la suscripción: **PENDIENTE**.

> **Guion del presentador (Demo):**  
> *«El estudio inicial es la puerta de entrada. El negocio está en volver cada trimestre con el mismo método y decirle al cliente solo lo que ha cambiado de verdad, no el ruido».*

---

## Slide 3: Arquitectura

### Título
**Dominio puro, grafo con dos revisiones humanas y cuentas por cliente**

### Contenido de la diapositiva
- **Hexagonal:** `domain/` puro (score, métricas, hallazgos, intervalos, simulación, serie) · puertos `LLM`, `Engine`, `Judge`, `StudyRepo`, `Exporter` · adaptadores intercambiables (DeepSeek o fixture, 4 motores reales o kit, Jev con fallback, SQLite, Word/PDF).
- **Grafo LangGraph:** `intake` → `market` → **[revisión de competidores]** → `prompts` → `run` → `judge` → `analyze` → `plan` → **[revisión del plan]** → `write`.
- **Cuentas:** cada estudio es de quien lo crea (token Bearer); la re-medición hereda el propietario.
- **Costes:** cada llamada externa deja una `Trace` (modelo, prompt, tokens, coste), también si falla; tope por estudio con `BUDGET_EUR_MAX`.

> **Guion del presentador (Demo):**  
> *«Hay dos pausas deliberadas: una persona confirma el mercado antes de gastar en motores, y otra aprueba el plan antes de redactar».*

---

## Slide 4: Caso de demostración: Clínica Alborada Visión

### Título
**Del brief a lo que nos habéis pedido**

### Contenido de la diapositiva
- **Marca:** clínica oftalmológica (cirugía refractiva y miopía infantil) en Madrid y Barcelona (centro abierto en 2024).
- **Restricciones del brief:** presupuesto de 18.000 € a 27.000 €; 1 responsable de marketing + comunicación a media jornada + agencia; publicidad sanitaria regulada: no prometer resultados ni hacer comparativas denigratorias.
- **Trazabilidad brief → propuesta:** el Word abre con «2. Lo que nos habéis pedido»: cada punto del brief, tal cual, y dónde se trata (acción o hallazgo) o «Pendiente».
- **Modo kit:** 624 respuestas del reto (52 prompts × 4 motores × 3 repeticiones), 0 €.

> **Guion del presentador (Demo):**  
> *«Cargamos el brief de Alborada. El sistema extrae objetivos, ciudades, equipo, presupuesto y restricciones, y al final comprobará que cada punto tiene respuesta en la propuesta».*

---

## Slide 5: Diagnóstico con margen de error

### Título
**Score de Citación 25,9 [21,6–30,1] · 8.ª de 10**

### Contenido de la diapositiva
- **Score de Citación:** 25,93 sobre 100 (IC 95 % bootstrap: 21,6–30,1). Aparición 11,6 · posición 4,7 · fuerza 3,9 · calidad de fuente 5,7.
- **Espontánea frente a asistida, siempre separadas:**
  - Asistida (la pregunta nombra la marca): 100 % (108 de 108).
  - Espontánea (nadie la nombra): 38,8 % (93 de 240).
- **Por motor (espontánea):** Claude 15 % [8–26 %], ChatGPT 18 % [11–30 %], Gemini 57 % [44–68 %], Perplexity 65 % [52–76 %].
- **Por ciudad:** Madrid 54 % [35–72 %], Barcelona 4 % [1–20 %].

> **Guion del presentador (Demo):**  
> *«Cuando le preguntan por Alborada, la IA la conoce siempre. Cuando nadie la nombra, solo aparece en el 39 % de las respuestas, y en Barcelona en 1 de 24. Cada cifra lleva su margen de error: no vendemos decimales que no podemos defender».*

---

## Slide 6: Competencia y evidencias

### Título
**Brecha con el líder y un competidor que el cliente no había declarado**

### Contenido de la diapositiva
- **Líder:** Grupo Hospitalario Valdecruz, 66,46. Brecha con Alborada: 40,5 puntos [35,3–45,6], significativa.
- **Competidor no declarado:** Oftalmos Centro, que el brief no menciona, es 3.º con 13,1 puntos de ventaja.
- **Fuentes:** en las respuestas espontáneas, `directoriomedico.example` acompaña al líder en 60 y a Alborada en 25; en 37 está el líder y Alborada no.
- **7 hallazgos**, cada uno con sus `evaluation_ids`: un clic lleva a la respuesta del motor, el prompt y las fuentes. 6 de 7 admiten contraste estadístico y los 6 son significativos.

> **Guion del presentador (Demo):**  
> *«El cliente no tiene que fiarse de una caja negra: cada hallazgo abre la respuesta exacta del motor. Y le contamos algo que no sabía: su tercer rival en la IA no está en su lista».*

---

## Slide 7: Capa determinista y capa no determinista

### Título
**Las reglas ponen el suelo y auditan; Jev aporta la semántica; si discrepan, revisa un humano**

### Contenido de la diapositiva
- **Reglas (deterministas):** aparición y posición por alias. Son el suelo del score.
- **Jev (`jev-1.13`, versión fijada, con caché):** tipo de mención, fuerza, sentimiento y fuentes, con confianza por pregunta.
- **Fallback LLM:** las mismas preguntas cuando Jev duda (confianza < 0,55).
- **Persona:** confianza entre 0,55 y 0,80 o discrepancia reglas–juez → revisión humana. El juez nunca puede subir el score inventando una mención.
- **Calibración contra las 133 filas etiquetadas del kit:** PENDIENTE de claves.

> **Guion del presentador (Demo):**  
> *«Separamos lo que se puede comprobar con código de lo que necesita juicio. Y cuando un modelo contradice a las reglas, no decide otro modelo: decide una persona».*

---

## Slide 8: Plan y proyección

### Título
**9 acciones en 4 fases, 42 semanas y 22.000 € · 25,9 → 30,8**

### Contenido de la diapositiva
- **Plan dentro de las restricciones:** 22.000 € (rango del brief: 18.000–27.000 €), responsables del equipo real, cada acción enlazada a sus hallazgos.
- **Proyección por fases** (`simulate_plan`, rendimientos decrecientes, esperado [mínimo–máximo]):
  - Fase 0 · Fundamentos (sem. 1–6): 27,0 [26,3–27,8].
  - Fase 1 · Quick wins (sem. 7–14): 27,7 [26,6–29,0].
  - Fase 2 · Autoridad y escala (sem. 15–30): 30,5 [27,8–33,4].
  - Fase 3 · Optimización y medición (sem. 31–42): **30,8 [27,8–34,0]**.
- **Escenarios:** mínimo viable, equilibrado y completo, re-simulados en `domain/` (en la API: PENDIENTE).
- Es una estimación técnica de visibilidad, no una promesa de pacientes.

> **Guion del presentador (Demo):**  
> *«Si se ejecuta el plan completo, el modelo proyecta pasar de 25,9 a 30,8, con un rango de 27,8 a 34. No inflamos: cada acción extra en el mismo segmento rinde menos».*

---

## Slide 9: Seguimiento con método

### Título
**Solo contamos lo que sale del margen de error**

### Contenido de la diapositiva
- **Re-medición:** `POST /studies/{id}/remeasure` repite el estudio con el mismo brief y el mismo mercado confirmado.
- **Comparabilidad:** misma metodología, misma versión del score, misma huella del banco de preguntas y mismos motores; si cambia el modelo de un motor, se avisa.
- **Sin ruido:** el kit medido dos veces da exactamente «Sin cambios fuera del margen de error». Con un segundo punto sintético perturbado, el score sube +15,88 [+9,51; +22,47] y pasa del 8.º al 3.º: eso sí se informa.
- **Indicadores adelantados:** citas a la web propia 5,85 %, presencia en las 5 fuentes principales 74,1 %, 0 inexactitudes y 21 afirmaciones a revisar por la clínica.
- **Serie en la API y la web:** PENDIENTE (dominio y golden listos).

> **Guion del presentador (Demo):**  
> *«Esto es lo que paga el cliente cada trimestre: no un número nuevo, sino saber si ha cambiado algo de verdad frente a sus competidores».*

---

## Slide 10: Validación y próximos pasos

### Título
**Rigor comprobable y lo que falta**

### Contenido de la diapositiva
- **Validación:** cifras canónicas fijadas por golden (25,93; 8.ª de 10; 25,9 → 30,8) y e2e contra la API; 100 % de hallazgos con `evaluation_ids` y de acciones con `finding_ids` (lo valida el esquema).
- **Límites declarados:** kit sintético; intervalos algo optimistas porque las repeticiones de un prompt se parecen; los IC no cubren el error del juez.
- **Próximos pasos:** primera medición real para fijar el coste por medición, calibración de Jev, serie y escenarios en la web, precio de la suscripción.

> **Guion del presentador (Demo):**  
> *«posiq. convierte días de consultoría manual en minutos, con cifras que se pueden auditar y un seguimiento que solo habla cuando hay algo que contar. Gracias».*
