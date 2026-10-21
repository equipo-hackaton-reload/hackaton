import { fmtEur, fmtInt } from "../lib/format";
import type { CostEstimate } from "../types/api";

/** Estimación previa de coste tal como la calcula la API: llamadas, coste, tope y desglose. */
export function CostEstimateView({ estimate }: { estimate: CostEstimate }) {
  const { llamadas, coste_estimado_eur, presupuesto_max_eur } = estimate;
  const excede = coste_estimado_eur > presupuesto_max_eur;
  const desglose: [string, number | undefined][] = [
    ["Motores", estimate.coste_motores_eur],
    ["LLM", estimate.coste_llm_eur],
    ["Juez", estimate.coste_juez_eur],
    ["PlanGuard", estimate.coste_plan_guard_eur],
  ];
  const partes = desglose.filter((p): p is [string, number] => p[1] != null);
  return (
    <div data-testid="estimacion">
      <dl className="grid grid-cols-3 gap-3">
        <div>
          <dt className="text-meta text-muted">Llamadas</dt>
          <dd className="num mt-0.5 text-section font-medium">{fmtInt(llamadas)}</dd>
        </div>
        <div>
          <dt className="text-meta text-muted">Coste estimado</dt>
          <dd className={`num mt-0.5 text-section font-medium ${excede ? "text-negative" : ""}`}>{fmtEur(coste_estimado_eur)}</dd>
        </div>
        <div>
          <dt className="text-meta text-muted">Tope</dt>
          <dd className="num mt-0.5 text-section text-muted">{fmtEur(presupuesto_max_eur)}</dd>
        </div>
      </dl>
      {partes.length > 0 && (
        <p className="num mt-2 text-meta text-muted">
          {partes.map(([nombre, eur]) => `${nombre} ${fmtEur(eur)}`).join(" · ")}
          {estimate.juez ? ` (juez: ${estimate.juez})` : ""}
        </p>
      )}
      {excede && (
        <p className="mt-2 text-meta font-medium text-negative" data-testid="excede-tope">
          La estimación supera el tope de {fmtEur(presupuesto_max_eur)}.
        </p>
      )}
    </div>
  );
}
