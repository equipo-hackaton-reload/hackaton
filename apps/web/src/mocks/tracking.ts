/**
 * Seguimiento del mock: `GET /brands` y `GET /brands/{id}/serie` a partir de los estudios
 * completados del usuario. Simula lo que hará el dominio (`domain/tracking_schemas.py`): la web no
 * calcula ninguna de estas cifras, solo las pinta.
 *
 * Con el kit cada re-medición repite las mismas respuestas, así que entre estudios del kit no hay
 * cambios significativos. La cuenta de demostración trae además dos mediciones históricas de
 * ejemplo para que se vea una serie con un cambio de método y un cambio significativo.
 */
import type { Market, Metrics } from "../types/schemas";
import type {
  BrandSummary,
  CambioSerie,
  IndicadorAdelantado,
  Intervalo,
  PuntoSerie,
  SerieMarca,
  Significancia,
} from "../types/tracking";
import { SIN_CAMBIOS } from "../types/tracking";
import { metricsFor } from "./data";
import * as db from "./db";

const MOTORES = ["ChatGPT", "Gemini", "Perplexity", "Claude"] as const;
const MODELOS_KIT = { ChatGPT: "kit", Gemini: "kit", Perplexity: "kit", Claude: "kit" };
const BANCO_KIT = "kit-624:9c41e2";
/** Semiamplitud del intervalo bootstrap del score con el kit (la calcula el dominio en la API). */
const MARGEN_SCORE = 3.4;
const MARGEN_DELTA = 4.8;

const r2 = (n: number) => Math.round(n * 100) / 100;
const es = (n: number, d = 2) => n.toFixed(d).replace(".", ",");

function intervalo(valor: number, margen: number, n: number): Intervalo {
  return { valor: r2(valor), inf: r2(valor - margen), sup: r2(valor + margen), n, nivel: 0.95, metodo: "bootstrap" };
}

function significancia(delta: number): Significancia {
  const iv = intervalo(delta, MARGEN_DELTA, 624);
  return { delta: r2(delta), intervalo: iv, p_valor: null, significativa: !(iv.inf <= 0 && 0 <= iv.sup) };
}

function tasaGlobal(m: Metrics): number | null {
  return (
    m.visibilidad.find((v) => v.brand_id === m.marca_foco_id && v.tipo === "espontaneo" && v.dimension === "global")?.tasa ??
    null
  );
}

function punto(studyId: string, fecha: string, market: Market): PuntoSerie {
  const m = metricsFor(studyId, market);
  const score = m.score_global.score;
  const otros = m.scores.filter((s) => s.brand_id !== m.marca_foco_id && s.score != null).map((s) => s.score!);
  const media = otros.length ? r2(otros.reduce((a, b) => a + b, 0) / otros.length) : null;
  const puesto = m.ranking.indexOf(m.marca_foco_id) + 1;
  return {
    study_id: studyId,
    fecha,
    score,
    intervalo: score == null ? null : intervalo(score, MARGEN_SCORE, 624),
    posicion: puesto || null,
    n_marcas: m.ranking.length,
    score_medio_competidores: media,
    diferencia_vs_competidores: score != null && media != null ? r2(score - media) : null,
    version_metodologia: "kit-2026.1",
    score_version: m.score_version,
    banco_prompts: BANCO_KIT,
    motores: [...MOTORES],
    modelos_motor: MODELOS_KIT,
    comparable_con_anterior: true,
    motivos_no_comparable: [],
    avisos: ["Datos sintéticos del kit."],
  };
}

/** Dos mediciones de ejemplo anteriores al primer estudio de la cuenta demo. */
function historiaDemo(): PuntoSerie[] {
  const base = {
    n_marcas: 10,
    version_metodologia: "kit-2026.1",
    score_version: "1.0",
    banco_prompts: BANCO_KIT,
    motores: [...MOTORES],
    avisos: ["Medición de ejemplo del mock."],
  };
  return [
    {
      ...base,
      study_id: "S-demo-2026T1",
      fecha: "2026-01-20T10:00:00Z",
      score: 17.8,
      intervalo: intervalo(17.8, 3.1, 624),
      posicion: 9,
      score_medio_competidores: 34.1,
      diferencia_vs_competidores: -16.3,
      modelos_motor: { ChatGPT: "gpt-4o", Gemini: "gemini-2.0-flash", Perplexity: "sonar", Claude: "claude-sonnet-4" },
      comparable_con_anterior: true,
      motivos_no_comparable: [],
    },
    {
      ...base,
      study_id: "S-demo-2026T2",
      fecha: "2026-04-21T10:00:00Z",
      score: 19.2,
      intervalo: intervalo(19.2, 3.2, 624),
      posicion: 9,
      score_medio_competidores: 34.6,
      diferencia_vs_competidores: -15.4,
      modelos_motor: { ChatGPT: "gpt-4.1", Gemini: "gemini-2.0-flash", Perplexity: "sonar", Claude: "claude-sonnet-4" },
      comparable_con_anterior: false,
      motivos_no_comparable: ["Cambió el modelo de ChatGPT (gpt-4o → gpt-4.1)"],
    },
  ];
}

function textoCambio(desde: number, hasta: number, s: Significancia, relativo: boolean): string {
  const verbo = hasta > desde ? "sube" : hasta < desde ? "baja" : "se mantiene";
  const sujeto = relativo ? "La diferencia con la media de competidores" : "El Score de Citación";
  const margen = s.significativa ? "fuera del margen de error" : "dentro del margen de error";
  if (verbo === "se mantiene") return `${sujeto} se mantiene en ${es(hasta)} puntos, ${margen}.`;
  return `${sujeto} ${verbo} ${es(Math.abs(hasta - desde))} puntos (de ${es(desde)} a ${es(hasta)}), ${margen}.`;
}

function cambios(puntos: PuntoSerie[]): CambioSerie[] {
  const out: CambioSerie[] = [];
  for (let i = 1; i < puntos.length; i++) {
    const a = puntos[i - 1];
    const b = puntos[i];
    if (!b.comparable_con_anterior) continue;
    if (a.score != null && b.score != null) {
      const s = significancia(b.score - a.score);
      out.push({
        desde_study_id: a.study_id,
        hasta_study_id: b.study_id,
        metrica: "score",
        delta: s.delta,
        significancia: s,
        significativo: s.significativa,
        relativo_a_competidores: false,
        texto: textoCambio(a.score, b.score, s, false),
      });
    }
    if (a.diferencia_vs_competidores != null && b.diferencia_vs_competidores != null) {
      const s = significancia(b.diferencia_vs_competidores - a.diferencia_vs_competidores);
      out.push({
        desde_study_id: a.study_id,
        hasta_study_id: b.study_id,
        metrica: "diferencia_vs_competidores",
        delta: s.delta,
        significancia: s,
        significativo: s.significativa,
        relativo_a_competidores: true,
        texto: textoCambio(a.diferencia_vs_competidores, b.diferencia_vs_competidores, s, true),
      });
    }
  }
  return out;
}

function indicadores(puntos: PuntoSerie[], tasas: Map<string, number | null>): IndicadorAdelantado[] {
  const demo: Record<string, [number, number, number]> = {
    "S-demo-2026T1": [0.29, 1, 3],
    "S-demo-2026T2": [0.33, 2, 3],
  };
  const val = (id: string, k: 0 | 1 | 2, kit: number | null) => (id in demo ? demo[id][k] : kit);
  return [
    {
      clave: "tasa_espontanea",
      nombre: "Aparición espontánea",
      unidad: "fraccion",
      valores: puntos.map((p) => ({ study_id: p.study_id, valor: val(p.study_id, 0, tasas.get(p.study_id) ?? null) })),
    },
    {
      clave: "fuentes_autoridad",
      nombre: "Fuentes de autoridad que citan la marca",
      unidad: "recuento",
      valores: puntos.map((p) => ({ study_id: p.study_id, valor: val(p.study_id, 1, 4) })),
    },
    {
      clave: "menciones_negativas",
      nombre: "Menciones negativas",
      unidad: "recuento",
      valores: puntos.map((p) => ({ study_id: p.study_id, valor: val(p.study_id, 2, 2) })),
    },
  ];
}

export function serie(owner: string, brandId: string, demo: boolean): SerieMarca | undefined {
  const estudios = db.listar(owner, brandId);
  if (estudios.length === 0) return undefined;
  const hechos = db.completados(owner, brandId);
  const tasas = new Map<string, number | null>();
  const reales = hechos.map(({ study, market }) => {
    tasas.set(study.id, tasaGlobal(metricsFor(study.id, market)));
    return punto(study.id, study.creado_en, market);
  });
  const puntos = demo && reales.length > 0 ? [...historiaDemo(), ...reales] : reales;
  const todos = cambios(puntos);
  const significativos = todos.filter((c) => c.significativo);
  return {
    brand_id: brandId,
    nombre: estudios[0].brief.marca,
    puntos,
    cambios: todos,
    cambios_significativos: significativos,
    indicadores: puntos.length ? indicadores(puntos, tasas) : [],
    resumen: significativos.length ? significativos.map((c) => c.texto) : [SIN_CAMBIOS],
  };
}

export function marcas(owner: string, demo: boolean): BrandSummary[] {
  const porMarca = new Map<string, BrandSummary>();
  for (const s of db.listar(owner, null)) {
    if (!porMarca.has(s.brand_id)) {
      const hechos = db.completados(owner, s.brand_id);
      const extra = demo && hechos.length > 0 ? historiaDemo().length : 0;
      porMarca.set(s.brand_id, {
        brand_id: s.brand_id,
        nombre: s.brief.marca,
        n_mediciones: hechos.length + extra,
        ultima_medicion: hechos.length ? hechos[hechos.length - 1].study.creado_en : null,
      });
    }
  }
  return [...porMarca.values()];
}
