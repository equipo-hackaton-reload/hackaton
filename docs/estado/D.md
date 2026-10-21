# Zona D · web (`apps/web/`)

## En develop
- React + Vite: nuevo estudio, competidores, diagnóstico, plan y propuesta; sondeo del estado,
  revisiones editables, evidencias por hallazgo y trazas. Mocks MSW con cifras del dominio. Job `web` en CI.
- Consume `/studies`, `/studies/{id}`, `/resume`, `/traces`, `/evaluations` y `GET /estimate`.
- La tarjeta de simulación y calidad del plan ya están conectadas a los campos opcionales de C;
  el mock incluye rangos por fase y calidad por acción.

## En `feature/D-cuentas-seguimiento` (PR abierta, sin fusionar)
- Rebasada sobre develop con #35, #36 y #37. Cuentas contra `/auth/*` de la API (mocks MSW con
  los mismos `detail` en `src/mocks/auth.ts` y `handlers.ts`): registro → verificación con código (la web solo enseña
  `codigo_dev` si la API lo devuelve) → login con token Bearer. Token en sessionStorage, o
  localStorage con «Recordarme». `api/client.ts` envía `Authorization` y, ante un 401, limpia la
  sesión y vuelve a `/login?next=<ruta>`. «Salir» llama a `POST /auth/logout`. La caché de TanStack
  Query se vacía al cambiar de usuario.
- Seguimiento: `/marcas` (`GET /brands`) y `/marcas/:brandId` (`GET /brands/{id}/serie`): gráfico
  SVG del score con banda del intervalo y media de competidores (las líneas se cortan en los puntos
  no comparables, marcados con círculo hueco y motivo), resumen, lista solo de
  `cambios_significativos` («Sin cambios fuera del margen de error» si no hay), tabla de mediciones e
  indicadores adelantados. No se calcula ninguna cifra: se pinta `SerieMarca`.
- «Volver a medir» (diagnóstico y seguimiento): `GET /studies/{id}/remeasure/estimate`, diálogo con
  el coste y `POST /remeasure {confirmado: true, coste_estimado_eur}`. Ante 409 vuelve a pedir la
  estimación: si cambió, enseña el coste nuevo; si no, avisa de que ya hay una re-medición en curso.
- Arreglos de la auditoría: estado `error` (aviso con `errores`, «Volver a comprobar», sin spinner
  infinito), fallo puntual del sondeo sin tapar la pantalla, estimación también en kit y
  confirmación explícita en real si supera el tope, KPI de fracción como porcentaje y borrador del
  plan que sobrevive al cambio de pestaña (`lib/planDraft.ts`).
- Degradación sin las rutas de seguimiento: un 404 «Not Found» de FastAPI (`rutaNoDisponible` en
  `api/client.ts`) en `/brands` o `/brands/{id}/serie` muestra «Seguimiento no disponible todavía»
  sin «Reintentar»; sin `/remeasure/estimate`, solo en modo kit (0 €) el diálogo usa `GET /estimate`
  y lo avisa («estimación aproximada»); en modo real no deja confirmar (`RemedicionRealNoDisponible`)
  porque `POST /remeasure` aún no valida `confirmado` ni el coste y no se lanza gasto de pago con una
  cifra aproximada. TanStack Query ya no reintenta los 4xx. Estimación con el
  desglose de #37 (motores, LLM, juez, PlanGuard; kit a 0 €).
- Probado de punta a punta con la API real (fixture, kit, BD temporal, `VITE_USE_MOCKS=false`):
  registro → verificación con `codigo_dev` → login → estudio kit → competidores → diagnóstico
  (25,93; 8.ª de 10) → plan → propuesta, y «Volver a medir» crea la re-medición.
- Tipos: `types/auth.ts`, `types/tracking.ts` (espejo de `domain/tracking_schemas.py`) y `EstadoApi = EstadoEstudio | "error"` en `types/api.ts`. `types/schemas.ts` vuelve a
  estar alineado con `schemas.py` (`Encargo`, `PuntoBrief`, `posicionamiento_deseado`,
  `atributos_deseados`); falta pintar el encargo.

- Aviso del modo kit: `POST /studies` devuelve `aviso` (solo en kit); `NewStudyPage` lo guarda
  por estudio en sessionStorage (`lib/avisoKit.ts`) y `CompetitorsPage` lo enseña con
  `components/AvisoKit.tsx`. Hecho por zona C con autorización; los mocks aún no lo devuelven.

## En `feature/D-identidad-claudia` (PR abierta, sin fusionar)
- Identidad visual de Claudia (commit 64e33cf de `feature/D-web-claudia`) aplicada sobre el login
  real con token (#38): logo de diana en SVG en cabecera, pantallas de cuentas (`AuthLayout`) y
  favicon; paleta cian/magenta/amarillo/coral con carbón #141414; Antonio y Outfit; marcas de
  registro; botón principal cian (login y registro con botón en tinta); franja de aros y pasos con
  viñetas en «Nuevo estudio». No reintroduce el login de cliente antiguo de esa rama.
- Comprobado con Playwright (web 5211, API 8911 en fixture), claro y oscuro: logo en login y
  cabecera, favicon con la diana, sin errores de consola.

## Falta
- Integrar `/brands`, `/brands/{id}/serie` y `/studies/{id}/remeasure/estimate` cuando los publique
  la etapa «Seguimiento API» (zona C; hoy responden 404 y la web degrada). `POST /remeasure` ya existe
  pero ignora `{confirmado, coste_estimado_eur}`: el 409 por coste cambiado solo lo da el mock y la
  única protección del gasto es la de la web. Zona C: validar `confirmado` y `coste_estimado_eur` en el
  servidor y exigir un indicador explícito cuando supere `presupuesto_max_eur`; entonces se puede
  reactivar «Volver a medir» en real sin la ruta de estimación propia; `types/tracking.ts` ya replica `domain/tracking_schemas.py` (#35).
- `Objective` no trae `unidad`: la web la infiere (KPI de tasa con valores 0-1 → porcentaje). Si A
  añade `unidad` al objetivo, la web ya la usa.
- Mostrar `proposal.encargo` (ver abajo).

## Siguiente tarea
- Cuando C publique los endpoints de seguimiento, probar `/marcas` contra la API real y quitar el
  respaldo de la estimación.

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
