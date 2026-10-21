import type { Finding, Objective, UnidadCifra } from "../types/schemas";

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
 * La cifra de un hallazgo con su `unidad`. Una fracción es un porcentaje, o puntos porcentuales si
 * el origen es una diferencia; los puntos del score llevan «pts» y los de una escala van solos; un
 * recuento de fuentes cuenta respuestas.
 */
export function fmtCifra(f: Pick<Finding, "cifra" | "origen_cifra" | "unidad">): string {
  const o = f.origen_cifra.toLowerCase();
  switch (f.unidad) {
    case "fraccion":
      return o.includes("−") || o.includes(" - ") ? `${fmtNum(f.cifra * 100, 1)} pp` : fmtPct(f.cifra);
    case "puntos":
      return o.startsWith("score") ? `${fmtNum(f.cifra)} pts` : fmtNum(f.cifra);
    case "recuento":
      return o.startsWith("brecha de fuentes") ? `${fmtInt(f.cifra)} resp.` : fmtInt(f.cifra);
    case "eur":
      return fmtEur(f.cifra, 0);
  }
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

const KPI_TASA = /visibilidad|tasa|aparici|cuota|proporci|porcentaje|%/i;

/**
 * Unidad de un objetivo del plan. `Objective` no trae `unidad` en el contrato: si la API la añade
 * se usa; si no, un KPI de tasa con valores entre 0 y 1 es una fracción.
 */
export function unidadObjetivo(o: Objective): UnidadCifra | "porcentaje" | "numero" {
  const declarada = (o as Objective & { unidad?: UnidadCifra }).unidad;
  if (declarada) return declarada;
  const fraccion = Math.abs(o.valor_actual) <= 1 && Math.abs(o.valor_objetivo) <= 1;
  if (KPI_TASA.test(o.kpi)) return fraccion ? "fraccion" : "porcentaje";
  return "numero";
}

/** Valor de un objetivo del plan con su unidad: 0,04 de una tasa es «4 %», no «0,0». */
export function fmtObjetivo(o: Objective, valor: number): string {
  switch (unidadObjetivo(o)) {
    case "fraccion":
      return fmtPct(valor);
    case "porcentaje":
      return `${fmtNum(valor, 0)} %`;
    case "eur":
      return fmtEur(valor, 0);
    case "recuento":
      return fmtInt(valor);
    default:
      return fmtNum(valor, 1);
  }
}

/** Valor de un indicador con la misma convención de unidades que los hallazgos. */
export function fmtUnidad(valor: number | null | undefined, unidad: string): string {
  if (valor == null) return DASH;
  switch (unidad) {
    case "fraccion":
      return fmtPct(valor);
    case "recuento":
      return fmtInt(valor);
    case "eur":
      return fmtEur(valor, 0);
    case "puntos":
      return fmtNum(valor);
    default:
      return fmtNum(valor);
  }
}

/** Cifra con signo: «+4,53», «−1,20», «0,00». */
export function fmtSigned(n: number | null | undefined, decimals = 2): string {
  if (n == null) return DASH;
  const t = fmtNum(Math.abs(n), decimals);
  return n > 0 ? `+${t}` : n < 0 ? `−${t}` : t;
}

/** Fecha corta para ejes y tablas: «21 oct 2026». */
export function fmtDay(iso: string): string {
  return new Intl.DateTimeFormat("es-ES", { day: "numeric", month: "short", year: "numeric" }).format(new Date(iso));
}
