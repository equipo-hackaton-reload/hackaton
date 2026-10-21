/**
 * Estudios en memoria del mock. Cada estudio avanza por el grafo cuando vence `listoEn`:
 * brief → revisión de competidores → medición → revisión del plan → propuesta.
 */
import type { Revision, StudyStatus } from "../types/api";
import type { EstadoEstudio, Market, MetricsDelta, ModoEstudio, Plan, Study, Trace } from "../types/schemas";
import type { PlanQuality, SimulationResult } from "../types/api";
import {
  findingsFor,
  kitBrief,
  kitMarket,
  metricsFor,
  planFor,
  proposalFor,
  qualityFor,
  simulationFor,
  tracesFor,
  violaciones,
} from "./data";

type Etapa = "brief" | "competidores" | "medicion" | "plan" | "propuesta" | "completado";

interface Registro {
  study: Study;
  etapa: Etapa;
  listoEn: number;
  market?: Market;
  plan?: Plan;
  simulacion?: SimulationResult;
  calidad_plan?: PlanQuality;
  metrics_delta?: MetricsDelta;
}

const SIGUIENTE: Partial<Record<Etapa, Etapa>> = {
  brief: "competidores",
  medicion: "plan",
  propuesta: "completado",
};

const ESTADO: Record<Etapa, EstadoEstudio> = {
  brief: "en_curso",
  competidores: "esperando_revision_competidores",
  medicion: "en_curso",
  plan: "esperando_revision_plan",
  propuesta: "en_curso",
  completado: "completado",
};

const REVISION: Partial<Record<Etapa, Revision>> = { competidores: "competidores", plan: "plan" };

const CLAVE = "posiq-mock-db";
// En el navegador el mock sobrevive a recargar la página; en los tests empieza vacío.
const almacen = typeof sessionStorage !== "undefined" && import.meta.env.MODE !== "test" ? sessionStorage : null;

function cargar(): Map<string, Registro> {
  try {
    return new Map(JSON.parse(almacen?.getItem(CLAVE) ?? "[]") as [string, Registro][]);
  } catch {
    return new Map();
  }
}

function guardar(): void {
  try {
    almacen?.setItem(CLAVE, JSON.stringify([...estudios]));
  } catch {
    // Sin almacenamiento (modo privado, cuota): el mock sigue en memoria.
  }
}

const estudios = cargar();
let contador = estudios.size;

/** Milisegundos que tarda cada tramo del grafo simulado (0 en tests). */
export const config = { pasoMs: 4500 };

export function resetDb(): void {
  estudios.clear();
  contador = 0;
  guardar();
}

export function crear(modo: ModoEstudio): string {
  contador += 1;
  const id = `S-${Date.now().toString(36)}-${contador}`;
  estudios.set(id, {
    study: {
      id,
      brand_id: "clinica-alborada-vision",
      brief: kitBrief,
      modo,
      creado_en: new Date().toISOString(),
      version_metodologia: "kit-2026.1",
      score_version: "1.0",
      estado: "en_curso",
    },
    etapa: "brief",
    listoEn: Date.now() + config.pasoMs,
  });
  guardar();
  return id;
}

function avanzar(r: Registro): void {
  const siguiente = SIGUIENTE[r.etapa];
  if (siguiente && Date.now() >= r.listoEn) {
    r.etapa = siguiente;
    if (siguiente === "competidores") r.market = structuredClone(kitMarket);
    if (siguiente === "plan" && !r.plan) {
      r.plan = planFor(r.study.id, metricsFor(r.study.id, r.market!));
      const metrics = metricsFor(r.study.id, r.market!);
      r.simulacion = simulationFor(r.study.id, metrics, r.plan);
      r.calidad_plan = qualityFor(r.study.id, r.plan);
    }
    guardar();
  }
  r.study = { ...r.study, estado: ESTADO[r.etapa] };
}

const FASE: Record<Etapa, 0 | 1 | 2 | 3> = {
  brief: 0,
  competidores: 1,
  medicion: 1,
  plan: 2,
  propuesta: 2,
  completado: 3,
};

export function trazas(id: string): Trace[] | undefined {
  const r = estudios.get(id);
  if (!r) return undefined;
  avanzar(r);
  const fase = FASE[r.etapa];
  if (fase === 0) return [];
  return tracesFor(r.study.modo, fase).map((t) => ({ ...t, study_id: id, fecha: r.study.creado_en }));
}

export function estado(id: string): StudyStatus | undefined {
  const r = estudios.get(id);
  if (!r) return undefined;
  avanzar(r);
  const coste = (trazas(id) ?? []).reduce((s, t) => s + t.coste_eur, 0);
  const out: StudyStatus = {
    study: r.study,
    estado: r.study.estado,
    revision_pendiente: REVISION[r.etapa] ?? null,
    coste_acumulado_eur: Math.round(coste * 10000) / 10000,
    errores: [],
  };
  if (r.etapa === "brief") return out;
  out.brief = kitBrief;
  out.market = r.market;
  if (r.etapa === "competidores" || r.etapa === "medicion") return out;
  const metrics = metricsFor(id, r.market!);
  const findings = findingsFor(id);
  out.metrics = metrics;
  out.findings = findings;
  out.plan = r.plan;
  out.simulacion = r.simulacion;
  out.calidad_plan = r.calidad_plan;
  out.metrics_delta = r.metrics_delta;
  if (r.etapa === "plan") out.errores = violaciones(r.plan!, kitBrief);
  if (r.etapa === "completado") {
    out.proposal = proposalFor(id, r.study.modo, metrics, findings, r.plan!, r.study.creado_en);
  }
  return out;
}

export type ResultadoResume = "ok" | "no_existe" | "fuera_de_turno";

export function reanudar(id: string, revision: Revision, payload: Market | Plan): ResultadoResume {
  const r = estudios.get(id);
  if (!r) return "no_existe";
  avanzar(r);
  if (REVISION[r.etapa] !== revision) return "fuera_de_turno";
  if (revision === "competidores") {
    r.market = { ...(payload as Market), confirmado_por_humano: true };
    r.etapa = "medicion";
  } else {
    r.plan = payload as Plan;
    r.etapa = "propuesta";
    const metrics = metricsFor(id, r.market ?? kitMarket);
    r.simulacion = simulationFor(id, metrics, r.plan);
    r.calidad_plan = qualityFor(id, r.plan);
  }

  r.listoEn = Date.now() + config.pasoMs;
  r.study = { ...r.study, estado: ESTADO[r.etapa] };
  guardar();
  return "ok";
}

export function remeasure(id: string): string | undefined {
  const original = estudios.get(id);
  if (!original) return undefined;
  contador += 1;
  const nuevoId = `${id}-remeasure-${contador}`;
  const metrics = metricsFor(nuevoId, original.market ?? kitMarket);
  const scoreAnterior = metricsFor(id, original.market ?? kitMarket).score_global.score;
  estudios.set(nuevoId, {
    study: { ...original.study, id: nuevoId, creado_en: new Date().toISOString(), estado: "completado" },
    etapa: "completado",
    listoEn: Date.now(),
    market: structuredClone(original.market ?? kitMarket),
    plan: original.plan,
    simulacion: original.plan ? simulationFor(nuevoId, metrics, original.plan) : undefined,
    calidad_plan: original.plan ? qualityFor(nuevoId, original.plan) : undefined,
    metrics_delta: {
      study_id: nuevoId,
      comparado_con: id,
      marca_foco_id: metrics.marca_foco_id,
      score_actual: metrics.score_global.score,
      score_anterior: scoreAnterior,
      // El kit es fijo: la re-medición repite las mismas respuestas y el delta sale de restar.
      score_delta:
        metrics.score_global.score == null || scoreAnterior == null
          ? null
          : Math.round((metrics.score_global.score - scoreAnterior) * 100) / 100,
      visibilidad_delta: [],
      comparable: true,
      avisos: ["Datos del kit: la re-medición repite las mismas respuestas, así que no hay cambio real."],
    },
  });
  guardar();
  return nuevoId;
}

export function listar(brandId: string | null): Study[] {
  return [...estudios.values()]
    .map((r) => r.study)
    .filter((s) => !brandId || s.brand_id === brandId)
    .sort((a, b) => b.creado_en.localeCompare(a.creado_en));
}

export function existe(id: string): boolean {
  return estudios.has(id);
}

export function etapa(id: string): Etapa | undefined {
  return estudios.get(id)?.etapa;
}
