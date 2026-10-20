import { fmtNum, ordinal } from "../lib/format";
import type { Metrics } from "../types/schemas";
import { Panel } from "./Panel";

/** Los cuatro componentes del Score de Citación y su peso máximo (metodología del kit). */
const COMPONENTES = [
  { key: "aparicion", label: "Aparición", peso: 30 },
  { key: "posicion", label: "Posición", peso: 20 },
  { key: "fuerza", label: "Fuerza", peso: 30 },
  { key: "calidad_fuente", label: "Calidad de fuente", peso: 20 },
] as const;

const MOTORES = ["ChatGPT", "Gemini", "Perplexity", "Claude"] as const;

interface Props {
  metrics: Metrics;
  nombre: (id: string) => string;
}

/**
 * Score global con su desglose 30/20/30/20. Cada pista mide el peso del componente; el relleno es
 * lo que suma la marca y la marca vertical, lo que suma el líder.
 */
export function ScoreCard({ metrics, nombre }: Props) {
  const s = metrics.score_global;
  const lider = metrics.scores.find((x) => x.brand_id === metrics.lider_id);
  const puesto = metrics.ranking.indexOf(metrics.marca_foco_id) + 1;
  const porMotor = MOTORES.flatMap((motor) =>
    metrics.scores_por_motor.filter((x) => x.brand_id === metrics.marca_foco_id && x.motor === motor),
  );
  return (
    <Panel
      title="Score de Citación"
      id="score"
      meta={<span className="num">n = {s.n_evaluaciones} evaluaciones espontáneas</span>}
    >
      <div className="flex flex-wrap items-baseline gap-x-3">
        <p className="num text-answer font-semibold tracking-[-0.02em]" data-testid="score-global">
          {fmtNum(s.score)}
        </p>
        <p className="text-muted">
          <span className="num">de 100</span>
          {puesto > 0 && (
            <>
              {" · "}
              <span className="font-medium text-ink">
                {ordinal(puesto)} de {metrics.ranking.length}
              </span>
            </>
          )}
        </p>
      </div>
      <table className="mt-5 w-full text-body">
        <caption className="sr-only">Desglose del Score de Citación por componente</caption>
        <thead>
          <tr className="text-meta text-muted">
            <th scope="col" className="pb-2 text-left font-normal">
              Componente
            </th>
            <th scope="col" className="w-[44%] pb-2 text-left font-normal">
              <span className="sr-only">Barra</span>
            </th>
            <th scope="col" className="pb-2 text-right font-normal">
              Marca
            </th>
            <th scope="col" className="pb-2 pl-3 text-right font-normal">
              Líder
            </th>
          </tr>
        </thead>
        <tbody>
          {COMPONENTES.map((c) => {
            const v = s[c.key];
            const l = lider?.[c.key] ?? null;
            return (
              <tr key={c.key}>
                <th scope="row" className="py-1.5 pr-3 text-left font-normal">
                  {c.label} <span className="num text-meta text-muted">{c.peso}</span>
                </th>
                <td className="py-1.5">
                  <div className="relative h-2 rounded-full bg-[var(--track)]" aria-hidden>
                    <div
                      className="h-2 rounded-full bg-accent"
                      style={{ width: `${((v ?? 0) / c.peso) * 100}%` }}
                    />
                    {l != null && (
                      <div
                        className="absolute -top-1 h-4 w-0.5 rounded-full bg-ink"
                        style={{ left: `calc(${(l / c.peso) * 100}% - 1px)` }}
                      />
                    )}
                  </div>
                </td>
                <td className="num py-1.5 text-right font-medium">{fmtNum(v)}</td>
                <td className="num py-1.5 pl-3 text-right text-muted">{fmtNum(l)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
      {lider && (
        <p className="mt-4 flex items-center gap-4 text-meta text-muted">
          <span className="inline-flex items-center gap-1.5">
            <span aria-hidden className="h-2 w-3 rounded-full bg-accent" /> {nombre(metrics.marca_foco_id)}
          </span>
          <span className="inline-flex items-center gap-1.5">
            <span aria-hidden className="h-3 w-0.5 rounded-full bg-ink" /> {nombre(lider.brand_id)}, líder
          </span>
        </p>
      )}
      {porMotor.length > 0 && (
        <div className="mt-5 border-t border-rule pt-4">
          <h3 className="text-meta text-muted">Score por motor</h3>
          <dl className="mt-2 grid grid-cols-4 gap-3" data-testid="score-por-motor">
            {porMotor.map((m) => (
              <div key={m.motor}>
                <dt className="text-meta text-muted">{m.motor}</dt>
                <dd className="num text-section font-medium">{fmtNum(m.score)}</dd>
              </div>
            ))}
          </dl>
        </div>
      )}
    </Panel>
  );
}
