import { useId } from "react";
import { fmtCifra } from "../lib/format";
import { FASE_LABEL, PALANCA_LABEL } from "../lib/study";
import type { Action, Finding, Talla } from "../types/schemas";

const TALLAS: Talla[] = ["S", "M", "L"];

function Tallas({
  label,
  value,
  onChange,
  disabled,
}: {
  label: string;
  value: Talla;
  onChange: (t: Talla) => void;
  disabled: boolean;
}) {
  return (
    <fieldset>
      <legend className="mb-1 text-meta text-muted">{label}</legend>
      <div className="inline-flex gap-0.5 rounded-control bg-raised p-0.5">
        {TALLAS.map((t) => (
          <label
            key={t}
            className={`flex h-7 w-8 items-center justify-center rounded-[5px] text-meta transition-colors has-[:focus-visible]:outline has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-accent ${
              value === t ? "bg-surface font-semibold text-ink" : "text-muted"
            } ${disabled ? "cursor-default" : "cursor-pointer hover:text-ink"}`}
          >
            <input
              type="radio"
              className="sr-only"
              checked={value === t}
              disabled={disabled}
              onChange={() => onChange(t)}
              aria-label={`${label} ${t}`}
            />
            {t}
          </label>
        ))}
      </div>
    </fieldset>
  );
}

interface Props {
  action: Action;
  original: Action;
  findings: Map<string, Finding>;
  restricciones: string[];
  readOnly: boolean;
  onChange: (a: Action) => void;
}

/** Una acción del plan: qué es, qué hallazgos la justifican y sus campos editables. */
export function ActionEditor({ action: a, original, findings, restricciones, readOnly, onChange }: Props) {
  const uid = useId();
  const set = (patch: Partial<Action>) => onChange({ ...a, ...patch });
  const editada = JSON.stringify(a) !== JSON.stringify(original);
  const ignoradas = restricciones.filter((r) => !a.restricciones_revisadas.includes(r));

  return (
    <article
      data-testid="accion"
      aria-labelledby={`${uid}-desc`}
      className="grid gap-x-8 gap-y-4 border-t border-rule px-5 py-5 first:border-t-0 lg:grid-cols-[minmax(0,1fr)_minmax(0,360px)]"
    >
      <div className="min-w-0">
        <div className="mb-1.5 flex flex-wrap items-center gap-2 text-meta text-muted">
          <span className="font-mono text-[12px] text-ink">{a.id}</span>
          <span className="pill bg-raised text-ink">{PALANCA_LABEL[a.palanca]}</span>
          {a.fase_embudo && <span>{FASE_LABEL[a.fase_embudo]}</span>}
          {a.motores_objetivo.length > 0 && <span>· {a.motores_objetivo.join(", ")}</span>}
          {a.dependencias.length > 0 && <span>· depende de {a.dependencias.join(", ")}</span>}
          {editada && (
            <span className="inline-flex items-center gap-1 font-medium text-accent-ink">
              <span aria-hidden className="h-1.5 w-1.5 rounded-full bg-accent" />
              Editada
            </span>
          )}
        </div>
        <h3 id={`${uid}-desc`} className="font-medium leading-6">
          {a.descripcion}
        </h3>
        <p className="mt-1 text-meta text-muted">Entregables: {a.entregables.join(" · ")}</p>

        <div className="mt-3">
          <p className="text-meta font-medium text-muted">La justifican</p>
          <ul className="mt-1 space-y-1">
            {a.finding_ids.map((fid) => {
              const f = findings.get(fid);
              return (
                <li key={fid} className="flex gap-2" data-testid="justificacion">
                  <span className="num w-[72px] flex-none text-right font-medium">{f ? fmtCifra(f) : "—"}</span>
                  <span className={f ? "" : "text-muted"}>{f ? f.titulo : `Hallazgo ${fid} no encontrado`}</span>
                </li>
              );
            })}
          </ul>
        </div>

        {restricciones.length > 0 && (
          <fieldset className="mt-3">
            <legend className="text-meta font-medium text-muted">Restricciones del brief revisadas</legend>
            <div className="mt-1 space-y-1">
              {restricciones.map((r) => {
                const ok = a.restricciones_revisadas.includes(r);
                return (
                  <label key={r} className={`flex items-start gap-2 ${ok ? "" : "text-pill-warn-ink"}`}>
                    <input
                      type="checkbox"
                      className="mt-[3px] h-4 w-4 flex-none accent-[var(--accent)]"
                      checked={ok}
                      disabled={readOnly}
                      onChange={(e) =>
                        set({
                          restricciones_revisadas: e.target.checked
                            ? [...a.restricciones_revisadas, r]
                            : a.restricciones_revisadas.filter((x) => x !== r),
                        })
                      }
                    />
                    <span>{r}</span>
                  </label>
                );
              })}
            </div>
            {ignoradas.length > 0 && !readOnly && (
              <p className="mt-1 text-meta text-pill-warn-ink">Sin revisar: marca la casilla cuando la acción la cumpla.</p>
            )}
          </fieldset>
        )}
      </div>

      <div className="grid content-start gap-3 sm:grid-cols-[auto_auto_minmax(0,1fr)]">
        <Tallas label="Esfuerzo" value={a.esfuerzo} disabled={readOnly} onChange={(t) => set({ esfuerzo: t })} />
        <Tallas label="Impacto" value={a.impacto} disabled={readOnly} onChange={(t) => set({ impacto: t })} />
        <div>
          <label htmlFor={`${uid}-plazo`} className="mb-1 block text-meta text-muted">
            Plazo (semanas)
          </label>
          <input
            id={`${uid}-plazo`}
            type="number"
            inputMode="numeric"
            min={1}
            className="field num"
            value={a.plazo_semanas}
            disabled={readOnly}
            onChange={(e) => set({ plazo_semanas: Math.max(1, Math.round(Number(e.target.value) || 1)) })}
          />
        </div>
        <div className="sm:col-span-3">
          <label htmlFor={`${uid}-resp`} className="mb-1 block text-meta text-muted">
            Responsable
          </label>
          <input
            id={`${uid}-resp`}
            className="field"
            value={a.responsable}
            disabled={readOnly}
            onChange={(e) => set({ responsable: e.target.value })}
          />
        </div>
        <div className="sm:col-span-3">
          <label htmlFor={`${uid}-kpi`} className="mb-1 block text-meta text-muted">
            KPI
          </label>
          <input
            id={`${uid}-kpi`}
            className="field"
            value={a.kpi}
            disabled={readOnly}
            onChange={(e) => set({ kpi: e.target.value })}
          />
        </div>
      </div>
    </article>
  );
}
