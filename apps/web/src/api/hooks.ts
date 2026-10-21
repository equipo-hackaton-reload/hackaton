import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { CreateStudyRequest, ResumeRequest, StudyStatus } from "../types/api";
import { api } from "./client";

export const POLL_MS = 3000;

export const keys = {
  study: (id: string) => ["study", id] as const,
  studies: (brandId: string) => ["studies", brandId] as const,
  evidence: (id: string, ids: string[]) => ["evidence", id, ids] as const,
  traces: (id: string) => ["traces", id] as const,
  estimate: ["estimate", "real"] as const,
};

/** Estado del estudio; sondea cada 3 s mientras el grafo está en curso. */
export function useStudy(id: string | undefined) {
  return useQuery({
    queryKey: keys.study(id ?? ""),
    queryFn: () => api.getStudy(id!),
    enabled: Boolean(id),
    refetchInterval: (q) => (q.state.data?.estado === "en_curso" ? POLL_MS : false),
  });
}

export function useCreateStudy() {
  return useMutation({ mutationFn: (body: CreateStudyRequest) => api.createStudy(body) });
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

export function useRemeasure() {
  return useMutation({ mutationFn: (id: string) => api.remeasure(id) });
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

export function useEstimate(enabled: boolean) {
  return useQuery({
    queryKey: keys.estimate,
    queryFn: () => api.estimate("real"),
    enabled,
    staleTime: 60_000,
  });
}
