import { Panel } from "./Panel";
import { fmtNum, fmtPct } from "../lib/format";
import type { PlanQuality, SimulationResult } from "../types/api";

function rango(minimo: number, esperado: number, maximo: number, percent = false): string {
  const format = percent ? fmtPct : (value: number) => fmtNum(value, 1);
  return `${format(minimo)} – ${format(esperado)} – ${format(maximo)}`;
}

export function SimulationCard({
  simulation,
  quality,
}: {
  simulation: SimulationResult;
  quality?: PlanQuality;
}) {
  return (
    <Panel title="Proyección del plan" meta={<span className="text-meta text-muted">{simulation.modelo_version}</span>}>
      <div className="space-y-5">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <p className="text-muted">Score actual</p>
          <p className="num text-xl font-semibold">{fmtNum(simulation.score_actual, 2)} <span className="text-sm font-normal text-muted">/ 100</span></p>
        </div>
        {/* En móvil cada fila se apila: la tabla de tres columnas no cabe sin scroll lateral. */}
        <div>
          <table className="block w-full text-body sm:table">
            <caption className="sr-only">Proyección por fase del plan</caption>
            <thead className="max-sm:sr-only">
              <tr className="text-meta text-muted">
                <th scope="col" className="pb-2 text-left font-normal">Fase</th>
                <th scope="col" className="pb-2 text-right font-normal">Visibilidad espontánea<br />mín. – esperado – máx.</th>
                <th scope="col" className="pb-2 text-right font-normal">Score<br />mín. – esperado – máx.</th>
              </tr>
            </thead>
            <tbody className="block sm:table-row-group">
              {simulation.proyecciones.map((projection) => (
                <tr key={projection.fase} className="block border-t border-rule py-3 sm:table-row sm:py-0">
                  <th scope="row" className="block text-left font-medium sm:table-cell sm:py-3 sm:font-normal">{projection.fase}</th>
                  <td className="num mt-1 flex justify-between gap-3 text-meta sm:table-cell sm:py-3 sm:text-right sm:text-body">
                    <span aria-hidden="true" className="text-muted sm:hidden">Visibilidad</span>
                    {rango(projection.tasa_espontanea.minimo, projection.tasa_espontanea.esperado, projection.tasa_espontanea.maximo, true)}
                  </td>
                  <td className="num flex justify-between gap-3 text-meta sm:table-cell sm:py-3 sm:text-right sm:text-body">
                    <span aria-hidden="true" className="text-muted sm:hidden">Score</span>
                    {rango(projection.score.minimo, projection.score.esperado, projection.score.maximo)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {quality?.nota && <p className="rounded-control bg-raised px-3 py-2 text-meta text-muted">{quality.nota}</p>}
        <details className="text-meta">
          <summary className="cursor-pointer font-medium">Supuestos y límites de la estimación</summary>
          <ul className="mt-2 list-disc space-y-1 pl-5 text-muted">
            {simulation.supuestos.map((assumption) => <li key={assumption}>{assumption}</li>)}
          </ul>
          <p className="mt-2 text-muted">{simulation.advertencia}</p>
        </details>
      </div>
    </Panel>
  );
}
