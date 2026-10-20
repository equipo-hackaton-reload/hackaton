import { describe, expect, it } from "vitest";
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

  it("da unidad a la cifra de un hallazgo según su origen", () => {
    expect(nb(fmtCifra({ cifra: 0.15, origen_cifra: "visibilidad espontánea por motor: Claude" }))).toBe("15 %");
    expect(fmtCifra({ cifra: 0.6125, origen_cifra: "visibilidad asistida − visibilidad espontánea" })).toBe(
      "61,3 pp",
    );
    expect(fmtCifra({ cifra: 40.53, origen_cifra: "score de citación: líder − marca foco" })).toBe("40,53 pts");
    expect(fmtCifra({ cifra: 37, origen_cifra: "brecha de fuentes frente al líder: x" })).toBe("37 resp.");
    expect(fmtCifra({ cifra: 1.011, origen_cifra: "fuerza media de las apariciones" })).toBe("1,01");
  });

  it("genera ids de marca sin tildes", () => {
    expect(slug("Clínica Óptica Núñez")).toBe("clinica-optica-nunez");
  });
});
