import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { API_URL } from "./api/client";
import { App } from "./App";
import { ESTIMACION_REAL, kitMarket } from "./mocks/data";
import * as db from "./mocks/db";
import { config } from "./mocks/db";
import { server } from "./mocks/server";
import { iniciarSesion, nb, testClient } from "./test/utils";

describe("estado error del estudio", () => {
  it("muestra el error, sin espera infinita, y deja reintentar o volver", async () => {
    const id = db.crear("kit", iniciarSesion().user.id);
    db.fallar(id, "El motor ChatGPT no respondió tras 3 reintentos");
    const user = userEvent.setup();
    render(<App initialPath={`/studies/${id}/competidores`} client={testClient()} />);

    const alerta = await screen.findByRole("alert");
    expect(alerta).toHaveTextContent("El estudio se ha detenido por un error");
    expect(within(alerta).getByTestId("errores-estudio")).toHaveTextContent("El motor ChatGPT no respondió");
    expect(within(screen.getByRole("banner")).getByTestId("estado")).toHaveTextContent("Detenido por un error");
    expect(screen.queryByText("Se actualiza sola cada 3 segundos.")).not.toBeInTheDocument();
    expect(screen.getByTestId("paso-detenido")).toBeInTheDocument();
    expect(within(alerta).getByRole("link", { name: "Empezar un estudio nuevo" })).toHaveAttribute("href", "/");
    await user.click(within(alerta).getByRole("button", { name: "Volver a comprobar" }));
    expect(await screen.findByRole("alert")).toBeInTheDocument();
  });

  it("un fallo puntual del sondeo no tapa la pantalla", async () => {
    config.pasoMs = 60_000;
    const id = db.crear("kit", iniciarSesion().user.id);
    try {
      render(<App initialPath={`/studies/${id}/competidores`} client={testClient()} />);
      expect(await screen.findByText("Leyendo el brief")).toBeInTheDocument();
      server.use(http.get(`${API_URL}/studies/:id`, () => HttpResponse.json({ detail: "caído" }, { status: 503 })));
      expect(await screen.findByTestId("sondeo-fallido", {}, { timeout: 6000 })).toBeInTheDocument();
      expect(screen.getByText("Leyendo el brief")).toBeInTheDocument();
      expect(screen.queryByText("No se pudo cargar el estudio")).not.toBeInTheDocument();
    } finally {
      config.pasoMs = 0;
    }
  }, 10000);
});

describe("nuevo estudio y coste", () => {
  it("en real, si la estimación supera el tope, no deja lanzar sin confirmarlo", async () => {
    iniciarSesion();
    server.use(
      http.get(`${API_URL}/estimate`, ({ request }) =>
        HttpResponse.json(
          new URL(request.url).searchParams.get("modo") === "real"
            ? { ...ESTIMACION_REAL, coste_estimado_eur: 7.2 }
            : { ...ESTIMACION_REAL, coste_estimado_eur: 0.44, coste_motores_eur: 0 },
        ),
      ),
    );
    const user = userEvent.setup();
    render(<App initialPath="/" client={testClient()} />);
    await user.click(await screen.findByRole("button", { name: "Usar el brief de ejemplo" }));
    expect(nb((await screen.findByTestId("estimacion")).textContent)).toContain("0,44 €");
    expect(screen.getByRole("button", { name: "Analizar" })).toBeEnabled();

    await user.click(screen.getByRole("radio", { name: "Real" }));
    expect(await screen.findByTestId("excede-tope")).toHaveTextContent("supera el tope de 5,00 €");
    expect(screen.getByRole("button", { name: "Analizar" })).toBeDisabled();
    await user.click(screen.getByRole("checkbox", { name: /supera el tope y quiero lanzarlo/ }));
    expect(screen.getByRole("button", { name: "Analizar" })).toBeEnabled();
  });
});

describe("plan en revisión", () => {
  async function enPlan() {
    const id = db.crear("kit", iniciarSesion().user.id);
    db.estado(id); // brief → competidores
    db.reanudar(id, "competidores", kitMarket);
    return id;
  }

  it("los KPI de fracción se leen como porcentaje", async () => {
    const id = await enPlan();
    render(<App initialPath={`/studies/${id}/plan`} client={testClient()} />);
    const objetivos = await screen.findByRole("table", { name: "Objetivos del plan" });
    const bcn = within(objetivos).getByRole("rowheader", { name: "Visibilidad espontánea en Barcelona" }).parentElement!;
    const celdas = within(bcn).getAllByRole("cell").map((c) => nb(c.textContent));
    expect(celdas[0]).toBe("4 %");
    expect(celdas[1]).toBe("20 %");
  });

  it("las ediciones no se pierden al cambiar de pestaña", async () => {
    const id = await enPlan();
    const user = userEvent.setup();
    render(<App initialPath={`/studies/${id}/plan`} client={testClient()} />);
    await screen.findByRole("heading", { level: 1, name: "Plan de acción" });
    const a4 = screen.getAllByTestId("accion").find((a) => a.textContent!.includes("A4"))!;
    const kpi = within(a4).getByLabelText("KPI");
    await user.clear(kpi);
    await user.type(kpi, "Menciones en medios de salud");
    expect(screen.getByText("1 acción editada")).toBeInTheDocument();

    await user.click(within(screen.getByRole("navigation", { name: "Pantallas del estudio" })).getByRole("link", { name: "Diagnóstico" }));
    await screen.findByRole("heading", { level: 1, name: "Diagnóstico" });
    await user.click(within(screen.getByRole("navigation", { name: "Pantallas del estudio" })).getByRole("link", { name: "Plan" }));
    await screen.findByRole("heading", { level: 1, name: "Plan de acción" });
    expect(screen.getByText("1 acción editada")).toBeInTheDocument();
    const otra = screen.getAllByTestId("accion").find((a) => a.textContent!.includes("A4"))!;
    expect(within(otra).getByLabelText("KPI")).toHaveValue("Menciones en medios de salud");
  });
});
