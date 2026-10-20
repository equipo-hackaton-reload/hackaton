import { describe, expect, it } from "vitest";
import { kitMarket } from "../mocks/data";
import { fromDrafts, toDrafts, validar } from "./brands";

describe("revisión de competidores", () => {
  it("ida y vuelta sin cambios conserva el mercado", () => {
    expect(fromDrafts(toDrafts(kitMarket.marcas))).toEqual(kitMarket.marcas);
  });

  it("el mercado del kit es válido", () => {
    expect(validar(toDrafts(kitMarket.marcas))).toEqual([]);
  });

  it("detecta nombres vacíos, repetidos, sin foco y dos líderes", () => {
    const d = toDrafts(kitMarket.marcas);
    const nueva = { ...d[0], key: "n", id: "", nueva: true };
    expect(validar([...d, nueva])).toContain("Hay marcas repetidas: instituto-oftalmico-tramuntana.");
    expect(validar([...d, { ...nueva, nombre: " " }])).toContain("Hay marcas sin nombre.");
    expect(validar(d.map((x) => ({ ...x, rol: "contexto" as const })))).toContain("Falta al menos una marca foco.");
    expect(validar(d.map((x, i) => (i < 2 ? { ...x, rol: "lider" as const } : x)))).toContain(
      "Solo puede haber un líder.",
    );
  });

  it("los alias se separan por comas y el dominio vacío es null", () => {
    const [b] = fromDrafts([{ ...toDrafts(kitMarket.marcas)[0], aliases: " A ,B,, ", dominio: " " }]);
    expect(b.aliases).toEqual(["A", "B"]);
    expect(b.dominio).toBeNull();
  });
});
