/**
 * Estudios en memoria del mock. Cada estudio avanza por el grafo cuando vence `listoEn`:
 * brief → revisión de competidores → medición → revisión del plan → propuesta.
 * Una re-medición salta directamente de la medición a completado.
 *
 * Cada estudio tiene propietario (`owner`, el id del usuario que lo crea), como la tabla de
 * propiedad study_id → user_id de la API: los handlers responden 404 a quien no lo es.
 */
import type { PlanQuality, Revision, SimulationResult, StudyStatus } from "../types/api";
import type { EstadoEstudio, Market, MetricsDelta, ModoEstudio, Plan, Study, Trace } from "../types/schemas";
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

type Etapa = "brief" | "competidores" | "medicion" | "plan" | "propuesta" | "remedicion" | "completado";

interface Registro {
  study: Study;
  owner: string;
  etapa: Etapa;
  listoEn: number;
  market?: Market;
  plan?: Plan;
  simulacion?: SimulationResult;
  calidad_plan?: PlanQuality;
  metrics_delta?: MetricsDelta;
  /** Estudio del que es re-medición. */
  remedicion_de?: string;
  /** El grafo se ha detenido con este error (estado `error` de la API). */
  error?: string;
}

const SIGUIENTE: Partial<Record<Etapa, Etapa>> = {
  brief: "competidores",
  medicion: "plan",
  propuesta: "completado",
  remedicion: "completado",
};

const ESTADO: Record<Etapa, EstadoEstudio> = {
  brief: "en_curso",
  competidores: "esperando_revision_competidores",
  medicion: "en_curso",
  plan: "esperando_revision_plan",
  propuesta: "en_curso",
  remedicion: "en_curso",
  completado: "completado",
};

const REVISION: Partial<Record<Etapa, Revision>> = { competidores: "competidores", plan: "plan" };

const CLAVE = "posiq-mock-db-v2";
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

export function crear(modo: ModoEstudio, owner: string): string {
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
    owner,
    etapa: "brief",
    listoEn: Date.now() + config.pasoMs,
  });
  guardar();
  return id;
}

function avanzar(r: Registro): void {
  const siguiente = SIGUIENTE[r.etapa];
  if (siguiente && !r.error && Date.now() >= r.listoEn) {
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
  remedicion: 1,
  plan: 2,
  propuesta: 2,
  completado: 3,
};

/** ¿Existe el estudio y es de `owner`? Si no, la API responde 404 (no revela que existe). */
export function esDe(id: string, owner: string): boolean {
  return estudios.get(id)?.owner === owner;
}

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
    estado: r.error ? "error" : r.study.estado,
    revision_pendiente: r.error ? null : (REVISION[r.etapa] ?? null),
    coste_acumulado_eur: Math.round(coste * 10000) / 10000,
    errores: r.error ? [r.error] : [],
  };
  if (r.etapa === "brief") return out;
  out.brief = kitBrief;
  out.market = r.market;
  if (r.etapa === "competidores" || r.etapa === "medicion" || r.etapa === "remedicion") return out;
  const metrics = metricsFor(id, r.market!);
  const findings = findingsFor(id);
  out.metrics = metrics;
  out.findings = findings;
  out.plan = r.plan;
  out.simulacion = r.simulacion;
  out.calidad_plan = r.calidad_plan;
  out.metrics_delta = r.metrics_delta;
  if (r.etapa === "plan" && !r.error) out.errores = violaciones(r.plan!, kitBrief);
  if (r.etapa === "completado" && r.plan) {
    out.proposal = proposalFor(id, r.study.modo, metrics, findings, r.plan, r.study.creado_en);
  }
  return out;
}

/** Para los tests y la demo: el grafo se detiene con un error. */
export function fallar(id: string, mensaje: string): void {
  const r = estudios.get(id);
  if (r) r.error = mensaje;
  guardar();
}

/** Para los tests: deja el estudio completado sin recorrer el grafo. */
export function completar(id: string): void {
  const r = estudios.get(id);
  if (!r) return;
  r.market = r.market ?? structuredClone(kitMarket);
  const metrics = metricsFor(id, r.market);
  r.plan = r.plan ?? planFor(id, metrics);
  r.etapa = "completado";
  r.study = { ...r.study, estado: "completado" };
  guardar();
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

export function modo(id: string): ModoEstudio | undefined {
  return estudios.get(id)?.study.modo;
}

export type ResultadoRemedicion = { study_id: string; remedicion_de: string } | "no_existe" | "no_completado" | "en_curso";

export function remeasure(id: string): ResultadoRemedicion {
  const original = estudios.get(id);
  if (!original) return "no_existe";
  avanzar(original);
  if (original.etapa !== "completado") return "no_completado";
  const enCurso = [...estudios.values()].some((r) => {
    if (r.remedicion_de !== id) return false;
    avanzar(r);
    return r.etapa !== "completado" && !r.error;
  });
  if (enCurso) return "en_curso";

  contador += 1;
  const nuevoId = `${id}-remeasure-${contador}`;
  const metrics = metricsFor(nuevoId, original.market ?? kitMarket);
  const scoreAnterior = metricsFor(id, original.market ?? kitMarket).score_global.score;
  estudios.set(nuevoId, {
    study: { ...original.study, id: nuevoId, creado_en: new Date().toISOString(), estado: "en_curso" },
    // La re-medición hereda el propietario del estudio original.
    owner: original.owner,
    etapa: "remedicion",
    listoEn: Date.now() + config.pasoMs,
    remedicion_de: id,
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
  return { study_id: nuevoId, remedicion_de: id };
}

/** Estudios de `owner`, del más reciente al más antiguo. */
export function listar(owner: string, brandId: string | null): Study[] {
  return [...estudios.values()]
    .filter((r) => r.owner === owner)
    .map((r) => {
      avanzar(r);
      return r.study;
    })
    .filter((s) => !brandId || s.brand_id === brandId)
    .sort((a, b) => b.creado_en.localeCompare(a.creado_en));
}

/** Estudios completados de `owner` para una marca, del más antiguo al más reciente. */
export function completados(owner: string, brandId: string): { study: Study; market: Market }[] {
  return [...estudios.values()]
    .filter((r) => r.owner === owner && r.study.brand_id === brandId)
    .filter((r) => {
      avanzar(r);
      return r.etapa === "completado" && !r.error;
    })
    .map((r) => ({ study: r.study, market: r.market ?? kitMarket }))
    .sort((a, b) => a.study.creado_en.localeCompare(b.study.creado_en));
}

export function etapa(id: string): Etapa | undefined {
  return estudios.get(id)?.etapa;
}
