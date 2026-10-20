import { useTraces } from "../api/hooks";
import { fmtEur, fmtInt, fmtMs } from "../lib/format";
import { Panel } from "./Panel";
import { Skeleton } from "./States";

/** Coste, modelo y versión de prompt de cada nodo del grafo, como los registra la `Trace`. */
export function TracesPanel({ studyId, estado }: { studyId: string; estado: string }) {
  const q = useTraces(studyId, estado);
  const trazas = q.data ?? [];
  const total = trazas.reduce(
    (s, t) => ({
      tokens_in: s.tokens_in + t.tokens_in,
      tokens_out: s.tokens_out + t.tokens_out,
      coste: s.coste + t.coste_eur,
      ms: s.ms + t.duracion_ms,
    }),
    { tokens_in: 0, tokens_out: 0, coste: 0, ms: 0 },
  );

  return (
    <Panel title="Trazas" id="trazas" meta={q.data && `${trazas.length} llamadas registradas`} flush>
      {q.isPending && (
        <div className="space-y-2 px-5 pb-3">
          <Skeleton className="h-6 w-full" />
          <Skeleton className="h-6 w-full" />
        </div>
      )}
      {q.isError && <p className="px-5 pb-3 text-muted">La API no ha devuelto las trazas de este estudio.</p>}
      {q.data && trazas.length === 0 && <p className="px-5 pb-3 text-muted">Aún no hay llamadas registradas.</p>}
      {trazas.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[760px] text-body" data-testid="trazas">
            <caption className="sr-only">Coste y modelo por nodo</caption>
            <thead>
              <tr className="text-meta text-muted">
                <th scope="col" className="px-5 pb-2 text-left font-normal">Nodo</th>
                <th scope="col" className="pb-2 text-left font-normal">Modelo</th>
                <th scope="col" className="pb-2 text-left font-normal">Prompt</th>
                <th scope="col" className="pb-2 text-right font-normal">Tokens entrada</th>
                <th scope="col" className="pb-2 text-right font-normal">Tokens salida</th>
                <th scope="col" className="pb-2 text-right font-normal">Duración</th>
                <th scope="col" className="px-5 pb-2 text-right font-normal">Coste</th>
              </tr>
            </thead>
            <tbody className="num">
              {trazas.map((t, i) => (
                <tr key={`${t.nodo}-${i}`} className="border-t border-rule">
                  <th scope="row" className="px-5 py-2 text-left font-medium">{t.nodo}</th>
                  <td className="py-2">{t.modelo}</td>
                  <td className="py-2 text-muted">{t.prompt_version}</td>
                  <td className="py-2 text-right text-muted">{fmtInt(t.tokens_in)}</td>
                  <td className="py-2 text-right text-muted">{fmtInt(t.tokens_out)}</td>
                  <td className="py-2 text-right text-muted">{fmtMs(t.duracion_ms)}</td>
                  <td className="px-5 py-2 text-right">
                    <span className="font-medium">{fmtEur(t.coste_eur, 4)}</span>
                  </td>
                </tr>
              ))}
            </tbody>
            <tfoot className="num">
              <tr className="border-t border-line">
                <th scope="row" colSpan={3} className="px-5 py-2.5 text-left font-semibold">
                  Total
                </th>
                <td className="py-2.5 text-right">{fmtInt(total.tokens_in)}</td>
                <td className="py-2.5 text-right">{fmtInt(total.tokens_out)}</td>
                <td className="py-2.5 text-right">{fmtMs(total.ms)}</td>
                <td className="px-5 py-2.5 text-right font-semibold" data-testid="coste-total">
                  {fmtEur(total.coste, 4)}
                </td>
              </tr>
            </tfoot>
          </table>
        </div>
      )}
    </Panel>
  );
}
