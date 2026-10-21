/**
 * Datos del mock: caso Clínica Alborada Visión del kit.
 *
 * `fixtures/` sale de ejecutar el dominio real sobre el kit (`scripts/gen_mock_fixtures.py`):
 * brief, mercado, métricas, hallazgos y evidencias son los que calcula `posiq.domain`. El plan, la
 * propuesta y las trazas son de ejemplo, pero sus cifras actuales se leen de esas métricas.
 */
import type { Evidence, PlanQuality, SimulationResult } from "../types/api";
import type {
  Action,
  BriefSummary,
  Finding,
  Market,
  Metrics,
  ModoEstudio,
  Plan,
  Proposal,
  Trace,
} from "../types/schemas";
import briefJson from "./fixtures/brief.json";
import evidenciasJson from "./fixtures/evidencias.json";
import findingsJson from "./fixtures/findings.json";
import marketJson from "./fixtures/market.json";
import metricsJson from "./fixtures/metrics.json";

export const KIT_STUDY_ID = "S-kit-alborada";

// Los JSON los produce Pydantic; TypeScript infiere tipos más estrechos de los literales.
export const kitBrief = briefJson as unknown as BriefSummary;
export const kitMarket = marketJson as unknown as Market;
export const kitMetrics = metricsJson as unknown as Metrics;
export const kitFindings = findingsJson as unknown as Finding[];
export const kitEvidencias = evidenciasJson as unknown as Record<string, Evidence>;

/** Reasigna el `study_id` (los fixtures se generaron con el del kit). */
function conEstudio<T>(value: T, studyId: string): T {
  return JSON.parse(JSON.stringify(value).replaceAll(KIT_STUDY_ID, studyId)) as T;
}

/** Métricas restringidas a las marcas confirmadas en la revisión 1. */
export function metricsFor(studyId: string, market: Market): Metrics {
  const ids = new Set(market.marcas.map((b) => b.id));
  const m = conEstudio(kitMetrics, studyId);
  const lider = market.marcas.find((b) => b.rol === "lider" && ids.has(b.id))?.id;
  const ranking = m.ranking.filter((id) => ids.has(id));
  return {
    ...m,
    lider_id: lider && ranking.includes(lider) ? lider : (ranking[0] ?? null),
    ranking,
    scores: m.scores.filter((s) => ids.has(s.brand_id)),
    scores_por_motor: m.scores_por_motor.filter((s) => ids.has(s.brand_id)),
    visibilidad: m.visibilidad.filter((c) => ids.has(c.brand_id)),
    calidad_menciones: m.calidad_menciones.filter((c) => ids.has(c.brand_id)),
    top_fuentes: m.top_fuentes.filter((s) => ids.has(s.brand_id)),
  };
}

export function findingsFor(studyId: string): Finding[] {
  return conEstudio(kitFindings, studyId);
}

export function simulationFor(studyId: string, m: Metrics, plan: Plan): SimulationResult {
  const actual = m.score_global.score ?? 0;
  return {
    study_id: studyId,
    marca_foco_id: m.marca_foco_id,
    modelo_version: "simulation-1.0",
    score_actual: actual,
    tasa_espontanea_actual: tasa(m, "global", "global") / 100,
    proyecciones: plan.fases.map((fase, indice) => ({
      fase: fase.nombre,
      indice,
      acciones: fase.acciones.map((action) => action.id),
      tasa_espontanea: {
        minimo: Math.min(1, 0.12 + indice * 0.08),
        esperado: Math.min(1, 0.16 + indice * 0.11),
        maximo: Math.min(1, 0.2 + indice * 0.14),
      },
      score: {
        minimo: Math.min(100, actual + 2 + indice * 4),
        esperado: Math.min(100, actual + 5 + indice * 6),
        maximo: Math.min(100, actual + 8 + indice * 8),
      },
    })),
    segmentos: [
      {
        segmento: "Barcelona",
        dimension: "ciudad",
        n: 30,
        tasa_actual: tasa(m, "ciudad", "Barcelona") / 100,
        delta: { minimo: 0.04, esperado: 0.1, maximo: 0.16 },
        acciones: ["A3", "A5"],
      },
      {
        segmento: "Claude · descubrimiento",
        dimension: "fase_motor",
        n: 24,
        tasa_actual: tasa(m, "motor", "Claude") / 100,
        delta: { minimo: 0.03, esperado: 0.08, maximo: 0.13 },
        acciones: ["A1", "A6"],
      },
    ],
    acciones_sin_efecto: [{ action_id: "A2", motivo: "la palanca «medición» no mueve la visibilidad" }],
    supuestos: [
      "Las acciones se ejecutan en el plazo previsto y mantienen su impacto durante el plan.",
      "La calidad de las menciones se mantiene igual que en la medición actual.",
      "La estimación no es una predicción y debe validarse con re-mediciones.",
    ],
    advertencia: "Estimación orientativa con rangos conservadores; no es una promesa de resultados.",
  };
}

export function qualityFor(studyId: string, plan: Plan): PlanQuality {
  const acciones = plan.fases.flatMap((fase) => fase.acciones).map((action, index) => ({
    action_id: action.id,
    es_especifica: true,
    coherente_con_hallazgo: action.finding_ids.length > 0,
    respeta_restricciones: action.restricciones_revisadas.length === RESTRICCIONES.length,
    realista_para_equipo: true,
    calidad_global: action.id === "A4" ? 2 : 3,
    probabilidades: { "0": 0.02, "1": 0.08, "2": action.id === "A4" ? 0.45 : 0.2, "3": 0.55 },
    confianza: index === 3 ? 0.71 : 0.92,
    por_debajo_umbral: action.id === "A4",
    motivos: action.id === "A4" ? ["No declara todas las restricciones del brief."] : [],
  }));
  return {
    study_id: studyId,
    juez: "fixture-plan-guard",
    modelo: "fixture",
    acciones,
    pct_especificas: 1,
    pct_coherentes: 1,
    pct_respetan_restricciones: 0.86,
    pct_realistas: 1,
    calidad_media: 2.86,
    por_debajo_umbral: ["A4"],
    baja_confianza: [],
    nota: "El plan es accionable, pero conviene revisar A4 antes de aprobarlo.",
  };
}

function tasa(m: Metrics, dimension: "global" | "motor" | "ciudad", valor: string): number {
  const c = m.visibilidad.find(
    (v) =>
      v.brand_id === m.marca_foco_id &&
      v.tipo === "espontaneo" &&
      v.dimension === dimension &&
      v.valor === valor,
  );
  return Math.round((c?.tasa ?? 0) * 1000) / 10;
}

const RESTRICCIONES = kitBrief.restricciones;

type Opcionales = "dependencias" | "restricciones_revisadas" | "fase_embudo" | "motores_objetivo";

function accion(a: Omit<Action, Opcionales> & Partial<Pick<Action, Opcionales>>): Action {
  return {
    dependencias: [],
    restricciones_revisadas: [...RESTRICCIONES],
    fase_embudo: null,
    motores_objetivo: [],
    ...a,
  };
}

export function planFor(studyId: string, m: Metrics): Plan {
  return {
    study_id: studyId,
    objetivos: [
      {
        kpi: "Visibilidad espontánea global (%)",
        valor_actual: tasa(m, "global", "global"),
        valor_objetivo: 55,
        plazo_semanas: 24,
      },
      {
        kpi: "Visibilidad espontánea en Barcelona (%)",
        valor_actual: tasa(m, "ciudad", "Barcelona"),
        valor_objetivo: 20,
        plazo_semanas: 24,
      },
      {
        kpi: "Visibilidad espontánea en Claude (%)",
        valor_actual: tasa(m, "motor", "Claude"),
        valor_objetivo: 35,
        plazo_semanas: 24,
      },
    ],
    fases: [
      {
        nombre: "Base de entidad y medición",
        semanas: 4,
        objetivo: "Que los motores identifiquen la clínica con datos coherentes en todas las fuentes",
        acciones: [
          accion({
            id: "A1",
            descripcion:
              "Unificar nombre, sedes, especialidades y horarios en directorios médicos y comparadores, empezando por directoriomedico.example",
            finding_ids: ["F-fuente-lider", "F-brecha-lider"],
            palanca: "entidad_datos",
            fase_embudo: "descubrimiento",
            motores_objetivo: ["ChatGPT", "Gemini", "Perplexity", "Claude"],
            esfuerzo: "S",
            impacto: "L",
            responsable: "Responsable de marketing",
            entregables: ["Inventario de fichas", "Fichas corregidas en 12 directorios"],
            plazo_semanas: 3,
            kpi: "Citas de directorios con la marca presente",
          }),
          accion({
            id: "A2",
            descripcion: "Panel mensual de visibilidad por motor, ciudad y fase con los prompts del estudio",
            finding_ids: ["F-brecha-lider", "F-motor-debil"],
            palanca: "medicion",
            esfuerzo: "S",
            impacto: "M",
            responsable: "Agencia colaboradora",
            entregables: ["Panel de seguimiento", "Informe mensual"],
            plazo_semanas: 4,
            kpi: "Score de Citación mensual",
          }),
        ],
      },
      {
        nombre: "Autoridad y contenido local",
        semanas: 8,
        objetivo: "Ganar presencia espontánea en Barcelona y en las fases de comparación y decisión",
        acciones: [
          accion({
            id: "A3",
            descripcion:
              "Página propia del centro de Barcelona con equipo médico, tecnología y preguntas frecuentes por tratamiento",
            finding_ids: ["F-ciudad-barcelona"],
            palanca: "contenido",
            fase_embudo: "descubrimiento",
            esfuerzo: "M",
            impacto: "L",
            responsable: "Comunicación",
            dependencias: ["A1"],
            entregables: ["Landing de Barcelona", "8 respuestas a preguntas frecuentes"],
            plazo_semanas: 6,
            kpi: "Visibilidad espontánea en Barcelona",
          }),
          accion({
            id: "A4",
            descripcion:
              "Colaboraciones divulgativas en medios de salud (saludactual.example, diariosalud.example) sobre cirugía refractiva y miopía infantil",
            finding_ids: ["F-fuente-lider", "F-recomendacion-debil"],
            palanca: "autoridad_terceros",
            fase_embudo: "comparacion",
            motores_objetivo: ["Perplexity", "Gemini"],
            esfuerzo: "M",
            impacto: "L",
            responsable: "Agencia colaboradora",
            entregables: ["4 artículos firmados por oftalmólogos"],
            plazo_semanas: 8,
            kpi: "Citas de medios con la marca presente",
            // Revisada contra la regulación sanitaria, pero falta la de comparativas: el mock la
            // deja fuera para que la revisión 2 muestre un aviso de restricciones.
            restricciones_revisadas: [RESTRICCIONES[0]],
          }),
          accion({
            id: "A5",
            descripcion:
              "Guía de decisión para pacientes: qué preguntar en la valoración preoperatoria y qué incluye el seguimiento de 12 meses",
            finding_ids: ["F-caida-embudo", "F-recomendacion-debil"],
            palanca: "contenido",
            fase_embudo: "decision",
            esfuerzo: "M",
            impacto: "M",
            responsable: "Comunicación",
            entregables: ["Guía descargable", "Resumen en la web"],
            plazo_semanas: 5,
            kpi: "Visibilidad espontánea en fase de decisión",
          }),
        ],
      },
      {
        nombre: "Reputación y cobertura por motor",
        semanas: 12,
        objetivo: "Pasar de ser conocida a ser recomendada, también en Claude y ChatGPT",
        acciones: [
          accion({
            id: "A6",
            descripcion: "Programa de reseñas verificadas tras el alta en plataformas de reseñas sanitarias",
            finding_ids: ["F-asistida-vs-espontanea", "F-recomendacion-debil"],
            palanca: "reputacion",
            fase_embudo: "validacion",
            esfuerzo: "M",
            impacto: "M",
            responsable: "Responsable de marketing",
            entregables: ["Circuito de solicitud de reseñas", "Respuesta a reseñas en 48 h"],
            plazo_semanas: 12,
            kpi: "Fuerza media de las apariciones espontáneas",
          }),
          accion({
            id: "A7",
            descripcion:
              "Datos estructurados de centros, médicos y tratamientos, y acceso de los rastreadores de los asistentes a la web",
            finding_ids: ["F-motor-debil"],
            palanca: "tecnico",
            motores_objetivo: ["Claude", "ChatGPT"],
            esfuerzo: "S",
            impacto: "M",
            responsable: "Agencia colaboradora",
            entregables: ["Marcado schema.org", "Revisión de robots.txt"],
            plazo_semanas: 3,
            kpi: "Visibilidad espontánea en Claude",
          }),
        ],
      },
    ],
    presupuesto_estimado_eur: 24000,
    respeta_restricciones: true,
  };
}

/** Puerto al mock de `validate_plan_against_brief` (en la API real lo calcula el dominio). */
export function violaciones(plan: Plan, brief: BriefSummary): string[] {
  const out: string[] = [];
  if (brief.presupuesto_anual_eur && plan.presupuesto_estimado_eur > brief.presupuesto_anual_eur[1]) {
    out.push(
      `presupuesto estimado ${plan.presupuesto_estimado_eur.toFixed(0)} € supera el máximo del brief (${brief.presupuesto_anual_eur[1]} €)`,
    );
  }
  for (const a of plan.fases.flatMap((f) => f.acciones)) {
    for (const r of brief.restricciones) {
      if (!a.restricciones_revisadas.includes(r)) out.push(`acción ${a.id} ignora la restricción «${r}»`);
    }
  }
  if (!plan.respeta_restricciones) out.push("el plan declara que no respeta las restricciones del brief");
  return out;
}

export function proposalFor(
  studyId: string,
  modo: ModoEstudio,
  m: Metrics,
  findings: Finding[],
  plan: Plan,
  fecha: string,
): Proposal {
  const foco = m.score_global.score ?? 0;
  const lider = m.scores.find((s) => s.brand_id === m.lider_id)?.score ?? 0;
  const puesto = m.ranking.indexOf(m.marca_foco_id) + 1;
  const kit = modo === "kit";
  const fmt = (n: number) => n.toLocaleString("es-ES", { maximumFractionDigits: 2 });
  return {
    study_id: studyId,
    resumen_ejecutivo:
      `Clínica Alborada Visión obtiene un Score de Citación de ${fmt(foco)} sobre 100 y ocupa el puesto ${puesto} de ${m.ranking.length} marcas, ` +
      `a ${fmt(lider - foco)} puntos del líder (${fmt(lider)}). Los asistentes la conocen cuando se les pregunta por ella, ` +
      `pero rara vez la proponen por iniciativa propia: aparece en el ${fmt(tasa(m, "global", "global"))} % de las respuestas espontáneas, ` +
      `solo en el ${fmt(tasa(m, "ciudad", "Barcelona"))} % cuando la pregunta nombra Barcelona y en el ${fmt(tasa(m, "motor", "Claude"))} % de las respuestas de Claude, ` +
      `frente al ${fmt(tasa(m, "motor", "Perplexity"))} % en Perplexity. El plan propone tres fases en 24 semanas, centradas en datos de entidad coherentes, ` +
      `autoridad de terceros y contenido local, con un presupuesto estimado de ${fmt(plan.presupuesto_estimado_eur)} €.`,
    contexto: {
      marca: kitBrief.marca,
      sector: kitBrief.sector,
      motores: ["ChatGPT", "Gemini", "Perplexity", "Claude"],
      fecha,
      origen_datos: kit ? "kit" : "api",
      datos_sinteticos: kit,
      limitaciones: [
        kit
          ? "Datos sintéticos del kit del reto: 624 ejecuciones simuladas, no respuestas reales de los motores."
          : "Una sola medición: las respuestas de los motores varían entre ejecuciones.",
        "Las evaluaciones sin etiqueta humana se resuelven por reglas o con el juez, con su confianza registrada.",
        "La visibilidad asistida no tiene datos por ciudad: ningún prompt asistido nombra una ciudad.",
      ],
    },
    diagnostico: {
      texto: `Score de Citación ${fmt(foco)}: aparición ${fmt(m.score_global.aparicion ?? 0)}, posición ${fmt(m.score_global.posicion ?? 0)}, fuerza ${fmt(m.score_global.fuerza ?? 0)} y calidad de fuente ${fmt(m.score_global.calidad_fuente ?? 0)}.`,
      metrics: m,
    },
    competencia: {
      texto: `El líder espontáneo es ${kitMarket.marcas.find((b) => b.id === m.lider_id)?.nombre ?? "—"}, apoyado en directorios médicos y medios de salud que no citan a la clínica.`,
      ranking: m.ranking,
    },
    hallazgos: findings,
    estrategia: {
      texto: "Primero, que los motores reconozcan la entidad con datos coherentes; después, ganar fuentes de terceros y contenido local; por último, convertir la mención en recomendación.",
      objetivos: plan.objetivos,
      prioridades: ["Barcelona", "Claude y ChatGPT", "Fases de comparación y decisión"],
    },
    plan,
    medicion: {
      kpis: plan.objetivos.map((o) => o.kpi),
      metodologia: "Re-medición con el mismo banco de prompts, motores y repeticiones; diferencias calculadas por el dominio.",
      cadencia: "Mensual durante 24 semanas",
    },
    riesgos: [
      {
        riesgo: "Publicidad sanitaria regulada",
        mitigacion: "Revisión médica y legal de todo contenido; sin promesas de resultados.",
      },
      {
        riesgo: "Variabilidad de las respuestas de los motores",
        mitigacion: "Tres repeticiones por prompt y lectura de tendencias, no de ejecuciones sueltas.",
      },
    ],
    marcas: Object.fromEntries(kitMarket.marcas.map((b) => [b.id, b.nombre])),
    hoja_ruta: {
      hitos: [
        { semana: 0, descripcion: "Arranque y línea base" },
        { semana: 4, descripcion: "Fichas de entidad corregidas" },
        { semana: 12, descripcion: "Contenido de Barcelona publicado y primera re-medición" },
        { semana: 24, descripcion: "Re-medición final y revisión de objetivos" },
      ],
      responsabilidades: {
        "Responsable de marketing": ["A1", "A6"],
        Comunicación: ["A3", "A5"],
        "Agencia colaboradora": ["A2", "A4", "A7"],
      },
      presupuesto_eur: plan.presupuesto_estimado_eur,
      seguimiento: "Comité mensual con el panel de visibilidad",
    },
  };
}

type TraceSeed = Omit<Trace, "study_id" | "fecha">;

/** Trazas por fase del grafo; en modo kit los motores no cuestan nada. */
export function tracesFor(modo: ModoEstudio, fase: 1 | 2 | 3): TraceSeed[] {
  const real = modo === "real";
  const t: TraceSeed[][] = [
    [
      { nodo: "parse_brief", modelo: "deepseek-chat", prompt_version: "parse_brief.v1", tokens_in: 1840, tokens_out: 620, coste_eur: 0.0012, duracion_ms: 3900 },
      { nodo: "propose_market", modelo: "deepseek-chat", prompt_version: "propose_market.v1", tokens_in: 1210, tokens_out: 540, coste_eur: 0.0009, duracion_ms: 2800 },
    ],
    [
      { nodo: "run_engines", modelo: real ? "4 motores" : "kit", prompt_version: "banco_prompts", tokens_in: real ? 93600 : 0, tokens_out: real ? 436800 : 0, coste_eur: real ? 3.1 : 0, duracion_ms: real ? 412000 : 900 },
      { nodo: "judge", modelo: "jev-latest", prompt_version: "judge_questions", tokens_in: 586000, tokens_out: 87900, coste_eur: 0.41, duracion_ms: 96000 },
      { nodo: "judge_fallback", modelo: "deepseek-chat", prompt_version: "judge_fallback.v1", tokens_in: 41000, tokens_out: 6100, coste_eur: 0.018, duracion_ms: 21000 },
      { nodo: "metrics", modelo: "dominio", prompt_version: "score 1.0", tokens_in: 0, tokens_out: 0, coste_eur: 0, duracion_ms: 140 },
      { nodo: "findings", modelo: "dominio", prompt_version: "findings", tokens_in: 0, tokens_out: 0, coste_eur: 0, duracion_ms: 30 },
      { nodo: "plan", modelo: "deepseek-chat", prompt_version: "plan.v1", tokens_in: 6900, tokens_out: 2400, coste_eur: 0.0044, duracion_ms: 14500 },
    ],
    [
      { nodo: "proposal", modelo: "deepseek-chat", prompt_version: "proposal.v1", tokens_in: 11200, tokens_out: 4100, coste_eur: 0.0074, duracion_ms: 22800 },
    ],
  ];
  return t.slice(0, fase).flat();
}

export const ESTIMACION_REAL = { llamadas: 624, coste_estimado_eur: 3.55, presupuesto_max_eur: 5 };
