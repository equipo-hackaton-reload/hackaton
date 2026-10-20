import type { Finding } from "../types/schemas";

// es-ES no agrupa por defecto los miles de 4 cifras («1840» junto a «11.200»); se fuerza para que
// las columnas de cifras se lean igual.
// (`"always"` es ES2023; el lib de TypeScript del proyecto solo admite booleanos.)
const AGRUPAR = { useGrouping: "always" } as unknown as Intl.NumberFormatOptions;
const num = (d: number) =>
  new Intl.NumberFormat("es-ES", { ...AGRUPAR, minimumFractionDigits: d, maximumFractionDigits: d });
const pct = new Intl.NumberFormat("es-ES", { style: "percent", maximumFractionDigits: 0 });
const eur = (d: number) =>
  new Intl.NumberFormat("es-ES", {
    ...AGRUPAR,
    style: "currency",
    currency: "EUR",
    minimumFractionDigits: d,
    maximumFractionDigits: d,
  });

export const DASH = "—";

export function fmtNum(n: number | null | undefined, decimals = 2): string {
  return n == null ? DASH : num(decimals).format(n);
}

/** Tasa 0-1 como porcentaje sin decimales; `null` (sin datos) es un guion, nunca 0 %. */
export function fmtPct(rate: number | null | undefined): string {
  return rate == null ? DASH : pct.format(rate);
}

export function fmtEur(n: number | null | undefined, decimals = 2): string {
  return n == null ? DASH : eur(decimals).format(n);
}

export function fmtInt(n: number | null | undefined): string {
  return n == null ? DASH : num(0).format(n);
}

/** Ordinal femenino abreviado: 8 → «8.ª». */
export function ordinal(n: number): string {
  return `${n}.ª`;
}

/**
 * La cifra de un hallazgo con su unidad, deducida de su origen: las tasas de visibilidad son
 * porcentajes (o puntos porcentuales si son una diferencia), el score va en puntos y la brecha de
 * fuentes cuenta respuestas.
 */
export function fmtCifra(f: Pick<Finding, "cifra" | "origen_cifra">): string {
  const o = f.origen_cifra.toLowerCase();
  const diferencia = o.includes("−") || o.includes(" - ");
  if (o.startsWith("visibilidad")) {
    return diferencia ? `${fmtNum(f.cifra * 100, 1)} pp` : fmtPct(f.cifra);
  }
  if (o.startsWith("score")) return `${fmtNum(f.cifra)} pts`;
  if (o.startsWith("brecha de fuentes")) return `${fmtInt(f.cifra)} resp.`;
  return fmtNum(f.cifra);
}

export function fmtDate(iso: string): string {
  return new Intl.DateTimeFormat("es-ES", { dateStyle: "medium", timeStyle: "short" }).format(
    new Date(iso),
  );
}

export function fmtMs(ms: number): string {
  return ms < 1000 ? `${fmtInt(ms)} ms` : `${fmtNum(ms / 1000, 1)} s`;
}

export function slug(s: string): string {
  return s
    .normalize("NFD")
    .replace(/\p{Diacritic}/gu, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");
}
