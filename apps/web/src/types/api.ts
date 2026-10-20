/** Contrato HTTP de la API de posiq. (zona C) tal como lo consume la web. */
import type {
  BriefSummary,
  EstadoEstudio,
  Evaluation,
  Finding,
  Market,
  Metrics,
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
  findings?: Finding[];
  plan?: Plan;
  proposal?: Proposal;
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
