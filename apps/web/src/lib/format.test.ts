import { describe, expect, it } from "vitest";
import type { Finding } from "../types/schemas";
import { nb } from "../test/utils";
import { DASH, fmtCifra, fmtEur, fmtInt, fmtNum, fmtPct, slug } from "./format";

describe("format", () => {
  it("formatea cifras en es-ES", () => {
    expect(fmtNum(25.93)).toBe("25,93");
    expect(fmtInt(1840)).toBe("1.840");
    expect(nb(fmtEur(0.4419, 4))).toBe("0,4419 €");
  });

  it("un dato ausente es un guion, nunca 0 %", () => {
    expect(fmtPct(null)).toBe(DASH);
    expect(nb(fmtPct(0))).toBe("0 %");
    expect(nb(fmtPct(0.0417))).toBe("4 %");
  });

  it("da unidad a la cifra de un hallazgo según su `unidad`", () => {
    const c = (cifra: number, unidad: Finding["unidad"], origen_cifra: string) =>
      nb(fmtCifra({ cifra, unidad, origen_cifra }));
    expect(c(0.15, "fraccion", "visibilidad espontánea por motor: Claude")).toBe("15 %");
    expect(c(0.6125, "fraccion", "visibilidad asistida − visibilidad espontánea")).toBe("61,3 pp");
    expect(c(40.53, "puntos", "score de citación: líder − marca foco")).toBe("40,53 pts");
    expect(c(1.011, "puntos", "fuerza media de las apariciones")).toBe("1,01");
    expect(c(37, "recuento", "brecha de fuentes frente al líder: x")).toBe("37 resp.");
    expect(c(24000, "eur", "presupuesto")).toBe("24.000 €");
  });

  it("genera ids de marca sin tildes", () => {
    expect(slug("Clínica Óptica Núñez")).toBe("clinica-optica-nunez");
  });
});
