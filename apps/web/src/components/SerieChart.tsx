import { useId, useState } from "react";
import { fmtDay, fmtNum } from "../lib/format";
import type { PuntoSerie } from "../types/tracking";

// Ancho parecido al del panel en escritorio: así el texto del SVG sale a su tamaño real.
const W = 1120;
const H = 340;
const M = { top: 28, right: 56, bottom: 36, left: 40 };

/** Dominio del eje Y a partir de las cifras que trae la serie (no se calcula ninguna cifra nueva). */
function dominio(puntos: PuntoSerie[]): [number, number] {
  const vals = puntos.flatMap((p) => [p.score, p.intervalo?.inf, p.intervalo?.sup, p.score_medio_competidores]);
  const nums = vals.filter((v): v is number => v != null);
  if (nums.length === 0) return [0, 100];
  const paso = 10;
  const lo = Math.max(0, Math.floor((Math.min(...nums) - 2) / paso) * paso);
  const hi = Math.min(100, Math.ceil((Math.max(...nums) + 2) / paso) * paso);
  return lo === hi ? [Math.max(0, lo - paso), Math.min(100, hi + paso)] : [lo, hi];
}

/** Tramos que se pueden unir con una línea: se cortan al cambiar el método (no comparables). */
function tramos(puntos: PuntoSerie[]): number[][] {
  const out: number[][] = [];
  puntos.forEach((p, i) => {
    if (i === 0 || !p.comparable_con_anterior) out.push([i]);
    else out[out.length - 1].push(i);
  });
  return out;
}

interface Props {
  puntos: PuntoSerie[];
  nombre: string;
}

/**
 * Evolución del Score de Citación: línea de la marca con la banda de su intervalo de confianza y la
 * media de los competidores. Las mediciones no comparables con la anterior cortan las líneas y se
 * marcan con un círculo hueco y una guía vertical.
 */
export function SerieChart({ puntos, nombre }: Props) {
  const tooltipId = useId();
  const [activo, setActivo] = useState<number | null>(null);
  const [y0, y1] = dominio(puntos);
  const ancho = W - M.left - M.right;
  const alto = H - M.top - M.bottom;
  const x = (i: number) => M.left + (puntos.length === 1 ? ancho / 2 : (i / (puntos.length - 1)) * ancho);
  const y = (v: number) => M.top + alto - ((v - y0) / (y1 - y0)) * alto;
  const ticks = Array.from({ length: Math.round((y1 - y0) / 10) + 1 }, (_, k) => y0 + k * 10);
  const grupos = tramos(puntos);

  const linea = (idx: number[], valor: (p: PuntoSerie) => number | null) => {
    const conValor = idx.filter((i) => valor(puntos[i]) != null);
    return conValor.map((i, k) => `${k ? "L" : "M"}${x(i)},${y(valor(puntos[i])!)}`).join(" ");
  };
  const banda = (idx: number[]) => {
    const con = idx.filter((i) => puntos[i].intervalo);
    if (con.length < 2) return null;
    const arriba = con.map((i) => `${x(i)},${y(puntos[i].intervalo!.sup)}`);
    const abajo = [...con].reverse().map((i) => `${x(i)},${y(puntos[i].intervalo!.inf)}`);
    return `M${arriba.join(" L")} L${abajo.join(" L")} Z`;
  };

  const ultimo = puntos.length - 1;
  const p = activo != null ? puntos[activo] : null;

  return (
    <div>
      <ul className="mb-3 flex flex-wrap gap-x-5 gap-y-1.5 text-meta text-muted" aria-label="Leyenda">
        <li className="flex items-center gap-2">
          <span aria-hidden className="h-0.5 w-5 rounded-full bg-accent" /> {nombre}
        </li>
        <li className="flex items-center gap-2">
          <span aria-hidden className="h-3 w-5 rounded-chip bg-accent opacity-20" /> Intervalo de confianza
        </li>
        <li className="flex items-center gap-2">
          <svg aria-hidden width="20" height="4"><line x1="0" y1="2" x2="20" y2="2" stroke="var(--bar)" strokeWidth="2" strokeDasharray="4 3" /></svg>
          Media de competidores
        </li>
        <li className="flex items-center gap-2">
          <svg aria-hidden width="12" height="12"><circle cx="6" cy="6" r="4" fill="var(--surface)" stroke="var(--accent)" strokeWidth="2" /></svg>
          No comparable con la anterior
        </li>
      </ul>

      {/* En móvil el gráfico conserva un ancho legible y se desplaza en horizontal. */}
      <div className="-mx-1 overflow-x-auto px-1">
        <div className="relative min-w-[640px]">
          <svg
            viewBox={`0 0 ${W} ${H}`}
            className="h-auto w-full overflow-visible"
            role="group"
            aria-label={`Evolución del Score de Citación de ${nombre}: ${puntos.length} mediciones. La tabla de mediciones tiene los mismos datos.`}
            onMouseLeave={() => setActivo(null)}
            data-testid="serie-grafico"
          >
            {ticks.map((t) => (
              <g key={t}>
                <line x1={M.left} x2={W - M.right} y1={y(t)} y2={y(t)} stroke="var(--rule)" strokeWidth="1" />
                <text x={M.left - 8} y={y(t)} dy="0.32em" textAnchor="end" className="fill-[var(--faint)] text-[11px]">
                  {fmtNum(t, 0)}
                </text>
              </g>
            ))}

            {puntos.map((pt, i) =>
              i > 0 && !pt.comparable_con_anterior ? (
                <g key={`rule-${pt.study_id}`} aria-hidden>
                  <line x1={(x(i - 1) + x(i)) / 2} x2={(x(i - 1) + x(i)) / 2} y1={M.top - 8} y2={M.top + alto} stroke="var(--control)" strokeDasharray="3 3" />
                  <text x={(x(i - 1) + x(i)) / 2} y={M.top - 12} textAnchor="middle" className="fill-[var(--muted)] text-[11px]">
                    Cambio de método
                  </text>
                </g>
              ) : null,
            )}

            {grupos.map((g) => {
              const d = banda(g);
              return d ? <path key={`b-${g[0]}`} d={d} fill="var(--accent)" opacity="0.14" /> : null;
            })}
            {grupos.map((g) => (
              <path key={`c-${g[0]}`} d={linea(g, (pt) => pt.score_medio_competidores)} fill="none" stroke="var(--bar)" strokeWidth="2" strokeDasharray="4 3" strokeLinejoin="round" />
            ))}
            {grupos.map((g) => (
              <path key={`s-${g[0]}`} d={linea(g, (pt) => pt.score)} fill="none" stroke="var(--accent)" strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" />
            ))}

            {puntos.map((pt, i) => {
              const etiqueta = `${fmtDay(pt.fecha)}: score ${fmtNum(pt.score)}${
                pt.intervalo ? ` (entre ${fmtNum(pt.intervalo.inf)} y ${fmtNum(pt.intervalo.sup)})` : ""
              }, media de competidores ${fmtNum(pt.score_medio_competidores)}${
                pt.comparable_con_anterior || i === 0 ? "" : `. No comparable con la anterior: ${pt.motivos_no_comparable.join("; ")}`
              }`;
              const hueco = i > 0 && !pt.comparable_con_anterior;
              return (
                <g
                  key={pt.study_id}
                  tabIndex={0}
                  role="img"
                  aria-label={etiqueta}
                  aria-describedby={activo === i ? tooltipId : undefined}
                  onMouseEnter={() => setActivo(i)}
                  onFocus={() => setActivo(i)}
                  onBlur={() => setActivo(null)}
                  className="outline-none [&:focus-visible_circle.marca]:stroke-[var(--text)]"
                  data-testid={hueco ? "punto-no-comparable" : "punto"}
                >
                  {/* Zona de acierto más grande que la marca. */}
                  <rect x={x(i) - 18} y={M.top} width="36" height={alto} fill="transparent" />
                  {pt.score_medio_competidores != null && (
                    <circle cx={x(i)} cy={y(pt.score_medio_competidores)} r="3" fill="var(--bar)" stroke="var(--surface)" strokeWidth="2" />
                  )}
                  {pt.score != null && (
                    <circle
                      className="marca"
                      cx={x(i)}
                      cy={y(pt.score)}
                      r={activo === i ? 6 : 4.5}
                      fill={hueco ? "var(--surface)" : "var(--accent)"}
                      stroke={hueco ? "var(--accent)" : "var(--surface)"}
                      strokeWidth="2"
                    />
                  )}
                  <text x={x(i)} y={H - 12} textAnchor="middle" className="fill-[var(--faint)] text-[11px]">
                    {fmtDay(pt.fecha)}
                  </text>
                </g>
              );
            })}

            {/* Etiqueta directa solo del último valor. */}
            {puntos[ultimo]?.score != null && (
              <text x={x(ultimo) + 10} y={y(puntos[ultimo].score!)} dy="0.32em" className="fill-[var(--text)] text-[12px] font-semibold">
                {fmtNum(puntos[ultimo].score)}
              </text>
            )}
          </svg>

          {p && activo != null && (
            <div
              id={tooltipId}
              role="tooltip"
              className="pointer-events-none absolute top-2 z-10 w-60 -translate-x-1/2 rounded-control border border-line bg-surface px-3 py-2 text-meta shadow-panel"
              style={{ left: `${(x(activo) / W) * 100}%` }}
            >
              <p className="font-semibold">{fmtDay(p.fecha)}</p>
              <p className="num mt-1">
                Score {fmtNum(p.score)}
                {p.intervalo && (
                  <span className="text-muted"> · IC {fmtNum(p.intervalo.inf)}–{fmtNum(p.intervalo.sup)}</span>
                )}
              </p>
              <p className="num text-muted">Media de competidores {fmtNum(p.score_medio_competidores)}</p>
              {activo > 0 && !p.comparable_con_anterior && (
                <p className="mt-1 text-pill-warn-ink">No comparable: {p.motivos_no_comparable.join("; ")}</p>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
