import { useState } from "react";
import { DASH, fmtNum, fmtPct } from "../lib/format";
import { FASE_LABEL } from "../lib/study";
import type { Dimension, Metrics, TipoVisibilidad, VisibilityCell } from "../types/schemas";
import { Panel } from "./Panel";

type Dim = Extract<Dimension, "motor" | "fase" | "ciudad">;

const DIMS: { value: Dim; label: string }[] = [
  { value: "motor", label: "Motor" },
  { value: "fase", label: "Fase" },
  { value: "ciudad", label: "Ciudad" },
];

const ORDEN: Record<Dim, string[]> = {
  motor: ["ChatGPT", "Gemini", "Perplexity", "Claude"],
  fase: ["descubrimiento", "comparacion", "validacion", "decision"],
  ciudad: [],
};

function etiqueta(dim: Dim, valor: string) {
  return dim === "fase" ? (FASE_LABEL[valor as keyof typeof FASE_LABEL] ?? valor) : valor;
}

function Tasa({ cell, strong = false }: { cell: VisibilityCell | undefined; strong?: boolean }) {
  if (!cell || cell.tasa == null) {
    return (
      <span className="text-faint" title="Sin datos: ninguna pregunta de este segmento">
        {DASH}
      </span>
    );
  }
  return (
    <span className={strong ? "font-medium" : ""} title={`${cell.apariciones} de ${cell.n} respuestas`}>
      {fmtPct(cell.tasa)}
    </span>
  );
}

interface Props {
  metrics: Metrics;
  ciudades: string[];
  nombreLider: string;
}

/**
 * Visibilidad de la marca por motor, fase o ciudad. Espontáneo (la pregunta no nombra la marca) y
 * asistido (la nombra) van siempre en columnas distintas y nunca se suman.
 */
export function VisibilityTables({ metrics, ciudades, nombreLider }: Props) {
  const [dim, setDim] = useState<Dim>("motor");
  const foco = metrics.marca_foco_id;
  const celda = (brand: string | null, tipo: TipoVisibilidad, valor: string) =>
    metrics.visibilidad.find(
      (c) => c.brand_id === brand && c.tipo === tipo && c.dimension === dim && c.valor === valor,
    );
  const presentes = new Set(
    metrics.visibilidad.filter((c) => c.brand_id === foco && c.dimension === dim).map((c) => c.valor),
  );
  const orden = dim === "ciudad" ? ciudades : ORDEN[dim];
  const valores = [...orden.filter((v) => presentes.has(v)), ...[...presentes].filter((v) => !orden.includes(v))];

  return (
    <Panel
      title="Visibilidad espontánea y asistida"
      id="visibilidad"
      flush
      actions={
        <div role="tablist" aria-label="Segmentar por" className="flex gap-0.5 rounded-control bg-raised p-0.5">
          {DIMS.map((d) => (
            <button
              key={d.value}
              type="button"
              role="tab"
              aria-selected={dim === d.value}
              onClick={() => setDim(d.value)}
              className={`h-7 rounded-[5px] px-2.5 text-meta transition-colors ${
                dim === d.value ? "bg-surface font-medium text-ink" : "text-muted hover:text-ink"
              }`}
            >
              {d.label}
            </button>
          ))}
        </div>
      }
    >
      <div className="overflow-x-auto px-5" role="tabpanel" aria-label={`Por ${dim}`}>
        <table className="w-full min-w-[560px] text-body" data-testid={`visibilidad-${dim}`}>
          <caption className="sr-only">Visibilidad por {dim}: espontánea y asistida por separado</caption>
          <thead>
            <tr className="text-meta text-muted">
              <th scope="col" rowSpan={2} className="pb-2 text-left align-bottom font-normal">
                {DIMS.find((d) => d.value === dim)!.label}
              </th>
              <th scope="colgroup" colSpan={4} className="border-b border-line pb-1.5 text-right font-medium text-ink">
                Espontáneo <span className="font-normal text-muted">· no nombra la marca</span>
              </th>
              <th aria-hidden className="w-6" />
              <th scope="colgroup" colSpan={2} className="border-b border-line pb-1.5 text-right font-medium text-ink">
                Asistido <span className="font-normal text-muted">· la nombra</span>
              </th>
            </tr>
            <tr className="text-meta text-muted">
              <th scope="col" className="pb-2 pt-1.5 text-right font-normal">Marca</th>
              <th scope="col" className="pb-2 pt-1.5 text-right font-normal">
                <span className="block max-w-[11rem] truncate" title={nombreLider}>Líder</span>
              </th>
              <th scope="col" className="pb-2 pt-1.5 text-right font-normal">Brecha</th>
              <th scope="col" className="pb-2 pt-1.5 text-right font-normal">n</th>
              <th aria-hidden />
              <th scope="col" className="pb-2 pt-1.5 text-right font-normal">Marca</th>
              <th scope="col" className="pb-2 pt-1.5 text-right font-normal">n</th>
            </tr>
          </thead>
          <tbody className="num">
            {valores.map((v) => {
              const esp = celda(foco, "espontaneo", v);
              const lid = celda(metrics.lider_id, "espontaneo", v);
              const asi = celda(foco, "asistido", v);
              const brecha = esp?.tasa != null && lid?.tasa != null ? (esp.tasa - lid.tasa) * 100 : null;
              return (
                <tr key={v} className="border-t border-rule">
                  <th scope="row" className="py-2.5 text-left font-normal">
                    {etiqueta(dim, v)}
                  </th>
                  <td className="py-2.5 text-right">
                    <Tasa cell={esp} strong />
                  </td>
                  <td className="py-2.5 text-right text-muted">
                    <Tasa cell={lid} />
                  </td>
                  <td className={`py-2.5 text-right ${brecha != null && brecha < 0 ? "text-negative" : "text-muted"}`}>
                    {brecha == null ? <span className="text-faint">{DASH}</span> : `${brecha > 0 ? "+" : ""}${fmtNum(brecha, 0)} pp`}
                  </td>
                  <td className="py-2.5 text-right text-muted">{esp?.n ?? 0}</td>
                  <td aria-hidden />
                  <td className="py-2.5 text-right">
                    <Tasa cell={asi} strong />
                  </td>
                  <td className="py-2.5 text-right text-muted">{asi?.n ?? 0}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
        <p className="py-3 text-meta text-muted">
          Tasa = respuestas en las que aparece la marca entre las del segmento. Brecha en puntos
          porcentuales frente al líder. Un guion es un segmento sin preguntas, no un 0 %.
        </p>
      </div>
    </Panel>
  );
}
