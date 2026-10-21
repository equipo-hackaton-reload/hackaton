import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { API_URL } from "./api/client";
import { App } from "./App";
import { getSession } from "./lib/session";
import * as auth from "./mocks/auth";
import * as db from "./mocks/db";
import { server } from "./mocks/server";
import { iniciarSesion, testClient } from "./test/utils";

describe("cuentas contra /auth", () => {
  it("pide sesión, entra con token Bearer y vuelve a la ruta pedida", async () => {
    const user = userEvent.setup();
    let autorizacion: string | null = null;
    server.events.on("request:start", ({ request }) => {
      if (new URL(request.url).pathname === "/studies/no-existe") autorizacion = request.headers.get("Authorization");
    });
    try {
      render(<App initialPath="/studies/no-existe/diagnostico" client={testClient()} requireLogin />);
      expect(await screen.findByRole("heading", { name: "Inicia sesión" })).toBeInTheDocument();
      await user.type(screen.getByLabelText("Correo"), "ana");
      await user.tab();
      expect(screen.getByText(/nombre@dominio\.com/)).toBeInTheDocument();
      await user.click(screen.getByRole("button", { name: "Usar la cuenta de demostración" }));
      await user.click(screen.getByRole("button", { name: "Entrar" }));
      expect(await screen.findByText("No existe ningún estudio con ese identificador en tu cuenta.")).toBeInTheDocument();
      expect(autorizacion).toMatch(/^Bearer tok-/);
      // Sin «Recordarme», la sesión va a sessionStorage y se borra al cerrar la pestaña.
      expect(sessionStorage.getItem("posiq-session")).toContain(getSession()!.token);
      expect(localStorage.getItem("posiq-session")).toBeNull();
    } finally {
      server.events.removeAllListeners();
    }
  });

  it("con «Recordarme» la sesión se guarda en localStorage", async () => {
    const user = userEvent.setup();
    render(<App initialPath="/login" client={testClient()} requireLogin />);
    await user.type(screen.getByLabelText("Correo"), auth.DEMO.email);
    await user.type(screen.getByLabelText("Contraseña"), auth.DEMO.password);
    await user.click(screen.getByRole("checkbox", { name: "Recordarme en este navegador" }));
    await user.click(screen.getByRole("button", { name: "Entrar" }));
    await screen.findByRole("heading", { level: 1, name: "Nuevo estudio" });
    expect(localStorage.getItem("posiq-session")).toContain(getSession()!.token);
  });

  it("credenciales malas: mismo mensaje exista o no el correo", async () => {
    const user = userEvent.setup();
    render(<App initialPath="/login" client={testClient()} requireLogin />);
    await user.type(screen.getByLabelText("Correo"), auth.DEMO.email);
    await user.type(screen.getByLabelText("Contraseña"), "otra-clave-mala");
    await user.click(screen.getByRole("button", { name: "Entrar" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Correo o contraseña incorrectos.");
    expect(getSession()).toBeNull();
  });

  it("registro → verificación con el código que da la API → login", async () => {
    const user = userEvent.setup();
    render(<App initialPath="/login" client={testClient()} requireLogin />);
    await user.click(screen.getByRole("link", { name: "Crear una cuenta" }));
    await user.type(await screen.findByLabelText(/Nombre/), "Ana");
    await user.type(screen.getByLabelText("Correo"), "Ana@Clinica.es");
    await user.type(screen.getByLabelText("Contraseña"), "corta");
    await user.click(screen.getByRole("button", { name: "Crear cuenta" }));
    expect(screen.getByText("Usa al menos 8 caracteres.")).toBeInTheDocument();
    await user.clear(screen.getByLabelText("Contraseña"));
    await user.type(screen.getByLabelText("Contraseña"), "una-clave-larga");
    await user.click(screen.getByRole("button", { name: "Crear cuenta" }));

    // La API devuelve codigo_dev (modo demo) y la página lo enseña; el cliente no lo genera.
    await screen.findByRole("heading", { name: "Verifica tu correo" });
    expect(screen.getByText("ana@clinica.es")).toBeInTheDocument();
    const codigo = within(screen.getByTestId("codigo-dev")).getByText(/^\d{6}$/).textContent!;
    const campo = screen.getByLabelText("Código de verificación");
    await user.type(campo, codigo === "000000" ? "111111" : "000000");
    await user.click(screen.getByRole("button", { name: "Verificar" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("El código no coincide");
    await user.clear(campo);
    await user.type(campo, codigo);
    await user.click(screen.getByRole("button", { name: "Verificar" }));
    expect(await screen.findByText("Correo verificado")).toBeInTheDocument();

    // Vuelve al login con el correo puesto; ya puede entrar.
    expect(await screen.findByText("Correo verificado. Ya puedes entrar.", {}, { timeout: 3000 })).toBeInTheDocument();
    expect(screen.getByLabelText("Correo")).toHaveValue("ana@clinica.es");
    await user.type(screen.getByLabelText("Contraseña"), "una-clave-larga");
    await user.click(screen.getByRole("button", { name: "Entrar" }));
    await screen.findByRole("heading", { level: 1, name: "Nuevo estudio" });
    expect(getSession()?.user).toMatchObject({ email: "ana@clinica.es", nombre: "Ana", verificado: true });
  });

  it("un correo sin verificar no entra (403) y lleva a verificarlo", async () => {
    auth.registrar("luis@clinica.es", "una-clave-larga");
    const user = userEvent.setup();
    render(<App initialPath="/login" client={testClient()} requireLogin />);
    await user.type(screen.getByLabelText("Correo"), "luis@clinica.es");
    await user.type(screen.getByLabelText("Contraseña"), "una-clave-larga");
    await user.click(screen.getByRole("button", { name: "Entrar" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Aún no has verificado luis@clinica.es.");
    await user.click(screen.getByRole("link", { name: "Verificar el correo" }));
    await screen.findByRole("heading", { name: "Verifica tu correo" });
    // Sin código a la vista: se pide uno nuevo y la API lo devuelve en modo demo.
    expect(screen.queryByTestId("codigo-dev")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Pedir un código nuevo" }));
    expect(await screen.findByTestId("codigo-dev")).toHaveTextContent(/\d{6}/);
  });

  it("tras 5 intentos la API responde 429 y hay que pedir otro código", async () => {
    const { codigo } = auth.registrar("eva@clinica.es", "una-clave-larga") as { codigo: string };
    const malo = codigo === "000000" ? "111111" : "000000";
    for (let i = 0; i < 4; i++) auth.verificar("eva@clinica.es", malo);
    const user = userEvent.setup();
    render(<App initialPath="/verificar?email=eva%40clinica.es" client={testClient()} />);
    await user.type(screen.getByLabelText("Código de verificación"), malo);
    await user.click(screen.getByRole("button", { name: "Verificar" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Demasiados intentos");
    expect(screen.getByLabelText("Código de verificación")).toBeDisabled();
  });

  it("un 401 a mitad de sesión limpia la sesión y vuelve al login conservando la ruta", async () => {
    const { token, user: cuenta } = iniciarSesion();
    const id = db.crear("kit", cuenta.id);
    auth.caducarToken(token);
    render(<App initialPath={`/studies/${id}/competidores`} client={testClient()} />);
    expect(await screen.findByRole("heading", { name: "Inicia sesión" })).toBeInTheDocument();
    expect(getSession()).toBeNull();
    // Al volver a entrar (el correo ya viene puesto), se vuelve al estudio.
    const user = userEvent.setup();
    expect(screen.getByLabelText("Correo")).toHaveValue(cuenta.email);
    await user.type(screen.getByLabelText("Contraseña"), "contraseña-de-prueba");
    await user.click(screen.getByRole("button", { name: "Entrar" }));
    expect(await screen.findByRole("heading", { level: 1, name: "Competidores" })).toBeInTheDocument();
  });

  it("salir llama a /auth/logout e invalida el token", async () => {
    const { token } = iniciarSesion();
    let logout = 0;
    server.use(
      http.post(`${API_URL}/auth/logout`, ({ request }) => {
        if (request.headers.get("Authorization") === `Bearer ${token}`) logout += 1;
        auth.logout(token);
        return new HttpResponse(null, { status: 204 });
      }),
    );
    const user = userEvent.setup();
    render(<App initialPath="/" client={testClient()} requireLogin />);
    await user.click(screen.getByRole("button", { name: "Cerrar sesión de ana@clinica.es" }));
    expect(await screen.findByRole("heading", { name: "Inicia sesión" })).toBeInTheDocument();
    expect(logout).toBe(1);
    expect(getSession()).toBeNull();
    expect(auth.usuarioPorToken(token)).toBeNull();
  });
});
