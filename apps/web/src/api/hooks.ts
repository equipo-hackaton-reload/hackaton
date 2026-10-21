import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { CreateStudyRequest, ResumeRequest, StudyStatus } from "../types/api";
import type { ModoEstudio } from "../types/schemas";
import type { RemeasureRequest } from "../types/tracking";
import { api } from "./client";

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

/** Coste de volver a medir `id` con el mismo modo que el original. Siempre fresco. */
export function useRemeasureEstimate(id: string, enabled: boolean) {
  return useQuery({
    queryKey: keys.remeasureEstimate(id),
    queryFn: () => api.remeasureEstimate(id),
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
