import type {
  CostEstimate,
  CreateStudyRequest,
  CreateStudyResponse,
  Evidence,
  FormatoExport,
  RemeasureResponse,
  ResumeRequest,
  StudyStatus,
} from "../types/api";
import type { Study, Trace } from "../types/schemas";

export const API_URL = (import.meta.env.VITE_API_URL ?? "").replace(/\/$/, "");

export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function detalle(res: Response): Promise<string> {
  try {
    const body = await res.json();
    if (typeof body?.detail === "string") return body.detail;
    return JSON.stringify(body?.detail ?? body);
  } catch {
    return res.statusText || `HTTP ${res.status}`;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  if (!res.ok) throw new ApiError(res.status, await detalle(res));
  // 202 puede venir con cuerpo (remeasure) o sin él (resume).
  const texto = res.status === 204 ? "" : await res.text();
  return (texto ? JSON.parse(texto) : undefined) as T;
}

export const api = {
  createStudy: (body: CreateStudyRequest) =>
    request<CreateStudyResponse>("/studies", { method: "POST", body: JSON.stringify(body) }),

  getStudy: (id: string) => request<StudyStatus>(`/studies/${encodeURIComponent(id)}`),

  resume: (id: string, body: ResumeRequest) =>
    request<void>(`/studies/${encodeURIComponent(id)}/resume`, {
      method: "POST",
      body: JSON.stringify(body),
    }),

  remeasure: (id: string) =>
    request<RemeasureResponse>(`/studies/${encodeURIComponent(id)}/remeasure`, {
      method: "POST",
    }),

  listStudies: (brandId: string) =>
    request<Study[]>(`/studies?brand_id=${encodeURIComponent(brandId)}`),

  evidence: (id: string, ids: string[]) =>
    request<Evidence[]>(
      `/studies/${encodeURIComponent(id)}/evaluations?ids=${ids.map(encodeURIComponent).join(",")}`,
    ),

  traces: (id: string) => request<Trace[]>(`/studies/${encodeURIComponent(id)}/traces`),

  estimate: (modo: "real") => request<CostEstimate>(`/estimate?modo=${modo}`),

  /** Descarga la propuesta y la entrega al navegador con el nombre que indique la API. */
  async exportProposal(id: string, formato: FormatoExport): Promise<void> {
    const res = await fetch(
      `${API_URL}/studies/${encodeURIComponent(id)}/export?formato=${formato}`,
    );
    if (!res.ok) throw new ApiError(res.status, await detalle(res));
    const blob = await res.blob();
    const nombre =
      /filename="?([^";]+)"?/.exec(res.headers.get("Content-Disposition") ?? "")?.[1] ??
      `propuesta-${id}.${formato}`;
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = nombre;
    document.body.append(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  },
};
