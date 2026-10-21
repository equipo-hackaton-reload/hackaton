import { screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { renderUI } from "../test/utils";
import { guardarAvisoKit, leerAvisoKit } from "../lib/avisoKit";
import { AvisoKit } from "./AvisoKit";

const AVISO = "Modo kit: datos sintéticos de Alborada; el brief no cambia las mediciones";

describe("AvisoKit", () => {
  afterEach(() => sessionStorage.clear());

  it("enseña el aviso que la API devolvió al crear el estudio en modo kit", () => {
    guardarAvisoKit("S-1", AVISO);
    renderUI(<AvisoKit studyId="S-1" />);
    expect(screen.getByRole("note")).toHaveTextContent(AVISO);
  });

  it("no enseña nada en modo real (aviso null) ni para otro estudio", () => {
    guardarAvisoKit("S-2", null);
    expect(leerAvisoKit("S-2")).toBeNull();
    guardarAvisoKit("S-1", AVISO);
    const { container } = renderUI(<AvisoKit studyId="S-2" />);
    expect(container).toBeEmptyDOMElement();
  });
});
