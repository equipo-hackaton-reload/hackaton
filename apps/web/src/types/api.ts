/** Contrato HTTP de la API de posiq. (zona C) tal como lo consume la web. */
import type {
  BriefSummary,
  EstadoEstudio,
  Evaluation,
  Finding,
  Market,
  Metrics,
  MetricsDelta,
  ModoEstudio,
  Motor,
  Plan,
  Proposal,
  Study,
} from "./schemas";

export type Revision = "competidores" | "plan";
export type FormatoExport = "docx" | "pdf";

/** `POST /studies` */
export interface CreateStudyRequest {
  brief_texto: string;
  modo: ModoEstudio;
}
export interface CreateStudyResponse {
  study_id: string;
  /** Solo en modo kit: «Modo kit: datos sintéticos de Alborada; el brief no cambia las mediciones». */
  aviso?: string | null;
}

export interface RemeasureResponse {
  study_id: string;
}

/** `GET /studies/{id}`: los bloques opcionales aparecen a medida que el grafo los produce. */
export interface StudyStatus {
  study: Study;
  estado: EstadoEstudio;
  revision_pendiente: Revision | null;
  coste_acumulado_eur: number;
  errores: string[];
  brief?: BriefSummary;
  market?: Market;
  metrics?: Metrics;
  metrics_delta?: MetricsDelta;
  findings?: Finding[];
  plan?: Plan;
  simulacion?: SimulationResult;
  calidad_plan?: PlanQuality;
  proposal?: Proposal;
}

export interface Scenario {
  minimo: number;
  esperado: number;
  maximo: number;
}

export interface PhaseProjection {
  fase: string;
  indice: number;
  acciones: string[];
  tasa_espontanea: Scenario;
  score: Scenario;
}

export interface SegmentChange {
  segmento: string;
  dimension: "fase_motor" | "ciudad";
  n: number;
  tasa_actual: number;
  delta: Scenario;
  acciones: string[];
}

export interface IgnoredAction {
  action_id: string;
  motivo: string;
}

export interface SimulationResult {
  study_id: string;
  marca_foco_id: string;
  modelo_version: string;
  score_actual: number | null;
  tasa_espontanea_actual: number | null;
  proyecciones: PhaseProjection[];
  segmentos: SegmentChange[];
  acciones_sin_efecto: IgnoredAction[];
  supuestos: string[];
  advertencia: string;
}

export interface ActionQuality {
  action_id: string;
  es_especifica: boolean;
  coherente_con_hallazgo: boolean;
  respeta_restricciones: boolean;
  realista_para_equipo: boolean;
  calidad_global: number;
  probabilidades: Record<string, number>;
  confianza: number;
  por_debajo_umbral: boolean;
  motivos: string[];
}

export interface PlanQuality {
  study_id: string;
  juez: string;
  modelo: string;
  acciones: ActionQuality[];
  pct_especificas: number | null;
  pct_coherentes: number | null;
  pct_respetan_restricciones: number | null;
  pct_realistas: number | null;
  calidad_media: number | null;
  por_debajo_umbral: string[];
  baja_confianza: string[];
  nota: string;
}

/** `POST /studies/{id}/resume` → 202 */
export type ResumeRequest =
  | { revision: "competidores"; payload: Market }
  | { revision: "plan"; payload: Plan };

// --- Endpoints que la web asume además del contrato base (a contrastar con la zona C) ----------

/** `GET /studies/{id}/evaluations?ids=a,b` → evaluaciones con el texto de su ejecución. */
export interface Evidence {
  evaluation: Evaluation;
  motor: Motor;
  prompt: string;
  texto_respuesta: string;
  fuentes: string[];
}

/** `GET /estimate?modo=real` → estimación previa del coste de un estudio. */
export interface CostEstimate {
  llamadas: number;
  coste_estimado_eur: number;
  presupuesto_max_eur: number;
}
