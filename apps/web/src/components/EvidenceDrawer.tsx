import { useEffect, useRef, useState, type ReactNode } from "react";
import { useEvidence } from "../api/hooks";
import { fmtCifra, fmtPct } from "../lib/format";
import type { Evidence } from "../types/api";
import type { Brand, Finding } from "../types/schemas";

/** Cuántas evaluaciones se piden de golpe; el resto se cuenta pero no se carga. */
export const EVIDENCIAS_MAX = 20;

const ORIGEN: Record<string, string> = { jev: "Juez Jev", fallback: "Juez de respaldo", humano: "Etiqueta humana" };

function escapar(s: string) {
  return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

/** Resalta en el texto de la respuesta los nombres y alias de la marca evaluada. */
function Resaltado({ texto, marca }: { texto: string; marca: Brand | undefined }) {
  const nombres = marca ? [marca.nombre, ...marca.aliases].filter(Boolean).sort((a, b) => b.length - a.length) : [];
  if (!nombres.length) return <>{texto}</>;
  const re = new RegExp(`(${nombres.map(escapar).join("|")})`, "gi");
  const partes: ReactNode[] = texto.split(re).map((p, i) =>
    i % 2 === 1 ? (
      <mark key={i} className="rounded-[2px] bg-accent-soft px-0.5 text-accent-ink">
        {p}
      </mark>
    ) : (
      p
    ),
  );
  return <>{partes}</>;
}

function Item({ e, marca }: { e: Evidence; marca: Brand | undefined }) {
  const [abierto, setAbierto] = useState(false);
  const ev = e.evaluation;
  return (
    <li className="border-t border-rule py-4 first:border-t-0" data-testid="evidencia">
      <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-meta">
        <code className="rounded-chip bg-raised px-1.5 py-0.5 font-mono text-[12px] text-ink">{ev.id}</code>
        <span className="font-medium">{e.motor}</span>
        {ev.aparece ? (
          <span className="pill bg-pill-pos-bg text-pill-pos-ink">Aparece · {ev.posicion}.ª</span>
        ) : (
          <span className="pill bg-raised text-muted">No aparece</span>
        )}
        <span className="text-muted">
          Fuerza <span className="num">{ev.fuerza}</span>
          {ev.tipo_mencion ? ` · ${ev.tipo_mencion}` : ""}
          {ev.sentimiento ? ` · ${ev.sentimiento}` : ""}
        </span>
      </div>
      <p className="mt-2 text-muted">
        <span className="sr-only">Pregunta: </span>«{e.prompt}»
      </p>
      <blockquote
        className={`mt-2 whitespace-pre-line border-l-2 border-line pl-3 leading-6 ${abierto ? "" : "line-clamp-4"}`}
      >
        <Resaltado texto={e.texto_respuesta} marca={marca} />
      </blockquote>
      <div className="mt-2 flex flex-wrap items-center justify-between gap-2 text-meta text-muted">
        <span>
          {ev.necesita_revision && (
            <span className="pill mr-1.5 bg-pill-warn-bg text-pill-warn-ink" title="El juez dudó: conviene que la revise una persona">
              Revisar
            </span>
          )}
          {ORIGEN[ev.origen] ?? ev.origen} · confianza <span className="num">{fmtPct(ev.confianza)}</span>
          {e.fuentes.length > 0 && ` · fuentes: ${e.fuentes.join(", ")}`}
        </span>
        <button type="button" className="font-medium text-ink underline-offset-2 hover:underline" onClick={() => setAbierto((v) => !v)} aria-expanded={abierto}>
          {abierto ? "Recoger respuesta" : "Ver respuesta completa"}
        </button>
      </div>
    </li>
  );
}

interface Props {
  studyId: string;
  finding: Finding | null;
  marcas: Brand[];
  onClose: () => void;
}

/** Panel lateral con las evaluaciones que prueban un hallazgo. */
export function EvidenceDrawer({ studyId, finding, marcas, onClose }: Props) {
  const ids = finding?.evaluation_ids.slice(0, EVIDENCIAS_MAX) ?? [];
  const q = useEvidence(studyId, ids, Boolean(finding));
  const ref = useRef<HTMLDivElement>(null);
  const previo = useRef<Element | null>(null);

  useEffect(() => {
    if (!finding) return;
    previo.current = document.activeElement;
    ref.current?.focus();
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    document.addEventListener("keydown", onKey);
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = "";
      (previo.current as HTMLElement | null)?.focus?.();
    };
  }, [finding, onClose]);

  if (!finding) return null;
  const porId = new Map(marcas.map((b) => [b.id, b]));
  const cargadas = q.data ?? [];
  const sinCargar = finding.evaluation_ids.length - cargadas.length;

  return (
    <div className="fixed inset-0 z-40 flex justify-end">
      <div className="absolute inset-0 bg-black/30" aria-hidden onClick={onClose} />
      <div
        ref={ref}
        role="dialog"
        aria-modal="true"
        aria-labelledby="evidencias-titulo"
        tabIndex={-1}
        className="relative flex h-full w-full max-w-[600px] flex-col bg-surface shadow-[0_0_32px_rgba(0,0,0,0.18)] outline-none"
      >
        <div className="flex items-start justify-between gap-4 border-b border-line px-5 py-4">
          <div className="min-w-0">
            <h2 id="evidencias-titulo" className="text-section font-semibold">
              {finding.titulo}
            </h2>
            <p className="mt-1 text-meta text-muted">
              <span className="num font-medium text-ink">{fmtCifra(finding)}</span> · {finding.origen_cifra} ·{" "}
              {finding.evaluation_ids.length} evaluaciones
            </p>
          </div>
          <button type="button" className="btn-ghost h-8 w-8 flex-none px-0" onClick={onClose} aria-label="Cerrar evidencias">
            <svg aria-hidden width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
              <path d="M4 4l8 8M12 4l-8 8" strokeLinecap="round" />
            </svg>
          </button>
        </div>
        <div className="flex-1 overflow-y-auto px-5">
          {q.isPending && <p className="py-6 text-muted">Cargando evaluaciones…</p>}
          {q.isError && (
            <div className="py-5">
              <p className="text-muted">
                La API no devolvió el texto de las evaluaciones. Estos son sus identificadores:
              </p>
              <ul className="mt-3 flex flex-wrap gap-1.5">
                {finding.evaluation_ids.map((id) => (
                  <li key={id}>
                    <code className="rounded-chip bg-raised px-1.5 py-0.5 font-mono text-[12px]">{id}</code>
                  </li>
                ))}
              </ul>
            </div>
          )}
          {q.data && (
            <ul aria-label="Evaluaciones que prueban el hallazgo">
              {cargadas.map((e) => (
                <Item key={e.evaluation.id} e={e} marca={porId.get(e.evaluation.brand_id)} />
              ))}
            </ul>
          )}
        </div>
        {q.data && sinCargar > 0 && (
          <footer className="max-h-[40%] overflow-y-auto border-t border-line px-5 py-3 text-meta text-muted">
            <details>
              <summary className="cursor-pointer">
                Se muestran {cargadas.length} de {finding.evaluation_ids.length} evaluaciones. Ver todos los
                identificadores
              </summary>
              <ul className="mt-2 flex flex-wrap gap-1.5">
                {finding.evaluation_ids.map((id) => (
                  <li key={id}>
                    <code className="rounded-chip bg-raised px-1.5 py-0.5 font-mono text-[12px] text-ink">{id}</code>
                  </li>
                ))}
              </ul>
            </details>
          </footer>
        )}
      </div>
    </div>
  );
}
