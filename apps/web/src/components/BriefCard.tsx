import { fmtEur } from "../lib/format";
import type { BriefSummary } from "../types/schemas";

function Fila({ label, value }: { label: string; value: string }) {
  return (
    <div className="grid grid-cols-[96px_minmax(0,1fr)] gap-3 py-1.5">
      <dt className="text-muted">{label}</dt>
      <dd>{value}</dd>
    </div>
  );
}

/** Ficha del brief tal como la ha entendido el sistema. */
export function BriefCard({ brief }: { brief: BriefSummary }) {
  const p = brief.presupuesto_anual_eur;
  return (
    <section aria-labelledby="brief-titulo" className="panel px-5 py-4">
      <h2 id="brief-titulo" className="text-section font-semibold">
        Brief leído
      </h2>
      <p className="mt-1 text-muted">
        {brief.marca} · {brief.subsector}
      </p>
      <dl className="mt-3 divide-y divide-rule text-body">
        <Fila label="Ciudades" value={brief.ciudades.join(" · ")} />
        <Fila label="Prioridades" value={brief.servicios_prioritarios.join(" · ")} />
        <Fila label="Competidores" value={brief.competidores_declarados.join(" · ") || "No declara"} />
        <Fila label="Presupuesto" value={p ? `${fmtEur(p[0], 0)} – ${fmtEur(p[1], 0)} al año` : "No declara"} />
        <Fila label="Restricciones" value={brief.restricciones.join(" · ") || "Ninguna"} />
      </dl>
    </section>
  );
}
