import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { API_URL } from "./api/client";
import { POLL_MS } from "./api/hooks";
import { App } from "./App";
import { clearSession, getSession, saveSession } from "./lib/session";
import * as db from "./mocks/db";
import { config } from "./mocks/db";
import { server } from "./mocks/server";
import { nb, testClient } from "./test/utils";


describe("flujo completo con MSW", () => {
  it("recorre brief → competidores → diagnóstico → plan → propuesta", async () => {
    const user = userEvent.setup();
    render(<App initialPath="/" client={testClient()} />);

    // 1. Nuevo estudio: el modo kit viene por defecto y el real muestra su estimación.
    expect(screen.getByRole("heading", { level: 1, name: "Nuevo estudio" })).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: "Kit" })).toBeChecked();
    expect(screen.getByRole("button", { name: "Analizar" })).toBeDisabled();
    await user.click(screen.getByRole("radio", { name: "Real" }));
    expect(nb((await screen.findByTestId("estimacion")).textContent)).toContain("3,55 €");
    await user.click(screen.getByRole("radio", { name: "Kit" }));
    await user.click(screen.getByRole("button", { name: "Usar el brief de ejemplo" }));
    await user.click(screen.getByRole("button", { name: "Analizar" }));

    // 2. Revisión de competidores: se quita una marca, se añade otra y se confirma.
    await screen.findByRole("heading", { level: 1, name: "Competidores" });
    expect(await screen.findAllByTestId("marca")).toHaveLength(10);
    expect(within(screen.getByRole("banner")).getByTestId("estado")).toHaveTextContent("Esperando revisión de competidores");
    await user.click(screen.getByRole("button", { name: "Quitar Centro Lasik Península" }));
    await user.click(screen.getByRole("button", { name: "Añadir marca" }));
    await user.click(screen.getByRole("button", { name: "Confirmar y medir" }));
    expect(screen.getByRole("alert")).toHaveTextContent("Hay marcas sin nombre.");
    const nuevas = screen.getAllByLabelText("Nombre de la marca");
    await user.type(nuevas[nuevas.length - 1], "Clínica Visión Norte");
    await user.click(screen.getByRole("button", { name: "Confirmar y medir" }));

    // 3. Diagnóstico con las cifras del kit y el aviso de datos sintéticos.
    await screen.findByRole("heading", { level: 1, name: "Diagnóstico" });
    expect(await screen.findByTestId("score-global")).toHaveTextContent("25,93");
    expect(screen.getByText(/8\.ª de 9 marcas, a 40,53 puntos de Grupo Hospitalario Valdecruz/)).toBeInTheDocument();
    expect(screen.getByRole("note")).toHaveTextContent("Datos sintéticos del kit");
    expect(screen.getAllByTestId("hallazgo")).toHaveLength(7);
    expect(screen.queryByText("Centro Lasik Península")).not.toBeInTheDocument();
    await user.click(screen.getByRole("link", { name: "Revisar el plan" }));

    // 4. Revisión del plan: aviso de restricciones, edición y aprobación.
    await screen.findByRole("heading", { level: 1, name: "Plan de acción" });
    expect(screen.getByTestId("violaciones")).toHaveTextContent(
      "acción A4 ignora la restricción «Sin comparativas denigratorias»",
    );
    const a4 = screen.getAllByTestId("accion").find((a) => a.textContent!.includes("A4"))!;
    await user.click(within(a4).getByRole("checkbox", { name: "Sin comparativas denigratorias" }));
    const kpi = within(a4).getByLabelText("KPI");
    await user.clear(kpi);
    await user.type(kpi, "Menciones en medios de salud");
    expect(screen.getByText("1 acción editada")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Aprobar plan" }));

    // 5. Propuesta: resumen, limitaciones, descargas y trazas.
    await screen.findByRole("heading", { level: 1, name: "Propuesta" });
    expect(await screen.findByTestId("resumen-ejecutivo")).toHaveTextContent(
      /Score de Citación de 25,93 sobre 100 y ocupa el puesto 8 de 9/,
    );
    expect(screen.getByRole("heading", { name: "Limitaciones" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Descargar Word" })).toBeEnabled();
    expect(screen.getByRole("button", { name: "Descargar PDF" })).toBeEnabled();
    expect(within(screen.getByRole("banner")).getByTestId("estado")).toHaveTextContent("Completado");
    const trazas = await screen.findByTestId("trazas");
    expect(within(trazas).getByRole("rowheader", { name: "judge" })).toBeInTheDocument();
    expect(nb(screen.getByTestId("coste-total").textContent)).toBe("0,4419 €");
  }, 15000);

  it("enseña el error si la API no encuentra el estudio", async () => {
    render(<App initialPath="/studies/no-existe/diagnostico" client={testClient()} />);
    expect(await screen.findByText("No existe ningún estudio con ese identificador.")).toBeInTheDocument();
  });

  it("pide sesión, valida el formulario y vuelve a la ruta pedida", async () => {
    const user = userEvent.setup();
    try {
      render(<App initialPath="/studies/no-existe/diagnostico" client={testClient()} requireLogin />);
      expect(await screen.findByRole("heading", { name: "Inicia sesión" })).toBeInTheDocument();
      expect(screen.getByRole("button", { name: "Entrar" })).toBeDisabled();
      await user.type(screen.getByLabelText("Correo"), "ana");
      await user.tab();
      expect(screen.getByText(/nombre@dominio\.com/)).toBeInTheDocument();
      await user.click(screen.getByRole("button", { name: "Usar la cuenta de demostración" }));
      await user.click(screen.getByRole("button", { name: "Entrar" }));
      expect(await screen.findByText("No existe ningún estudio con ese identificador.")).toBeInTheDocument();
    } finally {
      clearSession();
    }
  });

  it("verifica el correo con el código y quita el aviso", async () => {
    const user = userEvent.setup();
    saveSession({ email: "ana@clinica.es", nombre: "Ana" }, false);
    try {
      render(<App initialPath="/" client={testClient()} requireLogin />);
      await user.click(await screen.findByRole("link", { name: "Verificar ahora" }));
      await user.click(await screen.findByRole("button", { name: "Enviar código" }));
      const demo = await screen.findByText(/Tu código es/);
      const codigo = within(demo).getByText(/^\d{6}$/).textContent!;
      const campo = screen.getByLabelText("Código de verificación");
      await user.type(campo, codigo === "000000" ? "111111" : "000000");
      await user.click(screen.getByRole("button", { name: "Verificar" }));
      expect(await screen.findByRole("alert")).toHaveTextContent("El código no coincide");
      await user.clear(campo);
      await user.type(campo, codigo);
      await user.click(screen.getByRole("button", { name: "Verificar" }));
      expect(await screen.findByText("Correo verificado")).toBeInTheDocument();
      expect(getSession()?.verificado).toBe(true);
      await screen.findByRole("heading", { level: 1, name: "Nuevo estudio" }, { timeout: 3000 });
      expect(screen.queryByRole("link", { name: "Verificar ahora" })).not.toBeInTheDocument();
    } finally {
      clearSession();
    }
  });

  it("sondea cada 3 s mientras el estudio está en curso y para al llegar a una revisión", async () => {
    config.pasoMs = 1000;
    const id = db.crear("kit");
    let llamadas = 0;
    server.events.on("request:start", ({ request }) => {
      if (request.method === "GET" && new URL(request.url).pathname === `/studies/${id}`) llamadas += 1;
    });
    try {
      render(<App initialPath={`/studies/${id}/competidores`} client={testClient()} />);
      expect(await screen.findByText("Leyendo el brief")).toBeInTheDocument();
      expect(within(screen.getByRole("banner")).getByTestId("estado")).toHaveTextContent("En curso");
      // El primer sondeo llega a los 3 s y el estudio ya espera la revisión.
      expect(await screen.findAllByTestId("marca", {}, { timeout: 5000 })).toHaveLength(10);
      const tras = llamadas;
      expect(tras).toBe(2);
      await new Promise((r) => setTimeout(r, POLL_MS + 300));
      expect(llamadas).toBe(tras);
    } finally {
      config.pasoMs = 0;
      server.events.removeAllListeners();
    }
  }, 12000);

  it("avisa si la API rechaza la reanudación", async () => {
    const id = db.crear("kit");
    server.use(
      http.post(`${API_URL}/studies/:id/resume`, () =>
        HttpResponse.json({ detail: "revisión fuera de turno" }, { status: 409 }),
      ),
    );
    const user = userEvent.setup();
    render(<App initialPath={`/studies/${id}/competidores`} client={testClient()} />);
    await user.click(await screen.findByRole("button", { name: "Confirmar y medir" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("La API no aceptó el mercado: revisión fuera de turno");
  });
});
