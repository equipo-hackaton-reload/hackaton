import { DASH, fmtInt } from "../lib/format";
import type { Metrics } from "../types/schemas";
import { Panel } from "./Panel";

const N = 6;

interface Props {
  metrics: Metrics;
  nombreLider: string;
}

/** Dominios que citan los motores cuando aparece la marca, y los que acompañan al líder y no a ella. */
export function SourcesPanel({ metrics, nombreLider }: Props) {
  const propias = metrics.top_fuentes
    .filter((s) => s.brand_id === metrics.marca_foco_id)
    .sort((a, b) => b.apariciones - a.apariciones)
    .slice(0, N);
  const brecha = [...metrics.brecha_fuentes].sort((a, b) => b.brecha - a.brecha).slice(0, N);

  return (
    <div className="grid items-start gap-6 lg:grid-cols-2">
      <Panel title="Brecha de fuentes frente al líder" id="brecha" meta={`${nombreLider}`} flush>
        {brecha.length === 0 ? (
          <p className="px-5 pb-3 text-muted">El líder no se apoya en fuentes que no citen también a la marca.</p>
        ) : (
          <table className="w-full text-body" data-testid="brecha-fuentes">
            <caption className="sr-only">Dominios que acompañan al líder más que a la marca</caption>
            <thead>
              <tr className="text-meta text-muted">
                <th scope="col" className="px-5 pb-2 text-left font-normal">Dominio</th>
                <th scope="col" className="pb-2 text-right font-normal">Líder</th>
                <th scope="col" className="pb-2 text-right font-normal">Marca</th>
                <th scope="col" className="px-5 pb-2 text-right font-normal">Brecha</th>
              </tr>
            </thead>
            <tbody className="num">
              {brecha.map((g) => (
                <tr key={g.dominio} className="border-t border-rule">
                  <th scope="row" className="max-w-0 px-5 py-2 text-left font-normal">
                    <span className="block truncate" title={g.dominio}>{g.dominio}</span>
                    <span className="block truncate text-meta text-muted">{g.tipo ?? "Fuera del catálogo"}</span>
                  </th>
                  <td className="py-2 text-right">{fmtInt(g.con_lider)}</td>
                  <td className="py-2 text-right text-muted">{fmtInt(g.con_marca)}</td>
                  <td className="px-5 py-2 text-right font-medium">+{fmtInt(g.brecha)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Panel>
      <Panel title="Fuentes que citan a la marca" id="fuentes" meta="respuestas espontáneas" flush>
        {propias.length === 0 ? (
          <p className="px-5 pb-3 text-muted">Ningún motor ha citado una fuente al mencionar la marca.</p>
        ) : (
          <table className="w-full text-body" data-testid="top-fuentes">
            <caption className="sr-only">Dominios más citados cuando aparece la marca</caption>
            <thead>
              <tr className="text-meta text-muted">
                <th scope="col" className="px-5 pb-2 text-left font-normal">Dominio</th>
                <th scope="col" className="pb-2 text-right font-normal">Calidad</th>
                <th scope="col" className="px-5 pb-2 text-right font-normal">Citas</th>
              </tr>
            </thead>
            <tbody className="num">
              {propias.map((s) => (
                <tr key={s.dominio} className="border-t border-rule">
                  <th scope="row" className="max-w-0 px-5 py-2 text-left font-normal">
                    <span className="block truncate" title={s.dominio}>{s.dominio}</span>
                    <span className="block truncate text-meta text-muted">{s.tipo ?? "Fuera del catálogo"}</span>
                  </th>
                  <td className="py-2 text-right text-muted">{s.calidad == null ? DASH : s.calidad.toLocaleString("es-ES")}</td>
                  <td className="px-5 py-2 text-right font-medium">{fmtInt(s.apariciones)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Panel>
    </div>
  );
}
