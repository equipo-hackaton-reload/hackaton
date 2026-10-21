/**
 * Seguimiento de una marca en el tiempo: espejo de `domain/tracking_schemas.py` y de los endpoints
 * `/brands` y `/studies/{id}/remeasure*`. Todas las cifras las calcula el dominio; la web las pinta.
 */
import type { DateTimeISO, Motor } from "./schemas";

export type MetodoIntervalo = "wilson" | "bootstrap" | "diferencia_proporciones";

/** Espejo de `domain/stats_schemas.Intervalo`. */
export interface Intervalo {
  valor: number;
  inf: number;
  sup: number;
  n: number;
  nivel: number;
  metodo: MetodoIntervalo;
}

/** Espejo de `domain/stats_schemas.Significancia`. */
export interface Significancia {
  delta: number;
  intervalo: Intervalo;
  p_valor: number | null;
  significativa: boolean;
}

export interface PuntoSerie {
  study_id: string;
  fecha: DateTimeISO;
  score: number | null;
  intervalo: Intervalo | null;
  posicion: number | null;
  n_marcas: number;
  score_medio_competidores: number | null;
  diferencia_vs_competidores: number | null;
  version_metodologia: string;
  score_version: string;
  /** Huella del banco de prompts: si cambia, la medición no es comparable. */
  banco_prompts: string;
  motores: Motor[];
  modelos_motor: Partial<Record<Motor, string>>;
  comparable_con_anterior: boolean;
  motivos_no_comparable: string[];
  avisos: string[];
}

export interface CambioSerie {
  desde_study_id: string;
  hasta_study_id: string;
  metrica: string;
  delta: number;
  significancia: Significancia | null;
  significativo: boolean;
  relativo_a_competidores: boolean;
  /** Frase determinista del dominio (plantilla), lista para mostrar. */
  texto: string;
}

export interface ValorIndicador {
  study_id: string;
  valor: number | null;
}

export interface IndicadorAdelantado {
  clave: string;
  nombre: string;
  /** Misma convención que `Finding.unidad`: fraccion, puntos, recuento o eur. */
  unidad: string;
  valores: ValorIndicador[];
}

export interface SerieMarca {
  brand_id: string;
  nombre: string;
  puntos: PuntoSerie[];
  cambios: CambioSerie[];
  cambios_significativos: CambioSerie[];
  indicadores: IndicadorAdelantado[];
  /** Frases deterministas; «Sin cambios fuera del margen de error» si no hay cambios significativos. */
  resumen: string[];
}

/** `GET /brands` */
export interface BrandSummary {
  brand_id: string;
  nombre: string;
  n_mediciones: number;
  ultima_medicion: DateTimeISO | null;
}

/** `POST /studies/{id}/remeasure` */
export interface RemeasureRequest {
  confirmado: true;
  coste_estimado_eur: number;
}

export interface RemeasureCreated {
  study_id: string;
  remedicion_de: string;
}

export const SIN_CAMBIOS = "Sin cambios fuera del margen de error";
