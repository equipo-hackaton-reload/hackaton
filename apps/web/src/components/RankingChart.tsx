import { fmtNum, ordinal } from "../lib/format";
import type { Metrics } from "../types/schemas";
import { Panel } from "./Panel";

interface Props {
  metrics: Metrics;
  nombre: (id: string) => string;
}

/** Ranking por Score de Citación: la marca foco en el acento, el líder en tinta, el resto en gris. */
export function RankingChart({ metrics, nombre }: Props) {
  const foco = metrics.score_global.score;
  const filas = metrics.ranking.map((id, i) => ({
    id,
    puesto: i + 1,
    score: metrics.scores.find((s) => s.brand_id === id)?.score ?? null,
  }));
  const max = Math.max(...filas.map((f) => f.score ?? 0), 1);
  const lider = filas.find((f) => f.id === metrics.lider_id);
  const brecha = foco != null && lider?.score != null ? lider.score - foco : null;

  return (
    <Panel
      title="Ranking frente a competidores"
      id="ranking"
      meta={brecha != null && <span className="num">Brecha con el líder: {fmtNum(brecha)} pts</span>}
    >
      <ol className="space-y-1" aria-label="Marcas ordenadas por Score de Citación">
        {filas.map((f) => {
          const esFoco = f.id === metrics.marca_foco_id;
          const esLider = f.id === metrics.lider_id;
          return (
            <li
              key={f.id}
              data-testid={esFoco ? "ranking-foco" : undefined}
              className={`grid grid-cols-[32px_minmax(0,230px)_minmax(0,1fr)_52px] items-center gap-3 rounded-control px-1.5 py-1 ${
                esFoco ? "bg-accent-soft" : ""
              }`}
            >
              <span className="num text-meta text-muted">{ordinal(f.puesto)}</span>
              <span className={`truncate ${esFoco ? "font-semibold text-accent-ink" : esLider ? "font-medium" : ""}`} title={nombre(f.id)}>
                {nombre(f.id)}
              </span>
              <span aria-hidden className="h-2.5">
                <span
                  className={`block h-2.5 rounded-r-[3px] ${esFoco ? "bg-accent" : esLider ? "bg-ink" : "bg-[var(--bar)]"}`}
                  style={{ width: `${((f.score ?? 0) / max) * 100}%` }}
                />
              </span>
              <span className={`num text-right ${esFoco || esLider ? "font-medium" : "text-muted"}`}>
                {fmtNum(f.score)}
              </span>
            </li>
          );
        })}
      </ol>
    </Panel>
  );
}
