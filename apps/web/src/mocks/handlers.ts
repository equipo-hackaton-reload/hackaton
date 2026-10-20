import { delay, http, HttpResponse } from "msw";
import { API_URL } from "../api/client";
import type { CreateStudyRequest, ResumeRequest } from "../types/api";
import { ESTIMACION_REAL, kitEvidencias } from "./data";
import * as db from "./db";

const u = (path: string) => `${API_URL}${path}`;
const noEncontrado = () => HttpResponse.json({ detail: "estudio no encontrado" }, { status: 404 });

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

export const handlers = [
  http.post(u("/studies"), async ({ request }) => {
    const body = (await request.json()) as CreateStudyRequest;
    if (!body?.brief_texto?.trim()) {
      return HttpResponse.json({ detail: "brief_texto vacío" }, { status: 422 });
    }
    await delay(150);
    return HttpResponse.json({ study_id: db.crear(body.modo) }, { status: 201 });
  }),

  http.get(u("/studies"), ({ request }) => {
    const brandId = new URL(request.url).searchParams.get("brand_id");
    return HttpResponse.json(db.listar(brandId));
  }),

  http.get(u("/estimate"), () => HttpResponse.json(ESTIMACION_REAL)),

  http.get(u("/studies/:id"), ({ params }) => {
    const s = db.estado(String(params.id));
    return s ? HttpResponse.json(s) : noEncontrado();
  }),

  http.post(u("/studies/:id/resume"), async ({ params, request }) => {
    const body = (await request.json()) as ResumeRequest;
    const r = db.reanudar(String(params.id), body.revision, body.payload);
    if (r === "no_existe") return noEncontrado();
    if (r === "fuera_de_turno") {
      return HttpResponse.json(
        { detail: `el estudio no espera la revisión «${body.revision}»` },
        { status: 409 },
      );
    }
    return new HttpResponse(null, { status: 202 });
  }),

  http.get(u("/studies/:id/evaluations"), ({ params, request }) => {
    if (!db.existe(String(params.id))) return noEncontrado();
    const ids = (new URL(request.url).searchParams.get("ids") ?? "").split(",").filter(Boolean);
    return HttpResponse.json(ids.flatMap((id) => (kitEvidencias[id] ? [kitEvidencias[id]] : [])));
  }),

  http.get(u("/studies/:id/traces"), ({ params }) => {
    const t = db.trazas(String(params.id));
    return t ? HttpResponse.json(t) : noEncontrado();
  }),

  http.get(u("/studies/:id/export"), ({ params, request }) => {
    const id = String(params.id);
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
