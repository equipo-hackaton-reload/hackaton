import { delay, http, HttpResponse } from "msw";
import { API_URL } from "../api/client";
import type { CreateStudyRequest, ResumeRequest } from "../types/api";
import type { User } from "../types/auth";
import { MIN_PASSWORD } from "../types/auth";
import * as auth from "./auth";
import { ESTIMACION_KIT, ESTIMACION_REAL, kitEvidencias } from "./data";
import * as db from "./db";
import * as tracking from "./tracking";

const u = (path: string) => `${API_URL}${path}`;
const noEncontrado = () => HttpResponse.json({ detail: "estudio no encontrado" }, { status: 404 });
const noAutenticado = () =>
  HttpResponse.json({ detail: "no autenticado" }, { status: 401, headers: { "WWW-Authenticate": "Bearer" } });
const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;
/** Margen con el que la API da por buena la estimación confirmada. */
const TOLERANCIA_EUR = 0.01;

function token(request: Request): string | null {
  const h = request.headers.get("Authorization") ?? "";
  return h.startsWith("Bearer ") ? h.slice(7) : null;
}

/** Usuario del token Bearer, o null (→ 401). */
function usuario(request: Request): User | null {
  return auth.usuarioPorToken(token(request));
}

const esDemo = (user: User) => user.email === auth.DEMO.email;

/** El contrato de `/auth` solo acepta JSON. */
function noEsJson(request: Request): boolean {
  return !(request.headers.get("Content-Type") ?? "").includes("application/json");
}
const noSoportado = () => HttpResponse.json({ detail: "se espera application/json" }, { status: 415 });

function estimacion(modo: string | null | undefined) {
  return modo === "real" ? ESTIMACION_REAL : ESTIMACION_KIT;
}

/** PDF mínimo válido de una página con el texto indicado (solo ASCII). */
function pdf(texto: string): string {
  const stream = `BT /F1 14 Tf 72 760 Td (${texto.replace(/[()\\]/g, "")}) Tj ET`;
  const objs = [
    "<< /Type /Catalog /Pages 2 0 R >>",
    "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
    "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
    `<< /Length ${stream.length} >>\nstream\n${stream}\nendstream`,
    "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
  ];
  let out = "%PDF-1.4\n";
  const offsets: number[] = [];
  objs.forEach((o, i) => {
    offsets.push(out.length);
    out += `${i + 1} 0 obj\n${o}\nendobj\n`;
  });
  const xref = out.length;
  out += `xref\n0 ${objs.length + 1}\n0000000000 65535 f \n`;
  out += offsets.map((o) => `${String(o).padStart(10, "0")} 00000 n \n`).join("");
  out += `trailer\n<< /Size ${objs.length + 1} /Root 1 0 R >>\nstartxref\n${xref}\n%%EOF`;
  return out;
}

const authHandlers = [
  http.post(u("/auth/register"), async ({ request }) => {
    if (noEsJson(request)) return noSoportado();
    const body = (await request.json()) as { email?: string; password?: string; nombre?: string };
    const email = (body.email ?? "").trim().toLowerCase();
    if (!EMAIL.test(email)) return HttpResponse.json({ detail: "email no válido" }, { status: 422 });
    if ((body.password ?? "").length < MIN_PASSWORD) {
      return HttpResponse.json({ detail: `la contraseña necesita al menos ${MIN_PASSWORD} caracteres` }, { status: 422 });
    }
    const r = auth.registrar(email, body.password!, body.nombre);
    if (r === "existe") return HttpResponse.json({ detail: "ya existe una cuenta con ese correo" }, { status: 409 });
    // El código va al log del servidor; en modo demo además en la respuesta.
    return HttpResponse.json({ user: r.user, verificacion: { enviado: true, codigo_dev: r.codigo } }, { status: 201 });
  }),

  http.post(u("/auth/verify"), async ({ request }) => {
    if (noEsJson(request)) return noSoportado();
    const { email = "", codigo = "" } = (await request.json()) as { email?: string; codigo?: string };
    const r = auth.verificar(email, codigo);
    if (typeof r === "object") return HttpResponse.json({ user: r });
    if (r === "bloqueado") {
      return HttpResponse.json({ detail: "demasiados intentos; pide un código nuevo" }, { status: 429 });
    }
    if (r === "caducado") return HttpResponse.json({ detail: "el código ha caducado" }, { status: 400 });
    return HttpResponse.json({ detail: "código incorrecto" }, { status: 400 });
  }),

  http.post(u("/auth/verify/reenviar"), async ({ request }) => {
    if (noEsJson(request)) return noSoportado();
    const { email = "" } = (await request.json()) as { email?: string };
    const e = email.trim().toLowerCase();
    // Misma respuesta exista o no la cuenta, para no revelar qué correos están registrados.
    const codigo = auth.existeCuenta(e) ? auth.nuevoCodigo(e) : undefined;
    return HttpResponse.json({ verificacion: { enviado: true, codigo_dev: codigo } }, { status: 202 });
  }),

  http.post(u("/auth/login"), async ({ request }) => {
    if (noEsJson(request)) return noSoportado();
    const { email = "", password = "" } = (await request.json()) as { email?: string; password?: string };
    await delay(80);
    const r = auth.login(email, password);
    if (r === "credenciales") return HttpResponse.json({ detail: "credenciales incorrectas" }, { status: 401 });
    if (r === "no_verificado") return HttpResponse.json({ detail: "correo_no_verificado" }, { status: 403 });
    return HttpResponse.json({ token: r.token, expira_en: new Date(r.expira).toISOString(), user: r.user });
  }),

  http.post(u("/auth/logout"), ({ request }) => {
    const t = token(request);
    if (!usuario(request) || !t) return noAutenticado();
    auth.logout(t);
    return new HttpResponse(null, { status: 204 });
  }),

  http.get(u("/auth/me"), ({ request }) => {
    const user = usuario(request);
    return user ? HttpResponse.json({ user }) : noAutenticado();
  }),
];

const studyHandlers = [
  http.post(u("/studies"), async ({ request }) => {
    const user = usuario(request);
    if (!user) return noAutenticado();
    const body = (await request.json()) as CreateStudyRequest;
    if (!body?.brief_texto?.trim()) {
      return HttpResponse.json({ detail: "brief_texto vacío" }, { status: 422 });
    }
    await delay(150);
    return HttpResponse.json({ study_id: db.crear(body.modo, user.id) }, { status: 201 });
  }),

  http.get(u("/studies"), ({ request }) => {
    const user = usuario(request);
    if (!user) return noAutenticado();
    const brandId = new URL(request.url).searchParams.get("brand_id");
    return HttpResponse.json(db.listar(user.id, brandId));
  }),

  http.get(u("/estimate"), ({ request }) => {
    if (!usuario(request)) return noAutenticado();
    return HttpResponse.json(estimacion(new URL(request.url).searchParams.get("modo")));
  }),

  http.get(u("/studies/:id"), ({ params, request }) => {
    const user = usuario(request);
    if (!user) return noAutenticado();
    const id = String(params.id);
    const s = db.esDe(id, user.id) ? db.estado(id) : undefined;
    return s ? HttpResponse.json(s) : noEncontrado();
  }),

  http.post(u("/studies/:id/resume"), async ({ params, request }) => {
    const user = usuario(request);
    if (!user) return noAutenticado();
    const id = String(params.id);
    if (!db.esDe(id, user.id)) return noEncontrado();
    const body = (await request.json()) as ResumeRequest;
    const r = db.reanudar(id, body.revision, body.payload);
    if (r === "no_existe") return noEncontrado();
    if (r === "fuera_de_turno") {
      return HttpResponse.json({ detail: `el estudio no espera la revisión «${body.revision}»` }, { status: 409 });
    }
    return HttpResponse.json({ study_id: id, revision: body.revision }, { status: 202 });
  }),

  http.get(u("/studies/:id/remeasure/estimate"), ({ params, request }) => {
    const user = usuario(request);
    if (!user) return noAutenticado();
    const id = String(params.id);
    if (!db.esDe(id, user.id)) return noEncontrado();
    return HttpResponse.json(estimacion(db.modo(id)));
  }),

  http.post(u("/studies/:id/remeasure"), async ({ params, request }) => {
    const user = usuario(request);
    if (!user) return noAutenticado();
    const id = String(params.id);
    if (!db.esDe(id, user.id)) return noEncontrado();
    const body = (await request.json().catch(() => null)) as { confirmado?: unknown; coste_estimado_eur?: unknown } | null;
    if (body?.confirmado !== true) {
      return HttpResponse.json({ detail: "hay que confirmar el coste (confirmado: true)" }, { status: 400 });
    }
    const actual = estimacion(db.modo(id)).coste_estimado_eur;
    if (typeof body.coste_estimado_eur !== "number" || Math.abs(body.coste_estimado_eur - actual) > TOLERANCIA_EUR) {
      return HttpResponse.json({ detail: "el coste estimado ha cambiado; vuelve a pedir la estimación" }, { status: 409 });
    }
    const r = db.remeasure(id);
    if (r === "no_existe") return noEncontrado();
    if (r === "no_completado") return HttpResponse.json({ detail: "el estudio aún no está completado" }, { status: 409 });
    if (r === "en_curso") return HttpResponse.json({ detail: "ya hay una re-medición en curso" }, { status: 409 });
    return HttpResponse.json(r, { status: 201 });
  }),

  http.get(u("/studies/:id/evaluations"), ({ params, request }) => {
    const user = usuario(request);
    if (!user) return noAutenticado();
    if (!db.esDe(String(params.id), user.id)) return noEncontrado();
    const ids = (new URL(request.url).searchParams.get("ids") ?? "").split(",").filter(Boolean);
    return HttpResponse.json(ids.flatMap((id) => (kitEvidencias[id] ? [kitEvidencias[id]] : [])));
  }),

  http.get(u("/studies/:id/traces"), ({ params, request }) => {
    const user = usuario(request);
    if (!user) return noAutenticado();
    const id = String(params.id);
    const t = db.esDe(id, user.id) ? db.trazas(id) : undefined;
    return t ? HttpResponse.json(t) : noEncontrado();
  }),

  http.get(u("/studies/:id/export"), ({ params, request }) => {
    const user = usuario(request);
    if (!user) return noAutenticado();
    const id = String(params.id);
    if (!db.esDe(id, user.id)) return noEncontrado();
    if (db.etapa(id) !== "completado") {
      return HttpResponse.json({ detail: "la propuesta aún no está lista" }, { status: 409 });
    }
    const formato = new URL(request.url).searchParams.get("formato");
    if (formato === "pdf") {
      return new HttpResponse(pdf(`posiq. - propuesta ${id} (mock)`), {
        headers: {
          "Content-Type": "application/pdf",
          "Content-Disposition": `attachment; filename="propuesta-${id}.pdf"`,
        },
      });
    }
    // Sin backend no hay plantilla Word: el mock entrega texto plano y lo dice en el nombre.
    return new HttpResponse(`posiq. - propuesta ${id}\nFichero de ejemplo del mock; la API real devuelve .docx.\n`, {
      headers: {
        "Content-Type": "text/plain; charset=utf-8",
        "Content-Disposition": `attachment; filename="propuesta-${id}-mock.txt"`,
      },
    });
  }),
];

const trackingHandlers = [
  http.get(u("/brands"), ({ request }) => {
    const user = usuario(request);
    if (!user) return noAutenticado();
    return HttpResponse.json(tracking.marcas(user.id, esDemo(user)));
  }),

  http.get(u("/brands/:brandId/serie"), ({ params, request }) => {
    const user = usuario(request);
    if (!user) return noAutenticado();
    const s = tracking.serie(user.id, String(params.brandId), esDemo(user));
    return s ? HttpResponse.json(s) : HttpResponse.json({ detail: "marca no encontrada" }, { status: 404 });
  }),
];

export const handlers = [...authHandlers, ...studyHandlers, ...trackingHandlers];
