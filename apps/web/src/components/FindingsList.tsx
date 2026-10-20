import { useCallback, useState } from "react";
import { fmtCifra, fmtPct } from "../lib/format";
import { FASE_LABEL } from "../lib/study";
import type { Brand, Finding, Talla } from "../types/schemas";
import { EvidenceDrawer } from "./EvidenceDrawer";
import { Panel } from "./Panel";

const IMPACTO: Record<Talla, string> = { L: "Impacto alto", M: "Impacto medio", S: "Impacto bajo" };
const ORDEN_IMPACTO: Record<Talla, number> = { L: 0, M: 1, S: 2 };

interface Props {
  studyId: string;
  findings: Finding[];
  marcas: Brand[];
}

/** Hallazgos con su cifra, de dónde sale y su confianza; cada uno abre sus evidencias. */
export function FindingsList({ studyId, findings, marcas }: Props) {
  const [abierto, setAbierto] = useState<Finding | null>(null);
  const cerrar = useCallback(() => setAbierto(null), []);
  const ordenados = [...findings].sort((a, b) => ORDEN_IMPACTO[a.impacto] - ORDEN_IMPACTO[b.impacto]);

  return (
    <Panel title="Hallazgos" id="hallazgos" meta={`${findings.length} hallazgos, de mayor a menor impacto`} flush>
      <ul>
        {ordenados.map((f) => (
          <li
            key={f.id}
            data-testid="hallazgo"
            className="grid gap-x-6 gap-y-2 border-t border-rule px-5 py-4 first:border-t-0 sm:grid-cols-[120px_minmax(0,1fr)_auto] sm:items-start"
          >
            <p className="num text-kpi font-semibold tracking-[-0.01em]">{fmtCifra(f)}</p>
            <div className="min-w-0">
              <h3 className="font-semibold">{f.titulo}</h3>
              <p className="mt-0.5 text-muted">{f.descripcion}</p>
              <p className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-meta text-muted">
                <span className={`pill ${f.impacto === "L" ? "bg-accent-soft text-accent-ink" : "bg-raised text-ink"}`}>
                  {IMPACTO[f.impacto]}
                </span>
                <span>
                  Confianza <span className="num font-medium text-ink">{fmtPct(f.confianza)}</span>
                </span>
                <span>Origen: {f.origen_cifra}</span>
                {f.fase_embudo && <span>Fase: {FASE_LABEL[f.fase_embudo]}</span>}
              </p>
            </div>
            <button
              type="button"
              className="btn-secondary h-8 justify-self-start sm:justify-self-end"
              onClick={() => setAbierto(f)}
              aria-haspopup="dialog"
            >
              Ver evidencias <span className="num text-muted">{f.evaluation_ids.length}</span>
            </button>
          </li>
        ))}
      </ul>
      <EvidenceDrawer studyId={studyId} finding={abierto} marcas={marcas} onClose={cerrar} />
    </Panel>
  );
}
