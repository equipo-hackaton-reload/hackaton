/**
 * Espejo TypeScript de `src/posiq/domain/schemas.py` (contrato compartido).
 *
 * Campo a campo con los modelos Pydantic tal como los serializa la API (`model_dump(mode="json")`):
 * los campos con valor por defecto siempre llegan, los `datetime` llegan como ISO 8601 y las tuplas
 * como arrays. `scripts/check_types.py` compara este fichero con los modelos y falla si divergen.
 */

// --- Categorías ----------------------------------------------------------------------------------

export type Rol = "foco" | "contexto" | "lider";
export type FaseEmbudo = "descubrimiento" | "comparacion" | "validacion" | "decision";
export type Familia =
  | "Descubrimiento genérico"
  | "Descubrimiento por perfil"
  | "Localización"
  | "Comparación de opciones"
  | "Comparación de marcas"
  | "Validación reputacional"
  | "Fuentes y citación"
  | "Decisión final"
  | "Precio y valor";
export type Instanciacion = "generico" | "ciudad" | "marca" | "par";
export type TipoVisibilidad = "espontaneo" | "asistido";
export type Prioridad = "P1" | "P2";
export type Uso = "Publicable" | "Diagnóstico";
export type Motor = "ChatGPT" | "Gemini" | "Perplexity" | "Claude";
export type TipoMencion = "Recomendación activa" | "Comparación neutra" | "Pasiva";
export type Sentimiento = "positivo" | "neutro" | "negativo";
export type TipoFuenteCatalogo =
  | "Ranking / institución"
  | "Medio"
  | "Web propia"
  | "Directorio / comparador"
  | "Plataforma de reseñas"
  | "Red social / foro";
export type TipoFuente = TipoFuenteCatalogo | "Sin fuente";
export type OrigenEvaluacion = "jev" | "fallback" | "humano";
export type OrigenDatos = "kit" | "api";
export type ModoEstudio = "kit" | "real";
export type EstadoEstudio =
  | "en_curso"
  | "esperando_revision_competidores"
  | "esperando_revision_plan"
  | "completado";
export type Talla = "S" | "M" | "L";
export type Palanca =
  | "autoridad_terceros"
  | "entidad_datos"
  | "contenido"
  | "reputacion"
  | "comunidades"
  | "tecnico"
  | "medicion";
export type Dimension = "global" | "motor" | "fase" | "ciudad" | "perfil" | "familia";
export type UnidadCifra = "fraccion" | "puntos" | "recuento" | "eur";

/** Fecha ISO 8601 tal como la serializa Pydantic. */
export type DateTimeISO = string;

// --- Marca, brief y mercado ----------------------------------------------------------------------

export interface Brand {
  id: string;
  nombre: string;
  aliases: string[];
  rol: Rol;
  dominio: string | null;
  rol_detalle: string;
}

export interface BriefSummary {
  marca: string;
  sector: string;
  subsector: string;
  servicios_prioritarios: string[];
  publicos: string[];
  ciudades: string[];
  competidores_declarados: string[];
  presupuesto_anual_eur: [number, number] | null;
  equipo: string[];
  restricciones: string[];
  objetivos: string[];
  audiencia_del_entregable: string;
  tono: string;
}

export interface Market {
  marcas: Brand[];
  confirmado_por_humano: boolean;
}

export interface Study {
  id: string;
  brand_id: string;
  brief: BriefSummary;
  modo: ModoEstudio;
  creado_en: DateTimeISO;
  version_metodologia: string;
  score_version: string;
  estado: EstadoEstudio;
}

// --- Prompts, fuentes y ejecuciones --------------------------------------------------------------

export interface PromptTemplate {
  id: string;
  familia: Familia;
  fase_embudo: FaseEmbudo;
  instanciacion: Instanciacion;
  texto: string;
  prioridad: Prioridad;
  uso: Uso;
  readonly tipo: TipoVisibilidad;
}

export interface PromptInstance {
  id: string;
  template_id: string;
  familia: Familia;
  fase_embudo: FaseEmbudo;
  instanciacion: Instanciacion;
  perfil: string | null;
  ciudad: string | null;
  texto: string;
  marca_nombrada: string | null;
  marca_nombrada_b: string | null;
  prioridad: Prioridad;
  readonly tipo: TipoVisibilidad;
}

export interface Source {
  dominio: string;
  tipo: TipoFuenteCatalogo | null;
  calidad: number | null;
}

export interface Run {
  id: string;
  study_id: string;
  prompt_id: string;
  motor: Motor;
  modelo: string | null;
  repeticion: number;
  fecha: DateTimeISO;
  texto_respuesta: string;
  fuentes: Source[];
  marcas_a_evaluar: string[];
  coste_eur: number;
  tokens: number | null;
  origen: OrigenDatos;
}

// --- Evaluación ----------------------------------------------------------------------------------

export interface Detection {
  brand_id: string;
  posicion: number;
  span: [number, number];
  menciones: number;
}

export interface Evaluation {
  id: string;
  study_id: string;
  run_id: string;
  brand_id: string;
  aparece: boolean;
  posicion: number | null;
  tipo_mencion: TipoMencion | null;
  fuerza: number;
  sentimiento: Sentimiento | null;
  tipo_fuente: TipoFuente | null;
  apoyada_en_fuente: boolean;
  confianza: number;
  origen: OrigenEvaluacion;
  /** El juez dudó (confianza entre los umbrales): se usa, pero conviene revisarla. */
  necesita_revision: boolean;
  readonly peso_posicion: number;
  readonly por_desconocimiento: boolean;
}

// --- Métricas ------------------------------------------------------------------------------------

export interface ScoreBreakdown {
  brand_id: string;
  motor: Motor | null;
  n_evaluaciones: number;
  aparicion: number | null;
  posicion: number | null;
  fuerza: number | null;
  calidad_fuente: number | null;
  score: number | null;
  score_version: string;
}

export interface VisibilityCell {
  brand_id: string;
  tipo: TipoVisibilidad;
  dimension: Dimension;
  valor: string;
  n: number;
  apariciones: number;
  tasa: number | null;
  fuerza_media: number | null;
  evaluation_ids: string[];
}

export interface MentionQuality {
  brand_id: string;
  tipo: TipoVisibilidad;
  apariciones: number;
  fuerza_media: number | null;
  por_tipo_mencion: Record<string, number>;
  por_sentimiento: Record<string, number>;
  por_desconocimiento: number;
  negativas: number;
  desconocimiento_ids: string[];
  negativas_ids: string[];
}

export interface SourceStat {
  brand_id: string;
  dominio: string;
  tipo: TipoFuenteCatalogo | null;
  calidad: number | null;
  apariciones: number;
}

export interface SourceGap {
  dominio: string;
  tipo: TipoFuenteCatalogo | null;
  con_lider: number;
  con_marca: number;
  brecha: number;
  lider_sin_marca: number;
  evaluation_ids: string[];
}

export interface Metrics {
  study_id: string;
  comparado_con: string | null;
  score_version: string;
  marca_foco_id: string;
  lider_id: string | null;
  score_global: ScoreBreakdown;
  scores: ScoreBreakdown[];
  scores_por_motor: ScoreBreakdown[];
  ranking: string[];
  visibilidad: VisibilityCell[];
  calidad_menciones: MentionQuality[];
  top_fuentes: SourceStat[];
  brecha_fuentes: SourceGap[];
  n_ejecuciones: Record<string, number>;
}

export interface VisibilityDelta {
  brand_id: string;
  tipo: TipoVisibilidad;
  dimension: Dimension;
  valor: string;
  tasa_actual: number | null;
  tasa_anterior: number | null;
  delta: number | null;
  n_actual: number;
  n_anterior: number;
}

export interface MetricsDelta {
  study_id: string;
  comparado_con: string;
  marca_foco_id: string;
  score_actual: number | null;
  score_anterior: number | null;
  score_delta: number | null;
  visibilidad_delta: VisibilityDelta[];
  comparable: boolean;
  avisos: string[];
}

// --- Hallazgos, plan y propuesta -----------------------------------------------------------------

export interface Finding {
  id: string;
  study_id: string;
  titulo: string;
  descripcion: string;
  fase_embudo: FaseEmbudo | null;
  impacto: Talla;
  confianza: number;
  cifra: number;
  /** Cómo leer `cifra`: fracción 0-1, puntos (score o escala), recuento o euros. */
  unidad: UnidadCifra;
  origen_cifra: string;
  evaluation_ids: string[];
}

export interface Objective {
  kpi: string;
  valor_actual: number;
  valor_objetivo: number;
  plazo_semanas: number;
}

export interface Action {
  id: string;
  descripcion: string;
  finding_ids: string[];
  palanca: Palanca;
  fase_embudo: FaseEmbudo | null;
  motores_objetivo: Motor[];
  esfuerzo: Talla;
  impacto: Talla;
  responsable: string;
  dependencias: string[];
  entregables: string[];
  plazo_semanas: number;
  kpi: string;
  restricciones_revisadas: string[];
}

export interface Phase {
  nombre: string;
  semanas: number;
  objetivo: string;
  acciones: Action[];
}

export interface Plan {
  study_id: string;
  objetivos: Objective[];
  fases: Phase[];
  presupuesto_estimado_eur: number;
  respeta_restricciones: boolean;
}

export interface Contexto {
  marca: string;
  sector: string;
  motores: Motor[];
  fecha: DateTimeISO;
  origen_datos: OrigenDatos;
  datos_sinteticos: boolean;
  limitaciones: string[];
}

export interface Diagnostico {
  texto: string;
  metrics: Metrics;
}

export interface Competencia {
  texto: string;
  ranking: string[];
}

export interface Estrategia {
  texto: string;
  objetivos: Objective[];
  prioridades: string[];
}

export interface Medicion {
  kpis: string[];
  metodologia: string;
  cadencia: string;
}

export interface Riesgo {
  riesgo: string;
  mitigacion: string;
}

export interface Hito {
  semana: number;
  descripcion: string;
}

export interface HojaRuta {
  hitos: Hito[];
  responsabilidades: Record<string, string[]>;
  presupuesto_eur: number;
  seguimiento: string;
}

export interface Proposal {
  study_id: string;
  resumen_ejecutivo: string;
  contexto: Contexto;
  diagnostico: Diagnostico;
  competencia: Competencia;
  hallazgos: Finding[];
  estrategia: Estrategia;
  plan: Plan;
  medicion: Medicion;
  riesgos: Riesgo[];
  hoja_ruta: HojaRuta;
  /** `brand_id` → nombre legible; vacío = se muestran los ids. */
  marcas: Record<string, string>;
}

// --- Trazas --------------------------------------------------------------------------------------

export interface Trace {
  study_id: string;
  nodo: string;
  modelo: string;
  prompt_version: string;
  tokens_in: number;
  tokens_out: number;
  coste_eur: number;
  duracion_ms: number;
  fecha: DateTimeISO;
}
