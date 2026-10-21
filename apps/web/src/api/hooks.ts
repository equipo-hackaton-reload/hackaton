import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { CostEstimate, CreateStudyRequest, ResumeRequest, StudyStatus } from "../types/api";
import type { ModoEstudio } from "../types/schemas";
import type { RemeasureRequest } from "../types/tracking";
import { api, rutaNoDisponible } from "./client";

export const POLL_MS = 3000;

export const keys = {
  study: (id: string) => ["study", id] as const,
  studies: (brandId: string) => ["studies", brandId] as const,
  evidence: (id: string, ids: string[]) => ["evidence", id, ids] as const,
  traces: (id: string) => ["traces", id] as const,
  estimate: (modo: ModoEstudio) => ["estimate", modo] as const,
  remeasureEstimate: (id: string) => ["remeasure-estimate", id] as const,
  brands: ["brands"] as const,
  serie: (brandId: string) => ["serie", brandId] as const,
};

/**
 * Estado del estudio; sondea cada 3 s mientras el grafo está en curso. Un fallo puntual del sondeo
 * no borra lo que ya había: la pantalla sigue con los últimos datos y el sondeo lo reintenta.
 */
export function useStudy(id: string | undefined) {
  return useQuery({
    queryKey: keys.study(id ?? ""),
    queryFn: () => api.getStudy(id!),
    enabled: Boolean(id),
    refetchInterval: (q) => (q.state.data?.estado === "en_curso" ? POLL_MS : false),
  });
}

export function useCreateStudy() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: CreateStudyRequest) => api.createStudy(body),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.brands }),
  });
}

export function useResume(id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: ResumeRequest) => api.resume(id, body),
    onSuccess: () => {
      // El grafo retoma: se marca en curso para que el sondeo arranque sin esperar.
      qc.setQueryData<StudyStatus>(keys.study(id), (prev) =>
        prev ? { ...prev, estado: "en_curso", revision_pendiente: null, errores: [] } : prev,
      );
      return qc.invalidateQueries({ queryKey: keys.study(id) });
    },
  });
}

/** Estimación de la re-medición; `aproximada` si viene de `GET /estimate` por falta de la ruta propia. */
export type EstimacionRemedicion = CostEstimate & { aproximada?: boolean };

/**
 * La API no ofrece `GET /remeasure/estimate` y el estudio es de modo real: no hay coste propio que
 * confirmar y `POST /remeasure` todavía no valida `confirmado` ni `coste_estimado_eur`, así que la web
 * no deja lanzar un gasto de pago con una cifra aproximada.
 */
export class RemedicionRealNoDisponible extends Error {
  constructor() {
    super(
      "Esta API todavía no calcula el coste propio de la re-medición ni lo valida al lanzarla. En modo real no se puede volver a medir hasta que lo haga.",
    );
    this.name = "RemedicionRealNoDisponible";
  }
}

/**
 * `GET /studies/{id}/remeasure/estimate`. Si la API todavía no ofrece esa ruta (404 «Not Found»), solo
 * en modo kit (0 €) se usa `GET /estimate` y se marca como aproximada; en modo real se rechaza con
 * `RemedicionRealNoDisponible`. El coste sigue saliendo de la API, nunca de la web.
 */
async function estimacionRemedicion(id: string): Promise<EstimacionRemedicion> {
  try {
    return await api.remeasureEstimate(id);
  } catch (e) {
    if (!rutaNoDisponible(e)) throw e;
    const { study } = await api.getStudy(id);
    if (study.modo !== "kit") throw new RemedicionRealNoDisponible();
    return { ...(await api.estimate(study.modo)), aproximada: true };
  }
}

export function useRemeasureEstimate(id: string, enabled: boolean) {
  return useQuery({
    queryKey: keys.remeasureEstimate(id),
    queryFn: () => estimacionRemedicion(id),
    enabled,
    staleTime: 0,
    gcTime: 0,
  });
}

export function useRemeasure(id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: RemeasureRequest) => api.remeasure(id, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: keys.brands });
      qc.invalidateQueries({ queryKey: ["serie"] });
    },
  });
}

export function useStudies(brandId: string | undefined) {
  return useQuery({
    queryKey: keys.studies(brandId ?? ""),
    queryFn: () => api.listStudies(brandId!),
    enabled: Boolean(brandId),
  });
}

export function useEvidence(id: string, ids: string[], enabled: boolean) {
  return useQuery({
    queryKey: keys.evidence(id, ids),
    queryFn: () => api.evidence(id, ids),
    enabled: enabled && ids.length > 0,
    staleTime: Infinity,
  });
}

export function useTraces(id: string, estado: string | undefined) {
  return useQuery({
    queryKey: [...keys.traces(id), estado],
    queryFn: () => api.traces(id),
  });
}

/** Estimación previa de un estudio nuevo, en kit y en real. */
export function useEstimate(modo: ModoEstudio) {
  return useQuery({
    queryKey: keys.estimate(modo),
    queryFn: () => api.estimate(modo),
    staleTime: 60_000,
  });
}

export function useBrands() {
  return useQuery({ queryKey: keys.brands, queryFn: api.brands });
}

export function useSerie(brandId: string) {
  return useQuery({
    queryKey: keys.serie(brandId),
    queryFn: () => api.serie(brandId),
    enabled: Boolean(brandId),
  });
}
