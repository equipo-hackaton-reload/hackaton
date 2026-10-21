# Revisión del Documento Word de la Propuesta desde la Perspectiva del Cliente

**Cliente:** Comité de Dirección de Clínica Alborada Visión  
*Perfil de la audiencia:* Dirección médica (oftalmólogos especialistas), dirección general y responsable de marketing.  
*Documento evaluado:* `docs/ejemplos/propuesta_alborada_ejemplo.docx` (y plantilla `src/posiq/adapters/export/templates/propuesta.docx`), con las 11 secciones de `develop` (`1798244`): las diez del formato del entregable más «2. Lo que nos habéis pedido» (ADR 0013).  
*Marco de referencia:* Briefing del cliente (`Brief_de_ejemplo_Clinica_Alborada.md`), Metodología GEO (`02_Metodologia_GEO.md`) y Formato del Entregable (`06_Formato_del_entregable.md`).

---

## 1. Resumen Ejecutivo de la Revisión

Un informe de consultoría para una clínica oftalmológica no puede leerse como un volcado de logs técnicos ni como un manual informático. La propuesta generada por **posiq.** debe poder ser entregada directamente a los directores médicos y al comité de dirección de Clínica Alborada Visión.

La revisión evalúa tres dimensiones críticas:
1. **Lenguaje y Tono:** Claridad conceptual, enfoque a negocio y respeto al rigor médico-asistencial sin tecnicismos superfluos ni frases informáticas informales.
2. **Limitaciones Declaradas:** Transparencia metodológica sobre el carácter estocástico de los LLMs, el uso de datos del kit y la diferenciación nítida entre visibilidad espontánea y asistida.
3. **Conformidad con la Normativa Sanitaria:** Estricto cumplimiento del Real Decreto 1907/1996 sobre publicidad y actividades con pretendida finalidad sanitaria, la Ley 34/1988 General de Publicidad y los códigos deontológicos médicos.

---

## 2. Dimensión 1: Lenguaje, Tono y Enfoque al Cliente

### Situación Detectada en Versiones Previas
- En las primeras implementaciones de prueba, textos como:  
  *«Alborada aparece poco cuando nadie la nombra. Proponemos un plan por fases.»* o *«El líder concentra las recomendaciones.»* resultaban excesivamente telegráficos, con tono de depuración de software.
- Ciertas secciones mostraban anglicismos sin traducir o jerga de desarrollo (*«run_id»*, *«fallback»*, *«decision»* sin tilde).

### Criterio del Cliente y Mejoras Aplicadas
- **Tono institucional y médico:** Redacción sobria, estructurada y fundamentada, adecuada para un comité multidisciplinar donde conviven criterios clínicos de excelencia y objetivos económicos de sostenibilidad.
- **Narrativa estratégica:** En lugar de indicar simplemente que la marca «aparece poco», se contextualiza el comportamiento de los motores: los asistentes de IA reconocen la entidad de Alborada cuando se les pregunta específicamente por ella (100 % en asistida), pero fallan en prescribirla cuando un paciente potencial solicita una recomendación abierta en cirugía refractiva o control de miopía en Madrid o Barcelona (38,8 % en espontánea).
- **Tipografía y lectura:** Se preservan acentos ortográficos (e.g., «Decisión»), tablas ordenadas con separador decimal estándar en español (coma) y nomenclatura oficial de marcas con sus tildes correspondientes («Láser Nítida», «Instituto Oftálmico Tramuntana»).

---

## 3. Dimensión 2: Limitaciones Técnicas y Metodológicas

Un cliente del sector salud exige máxima honestidad en los datos para evitar falsas expectativas comerciales:

| Limitación | Justificación para el Cliente | Declaración en el Documento |
|---|---|---|
| **Datos Sintéticos del Kit** | Los datos del kit del hackathon reproducen fielmente la estructura relacional de un estudio GEO, pero no reflejan las cuotas en vivo de los motores en producción. | Se declara en la portada (aviso destacado) y en la sección 3 (Contexto y alcance). |
| **No Determinismo de los LLMs** | Las respuestas de los modelos de IA generativa varían en función de la temperatura, fecha de corte, contexto de conversación y actualizaciones del índice web. | Se especifica que el estudio constituye una foto fija temporal que requiere monitorización trimestral. |
| **Espontáneo vs. Asistido** | No es comparable la visibilidad asistida (el usuario ya conoce la clínica) con la espontánea (el motor decide prescribirla). | Se enfatiza mediante nota metodológica fija antes de las tablas del diagnóstico. |
| **No Causalidad Comercial** | Un incremento en el Score de Citación GEO representa una mejora en visibilidad digital algorítmica, no una garantía matemática de incremento del +25 % en primeras visitas. | El +25 % de pacientes se explicita como objetivo comercial de Alborada, no como promesa automática del sistema. |
| **Incertidumbre en Fuentes** | Algunas fuentes citadas por los motores no están catalogadas o no permiten atribuir de forma unívoca el tipo de cita a la marca. | Se clasifican como «Fuera del catálogo» con indicación de datos no disponibles («s. d.») en lugar de asumir un 0 %. |

---

## 4. Dimensión 3: Normativa Sanitaria y Publicidad Médica

El sector sanitario en España está fuertemente regulado. Cualquier propuesta que vulnere la legislación expondría a la clínica a sanciones administrativas y descrédito deontológico.

### Requisitos Legales Aplicados:
1. **Real Decreto 1907/1996 sobre publicidad sanitaria:**
   - **Prohibición de garantizar resultados:** Ninguna acción del plan promete «eliminar totalmente las gafas» o «éxito asegurado en cirugía refractiva». Los contenidos (páginas FAQ, guías) se orientan a explicar el procedimiento preoperatorio, los criterios de idoneidad clínica del paciente y los protocolos de seguridad.
   - **Prohibición de testimonios engañosos o prescriptivos:** La acción A1-2 (pedir reseñas a pacientes del centro de Barcelona y responder a todas en menos de 72 horas) debe ejecutarse sin incentivos ni testimonios fabricados; el plan no lo dice expresamente y conviene que la agencia lo añada al protocolo de reseñas.
2. **Ley 34/1988 General de Publicidad y Deontología Médica:**
   - **Sin comparativas denigratorias:** El análisis de la competencia y las acciones de relaciones públicas (A2-1, A2-3) se centran en la presencia legítima de Alborada en directorios y medios de salud especializados, sin desacreditar a Valdecruz, Tramuntana o Láser Nítida.
   - **Firma médica colegiada:** Las acciones de divulgación en medios de salud (A2-3) y vídeos explicativos en YouTube (A3-2) son firmadas y presentadas por los oftalmólogos del cuadro médico de la clínica, asegurando rigor científico.

---

## 5. Dimensión 4: Factibilidad Operativa y Presupuestaria

El plan propuesto en el Word tiene que poder ejecutarse con los recursos reales de Alborada:
- **Presupuesto:** 22.000 €, dentro del rango de 18.000 € a 27.000 € del brief.
- **Equipo humano:**
  - *Responsable de Marketing:* Coordina las acciones A1-1 (FAQ de decisión) y A2-2 (guía del centro de Barcelona).
  - *Comunicación (media jornada):* Asume la gestión de reseñas (A1-2), apoyo en medios (A2-3) y producción de vídeos divulgativos (A3-2).
  - *Agencia colaboradora:* Ejecuta las acciones especializadas de marcado schema.org (A0-2), relaciones públicas en directorios (A2-1) y re-mediciones trimestrales (A0-1, A3-1).

---

## 6. Conclusión de la revisión

El Word que genera **posiq.** se puede entregar a un comité de dirección sanitario si se cumplen tres condiciones:
- Cada contenido del plan pasa revisión médica y jurídica de la clínica antes de publicarse; posiq. no certifica el cumplimiento del RD 1907/1996, solo evita prometer resultados y comparativas denigratorias, como pide el brief.
- Se mantienen declaradas las limitaciones: datos del kit sintéticos, foto en una fecha y visibilidad espontánea separada de la asistida.
- Toda cifra del documento sale de `domain/` (Regla 1); la redacción solo la explica.

Las cifras de Alborada citadas en esta revisión (100 % asistida, 108 de 108; 38,8 % espontánea, 93 de 240) salen de `compute_metrics` sobre el kit.
