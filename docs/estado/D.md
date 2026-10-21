# Zona D · web (`apps/web/`)

## En develop
- React + Vite: nuevo estudio, competidores, diagnóstico, plan y propuesta; sondeo del estado,
  revisiones editables, evidencias por hallazgo y trazas. Mocks MSW con cifras del dominio. Job `web` en CI.
- Consume `/studies`, `/studies/{id}`, `/resume`, `/traces`, `/evaluations` y `GET /estimate`.
- La tarjeta de simulación y calidad del plan ya están conectadas a los campos opcionales de C;
  el mock incluye rangos por fase y calidad por acción.
- El diagnóstico ya ofrece re-medición mock y vista del delta; queda probarlo cuando C publique
  `POST /studies/{id}/remeasure`.

- Aviso del modo kit: `POST /studies` devuelve `aviso` (solo en kit); `NewStudyPage` lo guarda
  por estudio en sessionStorage (`lib/avisoKit.ts`) y `CompetitorsPage` lo enseña con
  `components/AvisoKit.tsx`. Hecho por zona C con autorización; los mocks aún no lo devuelven.

## Falta
- Probar la integración con la API de C usando `LLM_PROVIDER=fixture`.
- Pulir la interfaz, ejecutar build de producción y capturar la demo.

## Siguiente tarea
- `feature/D-simulacion`: mock implementado; pendiente validación contra la API real y capturas.

## No tocar
- No calcular cifras en el front: se pintan las que da la API.

## Para Claudia: «Lo que nos habéis pedido» (trazabilidad brief → propuesta, ADR 0013)
`GET /studies/{id}` → `proposal.encargo` (no se ha tocado `apps/web/`). Es `null` en propuestas
antiguas.

```json
"encargo": null | {
  "objetivos": ["..."], "restricciones": ["..."], "servicios_prioritarios": ["..."],
  "ciudades": ["Madrid", "Barcelona"], "publicos": ["..."], "competidores_declarados": ["..."],
  "presupuesto_anual_eur": [18000, 27000] | null,
  "cobertura": [
    {"id": "ciudad-1", "tipo": "ciudad", "texto": "Madrid",
     "accion_ids": ["A0-1", "A2-1"], "hallazgo_ids": [],
     "estado": "cubierto" | "pendiente", "motivo": ""}
  ]
}
```

- `tipo`: `objetivo`, `restriccion`, `servicio_prioritario`, `ciudad`, `publico`, `competidor`,
  `presupuesto`. Los ids de `accion_ids` y `hallazgo_ids` existen en `proposal.plan` y en
  `proposal.hallazgos` (lo valida el esquema).
- En restricciones y presupuesto, `motivo` explica la comprobación («La declaran todas las acciones
  del plan.», «Plan de 22.000 €, dentro del máximo de 27.000 €.»). En los pendientes dice por qué.
- Propuesta para la web: un bloque al principio de la propuesta con las listas literales y una
  tabla punto → dónde se trata (enlazando a la acción o al hallazgo), con «pendiente» en ámbar.
  Las cifras no se recalculan en el front.
