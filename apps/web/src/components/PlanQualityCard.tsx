import { Panel } from "./Panel";
import { fmtNum, fmtPct } from "../lib/format";
import type { PlanQuality } from "../types/api";

export function PlanQualityCard({ quality }: { quality: PlanQuality }) {
  return (
    <Panel title="Calidad del plan" meta={<span className="text-meta text-muted">{quality.modelo}</span>}>
      <div className="space-y-4">
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {[
            ["Específicas", quality.pct_especificas],
            ["Coherentes", quality.pct_coherentes],
            ["Restricciones", quality.pct_respetan_restricciones],
            ["Realistas", quality.pct_realistas],
          ].map(([label, value]) => (
            <div key={label} className="rounded-control bg-raised px-3 py-2">
              <p className="text-meta text-muted">{label}</p>
              <p className="num mt-1 text-lg font-semibold">{fmtPct(value as number | null)}</p>
            </div>
          ))}
        </div>
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <p className="text-muted">Calidad media</p>
          <p className="num text-xl font-semibold">{fmtNum(quality.calidad_media, 2)} <span className="text-sm font-normal text-muted">/ 3</span></p>
        </div>
        {quality.por_debajo_umbral.length > 0 && (
          <p role="status" className="rounded-control bg-pill-warn-bg px-3 py-2 text-meta text-pill-warn-ink">
            Revisa las acciones {quality.por_debajo_umbral.join(", ")}: están por debajo del umbral de calidad.
          </p>
        )}
      </div>
    </Panel>
  );
}
