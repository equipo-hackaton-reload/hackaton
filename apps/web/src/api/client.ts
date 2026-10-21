import { clearSession, getToken } from "../lib/session";
import type {
  LoginRequest,
  LoginResponse,
  RegisterRequest,
  RegisterResponse,
  UserResponse,
  VerificacionEnviada,
  VerifyRequest,
} from "../types/auth";
import type {
  CostEstimate,
  CreateStudyRequest,
  CreateStudyResponse,
  Evidence,
  FormatoExport,
  ResumeRequest,
  StudyStatus,
} from "../types/api";
import type { ModoEstudio, Study, Trace } from "../types/schemas";
import type { BrandSummary, RemeasureCreated, RemeasureRequest, SerieMarca } from "../types/tracking";

export const API_URL = (import.meta.env.VITE_API_URL ?? "").replace(/\/$/, "");

/** Evento que se lanza cuando la API rechaza el token: la app vuelve al login. */
export const EVENTO_401 = "posiq:unauthorized";

export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

/**
 * 404 de una ruta que la API conectada todavía no ofrece (FastAPI responde `{"detail": "Not Found"}`),
 * distinto del 404 de un recurso que no existe o no es tuyo (la API explica cuál).
 */
export function rutaNoDisponible(e: unknown): boolean {
  return e instanceof ApiError && e.status === 404 && e.message === "Not Found";
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

interface Opciones extends RequestInit {
  /** false en las rutas públicas de `/auth`: allí un 401 es «credenciales malas», no «sesión caducada». */
  auth?: boolean;
}

function cabeceras(auth: boolean, extra?: HeadersInit): Headers {
  const h = new Headers(extra);
  if (!h.has("Content-Type")) h.set("Content-Type", "application/json");
  const token = auth ? getToken() : null;
  if (token) h.set("Authorization", `Bearer ${token}`);
  return h;
}

/** Sin token o con el token caducado: se limpia la sesión y la app redirige al login. */
function sesionCaducada(): void {
  clearSession();
  if (typeof window !== "undefined") window.dispatchEvent(new Event(EVENTO_401));
}

async function llamar(path: string, { auth = true, headers, ...init }: Opciones = {}): Promise<Response> {
  const res = await fetch(`${API_URL}${path}`, { ...init, headers: cabeceras(auth, headers) });
  if (res.status === 401 && auth) sesionCaducada();
  if (!res.ok) throw new ApiError(res.status, await detalle(res));
  return res;
}

async function request<T>(path: string, init?: Opciones): Promise<T> {
  const res = await llamar(path, init);
  // 202 puede venir con cuerpo (remeasure) o sin él (resume); 204 nunca lo trae.
  const texto = res.status === 204 ? "" : await res.text();
  return (texto ? JSON.parse(texto) : undefined) as T;
}

const json = (body: unknown) => JSON.stringify(body);
const study = (id: string) => `/studies/${encodeURIComponent(id)}`;

/** Cuerpo de `POST /auth/verify/reenviar` (202): `{enviado, codigo_dev?}`; `codigo_dev` solo en modo demo. */
export type ReenvioResponse = (Partial<VerificacionEnviada> & { verificacion?: VerificacionEnviada }) | undefined;

export const api = {
  // --- Cuentas -----------------------------------------------------------------------------------
  register: (body: RegisterRequest) =>
    request<RegisterResponse>("/auth/register", { method: "POST", body: json(body), auth: false }),

  verify: (body: VerifyRequest) =>
    request<UserResponse>("/auth/verify", { method: "POST", body: json(body), auth: false }),

  resendCode: (email: string) =>
    request<ReenvioResponse>("/auth/verify/reenviar", { method: "POST", body: json({ email }), auth: false }),

  login: (body: LoginRequest) =>
    request<LoginResponse>("/auth/login", { method: "POST", body: json(body), auth: false }),

  /** Invalida el token en la API. Un 401 aquí no redirige: ya se está saliendo. */
  logout: (token: string) =>
    request<void>("/auth/logout", { method: "POST", auth: false, headers: { Authorization: `Bearer ${token}` } }),

  me: () => request<UserResponse>("/auth/me"),

  // --- Estudios ----------------------------------------------------------------------------------
  createStudy: (body: CreateStudyRequest) =>
    request<CreateStudyResponse>("/studies", { method: "POST", body: json(body) }),

  getStudy: (id: string) => request<StudyStatus>(study(id)),

  resume: (id: string, body: ResumeRequest) =>
    request<void>(`${study(id)}/resume`, { method: "POST", body: json(body) }),

  remeasureEstimate: (id: string) => request<CostEstimate>(`${study(id)}/remeasure/estimate`),

  remeasure: (id: string, body: RemeasureRequest) =>
    request<RemeasureCreated>(`${study(id)}/remeasure`, { method: "POST", body: json(body) }),

  listStudies: (brandId: string) => request<Study[]>(`/studies?brand_id=${encodeURIComponent(brandId)}`),

  evidence: (id: string, ids: string[]) =>
    request<Evidence[]>(`${study(id)}/evaluations?ids=${ids.map(encodeURIComponent).join(",")}`),

  traces: (id: string) => request<Trace[]>(`${study(id)}/traces`),

  estimate: (modo: ModoEstudio) => request<CostEstimate>(`/estimate?modo=${modo}`),

  // --- Seguimiento -------------------------------------------------------------------------------
  brands: () => request<BrandSummary[]>("/brands"),

  serie: (brandId: string) => request<SerieMarca>(`/brands/${encodeURIComponent(brandId)}/serie`),

  /** Descarga la propuesta y la entrega al navegador con el nombre que indique la API. */
  async exportProposal(id: string, formato: FormatoExport): Promise<void> {
    const res = await llamar(`${study(id)}/export?formato=${formato}`);
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
