import type { StudyStatus } from "../types/api";
import type { EstadoEstudio, FaseEmbudo, Market, Metrics, Palanca, Rol } from "../types/schemas";

export const ESTADO_LABEL: Record<EstadoEstudio, string> = {
  en_curso: "En curso",
  esperando_revision_competidores: "Esperando revisión de competidores",
  esperando_revision_plan: "Esperando revisión del plan",
  completado: "Completado",
};

export const ROL_LABEL: Record<Rol, string> = { foco: "Foco", contexto: "Contexto", lider: "Líder" };

export const FASE_LABEL: Record<FaseEmbudo, string> = {
  descubrimiento: "Descubrimiento",
  comparacion: "Comparación",
  validacion: "Validación",
  decision: "Decisión",
};

export const PALANCA_LABEL: Record<Palanca, string> = {
  autoridad_terceros: "Autoridad de terceros",
  entidad_datos: "Entidad y datos",
  contenido: "Contenido",
  reputacion: "Reputación",
  comunidades: "Comunidades",
  tecnico: "Técnico",
  medicion: "Medición",
};

/** Pantalla a la que lleva el estado actual del estudio. */
export function pantallaActual(s: StudyStatus): Pantalla {
  if (s.estado === "completado") return "propuesta";
  if (s.revision_pendiente === "plan") return "plan";
  if (s.revision_pendiente === "competidores" || !s.market) return "competidores";
  // En curso: midiendo (sin métricas o sin plan) o redactando la propuesta tras aprobar el plan.
  if (!s.metrics || !s.plan) return "diagnostico";
  return "propuesta";
}

export type Pantalla = "competidores" | "diagnostico" | "plan" | "propuesta";

/** Pantallas que ya tienen algo que mostrar. */
export function disponibles(s: StudyStatus): Set<Pantalla> {
  const out = new Set<Pantalla>(["competidores"]);
  if (s.market?.confirmado_por_humano || s.metrics) out.add("diagnostico");
  if (s.plan) out.add("plan");
  if (s.estado === "completado" || (s.plan && s.estado === "en_curso")) out.add("propuesta");
  return out;
}

export function nombres(market: Market | undefined): (id: string) => string {
  const m = new Map(market?.marcas.map((b) => [b.id, b.nombre]));
  return (id) => m.get(id) ?? id;
}

export function scoreDe(m: Metrics, brandId: string | null | undefined): number | null {
  return m.scores.find((s) => s.brand_id === brandId)?.score ?? null;
}
