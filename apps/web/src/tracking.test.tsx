import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { API_URL } from "./api/client";
import { App } from "./App";
import * as auth from "./mocks/auth";
import { ESTIMACION_KIT } from "./mocks/data";
import * as db from "./mocks/db";
import { config } from "./mocks/db";
import { server } from "./mocks/server";
import { iniciarSesion, nb, testClient } from "./test/utils";

const MARCA = "clinica-alborada-vision";

/** Estudio completado del usuario, con fecha posterior al anterior. */
async function completado(owner: string): Promise<string> {
  const id = db.crear("kit", owner);
  db.completar(id);
  await new Promise((r) => setTimeout(r, 5));
  return id;
}

describe("seguimiento por marca", () => {
  it("lista las marcas y, sin cambios significativos, lo dice así", async () => {
    const { user: cuenta } = iniciarSesion();
    await completado(cuenta.id);
    await completado(cuenta.id);
    const user = userEvent.setup();
    render(<App initialPath="/marcas" client={testClient()} requireLogin />);

    const tarjeta = await screen.findByTestId("marca-seguimiento");
    expect(tarjeta).toHaveTextContent("Clínica Alborada Visión");
    expect(tarjeta).toHaveTextContent("2 mediciones");
    await user.click(tarjeta);

    await screen.findByRole("heading", { level: 1, name: "Clínica Alborada Visión" });
    expect(screen.getByTestId("sin-cambios")).toHaveTextContent("Sin cambios fuera del margen de error");
    expect(screen.getByTestId("resumen-serie")).toHaveTextContent("Sin cambios fuera del margen de error");
    expect(screen.queryAllByTestId("cambio-significativo")).toHaveLength(0);
    // Pinta las cifras de SerieMarca tal cual: score, intervalo y puesto.
    const filas = within(screen.getByTestId("tabla-mediciones")).getAllByRole("row").slice(1);
    expect(filas).toHaveLength(2);
    expect(nb(filas[0].textContent)).toContain("25,93");
    expect(nb(filas[0].textContent)).toContain("22,53 – 29,33");
    expect(nb(filas[0].textContent)).toContain("8.ª de 10");
    expect(within(filas[0]).getByText("Línea base")).toBeInTheDocument();
    expect(screen.getAllByTestId("punto")).toHaveLength(2);
    expect(within(screen.getByTestId("tabla-indicadores")).getByRole("rowheader", { name: "Aparición espontánea" })).toBeInTheDocument();
  });

  it("solo enseña los cambios significativos y marca los puntos no comparables con su motivo", async () => {
    const { user: cuenta } = iniciarSesion(auth.DEMO.email);
    await completado(cuenta.id);
    render(<App initialPath={`/marcas/${MARCA}`} client={testClient()} requireLogin />);

    await screen.findByRole("heading", { level: 1, name: "Clínica Alborada Visión" });
    const cambios = screen.getAllByTestId("cambio-significativo");
    expect(cambios.length).toBeGreaterThan(0);
    expect(cambios[0]).toHaveTextContent("El Score de Citación sube 6,73 puntos (de 19,20 a 25,93), fuera del margen de error.");
    // Del T1 al T2 cambió el modelo de ChatGPT: no hay cambio entre ellos y el punto va marcado.
    expect(screen.getAllByTestId("punto-no-comparable")).toHaveLength(1);
    expect(screen.getByTestId("motivo-no-comparable")).toHaveTextContent("Cambió el modelo de ChatGPT (gpt-4o → gpt-4.1)");
    expect(screen.getByText("Cambio de método")).toBeInTheDocument();
    expect(screen.getByTestId("resumen-serie")).toHaveTextContent("sube 6,73 puntos");
  });

  it("una marca ajena o inexistente da 404", async () => {
    const otra = iniciarSesion("otra@clinica.es");
    await completado(otra.user.id);
    iniciarSesion("ana@clinica.es");
    render(<App initialPath={`/marcas/${MARCA}`} client={testClient()} />);
    expect(await screen.findByText("No tienes ninguna marca con ese identificador.")).toBeInTheDocument();
  });
});

describe("volver a medir", () => {
  it("pide la estimación, la enseña y solo al confirmar envía el POST con el coste", async () => {
    const { user: cuenta } = iniciarSesion();
    const id = await completado(cuenta.id);
    const cuerpos: unknown[] = [];
    server.events.on("request:start", async ({ request }) => {
      if (request.method === "POST" && new URL(request.url).pathname.endsWith("/remeasure")) {
        cuerpos.push(await request.clone().json());
      }
    });
    try {
      const user = userEvent.setup();
      render(<App initialPath={`/marcas/${MARCA}`} client={testClient()} requireLogin />);
      await user.click(await screen.findByRole("button", { name: "Volver a medir" }));
      const dialogo = screen.getByRole("dialog", { name: "Volver a medir" });
      expect(nb((await within(dialogo).findByTestId("estimacion")).textContent)).toContain("0,00 €");

      // Cancelar no lanza nada.
      await user.click(within(dialogo).getByRole("button", { name: "Cancelar" }));
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
      expect(cuerpos).toHaveLength(0);

      await user.click(screen.getByRole("button", { name: "Volver a medir" }));
      const otra = screen.getByRole("dialog", { name: "Volver a medir" });
      await user.click(await within(otra).findByRole("button", { name: /Confirmar y medir/ }));
      await screen.findByRole("heading", { level: 1, name: "Diagnóstico" });
      expect(cuerpos).toEqual([{ confirmado: true, coste_estimado_eur: ESTIMACION_KIT.coste_estimado_eur }]);
      expect(db.listar(cuenta.id, MARCA).find((s) => s.id !== id)?.id).toContain(`${id}-remeasure-`);
    } finally {
      server.events.removeAllListeners();
    }
  });

  it("409 por coste cambiado: enseña el coste nuevo y pide confirmar otra vez", async () => {
    const { user: cuenta } = iniciarSesion();
    const id = await completado(cuenta.id);
    let llamadas = 0;
    server.use(
      http.get(`${API_URL}/studies/:id/remeasure/estimate`, () => {
        llamadas += 1;
        return HttpResponse.json({ ...ESTIMACION_KIT, coste_estimado_eur: llamadas === 1 ? 0.44 : 0.9 });
      }),
      // La API compara con su estimación actual (0,90 €) y rechaza los 0,44 € confirmados.
      http.post(`${API_URL}/studies/:id/remeasure`, async ({ request }) => {
        const body = (await request.json()) as { coste_estimado_eur: number };
        return Math.abs(body.coste_estimado_eur - 0.9) > 0.01
          ? HttpResponse.json({ detail: "el coste estimado ha cambiado" }, { status: 409 })
          : HttpResponse.json({ study_id: `${id}-r`, remedicion_de: id }, { status: 201 });
      }),
    );
    const user = userEvent.setup();
    render(<App initialPath={`/studies/${id}/diagnostico`} client={testClient()} requireLogin />);
    await user.click(await screen.findByRole("button", { name: "Volver a medir" }));
    await user.click(await screen.findByRole("button", { name: /Confirmar y medir \(0,44/ }));
    expect(nb((await screen.findByRole("alert")).textContent)).toContain(
      "El coste estimado ha cambiado: era 0,44 € y ahora es 0,90 €",
    );
    expect(screen.getByRole("button", { name: /Confirmar y medir \(0,90/ })).toBeEnabled();
  });

  it("409 si ya hay una re-medición en curso", async () => {
    const { user: cuenta } = iniciarSesion();
    const id = await completado(cuenta.id);
    config.pasoMs = 60_000;
    try {
      db.remeasure(id);
      const user = userEvent.setup();
      render(<App initialPath={`/studies/${id}/diagnostico`} client={testClient()} requireLogin />);
      await user.click(await screen.findByRole("button", { name: "Volver a medir" }));
      await user.click(await screen.findByRole("button", { name: /Confirmar y medir/ }));
      expect(await screen.findByRole("alert")).toHaveTextContent("Ya hay una re-medición en curso de este estudio");
    } finally {
      config.pasoMs = 0;
    }
  });
});

describe("API sin las rutas de seguimiento (404 «Not Found»)", () => {
  const rutaInexistente = () => HttpResponse.json({ detail: "Not Found" }, { status: 404 });

  it("/marcas explica que el seguimiento aún no está disponible, sin botón de reintentar", async () => {
    iniciarSesion();
    server.use(http.get(`${API_URL}/brands`, rutaInexistente));
    render(<App initialPath="/marcas" client={testClient()} requireLogin />);
    const alerta = await screen.findByRole("alert");
    expect(alerta).toHaveTextContent("Seguimiento no disponible todavía");
    expect(alerta).toHaveTextContent("todavía no ofrece el seguimiento por marca");
    expect(within(alerta).queryByRole("button", { name: "Reintentar" })).not.toBeInTheDocument();
  });

  it("la serie de una marca degrada con un mensaje claro", async () => {
    iniciarSesion();
    server.use(http.get(`${API_URL}/brands/:brandId/serie`, rutaInexistente));
    render(<App initialPath={`/marcas/${MARCA}`} client={testClient()} requireLogin />);
    const alerta = await screen.findByRole("alert");
    expect(alerta).toHaveTextContent("todavía no ofrece la serie de mediciones");
    expect(alerta).not.toHaveTextContent("No tienes ninguna marca");
  });

  it("sin estimación propia de re-medición usa GET /estimate del mismo modo y lo avisa", async () => {
    const { user: cuenta } = iniciarSesion();
    const id = await completado(cuenta.id);
    server.use(http.get(`${API_URL}/studies/:id/remeasure/estimate`, rutaInexistente));
    const user = userEvent.setup();
    render(<App initialPath={`/studies/${id}/diagnostico`} client={testClient()} requireLogin />);
    await user.click(await screen.findByRole("button", { name: "Volver a medir" }));
    const dialogo = screen.getByRole("dialog", { name: "Volver a medir" });
    expect(await within(dialogo).findByTestId("estimacion-aproximada")).toBeInTheDocument();
    expect(nb(within(dialogo).getByTestId("estimacion").textContent)).toContain("0,00 €");
    expect(within(dialogo).getByRole("button", { name: /Confirmar y medir/ })).toBeEnabled();
  });
});
