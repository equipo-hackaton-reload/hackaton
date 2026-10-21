/**
 * Cuentas en memoria del mock, fieles al contrato de `/auth/*` (zona C):
 * registro → código de 6 cifras (15 min, 5 intentos) → login con token Bearer (7 días).
 *
 * Es un mock: guarda la contraseña tal cual y devuelve siempre `codigo_dev` (modo demo). La API real
 * guarda hashes (scrypt) y solo devuelve `codigo_dev` si `settings.auth_dev_codes` es True.
 */
import type { User } from "../types/auth";

interface Cuenta extends User {
  password: string;
}

interface Codigo {
  codigo: string;
  caducaEn: number;
  intentos: number;
}

export const VIGENCIA_CODIGO_MS = 15 * 60 * 1000;
export const MAX_INTENTOS = 5;
export const VIGENCIA_TOKEN_MS = 7 * 24 * 60 * 60 * 1000;
export const DEMO = { email: "demo@posiq.app", password: "demo1234", nombre: "Demo" };

const CLAVE = "posiq-mock-auth";
// En el navegador las cuentas del mock sobreviven a recargar la página; en los tests empiezan vacías.
const almacen = typeof sessionStorage !== "undefined" && import.meta.env.MODE !== "test" ? sessionStorage : null;

interface Volcado {
  cuentas: [string, Cuenta][];
  codigos: [string, Codigo][];
  tokens: [string, { userId: string; expira: number }][];
  contador: number;
}

function cargar(): Volcado | null {
  try {
    const raw = almacen?.getItem(CLAVE);
    return raw ? (JSON.parse(raw) as Volcado) : null;
  } catch {
    return null;
  }
}

const previo = cargar();
const cuentas = new Map<string, Cuenta>(previo?.cuentas ?? []);
const codigos = new Map<string, Codigo>(previo?.codigos ?? []);
const tokens = new Map<string, { userId: string; expira: number }>(previo?.tokens ?? []);
let contador = previo?.contador ?? 0;

function guardar(): void {
  try {
    const v: Volcado = { cuentas: [...cuentas], codigos: [...codigos], tokens: [...tokens], contador };
    almacen?.setItem(CLAVE, JSON.stringify(v));
  } catch {
    // Sin almacenamiento el mock sigue en memoria.
  }
}

function publico(c: Cuenta): User {
  return { id: c.id, email: c.email, nombre: c.nombre, verificado: c.verificado };
}

function codigoAleatorio(): string {
  return String(Math.floor(Math.random() * 1_000_000)).padStart(6, "0");
}

function sembrar(): void {
  cuentas.set(DEMO.email, { id: "U-demo", email: DEMO.email, nombre: DEMO.nombre, verificado: true, password: DEMO.password });
}

sembrar();

export function resetAuth(): void {
  cuentas.clear();
  codigos.clear();
  tokens.clear();
  contador = 0;
  sembrar();
  guardar();
}

export function nuevoCodigo(email: string): string {
  const codigo = codigoAleatorio();
  codigos.set(email, { codigo, caducaEn: Date.now() + VIGENCIA_CODIGO_MS, intentos: 0 });
  guardar();
  return codigo;
}

export type ResultadoRegistro = { user: User; codigo: string } | "existe";

export function registrar(email: string, password: string, nombre?: string): ResultadoRegistro {
  const e = email.trim().toLowerCase();
  if (cuentas.has(e)) return "existe";
  contador += 1;
  const cuenta: Cuenta = { id: `U-${contador}`, email: e, nombre: nombre?.trim() || e.split("@")[0], verificado: false, password };
  cuentas.set(e, cuenta);
  return { user: publico(cuenta), codigo: nuevoCodigo(e) };
}

export type ResultadoVerificar = User | "sin_cuenta" | "sin_codigo" | "caducado" | "incorrecto" | "bloqueado";

export function verificar(email: string, codigo: string): ResultadoVerificar {
  const e = email.trim().toLowerCase();
  const cuenta = cuentas.get(e);
  if (!cuenta) return "sin_cuenta";
  if (cuenta.verificado) return publico(cuenta);
  const c = codigos.get(e);
  if (!c) return "sin_codigo";
  if (c.intentos >= MAX_INTENTOS) return "bloqueado";
  if (Date.now() > c.caducaEn) return "caducado";
  if (c.codigo !== codigo) {
    c.intentos += 1;
    guardar();
    return c.intentos >= MAX_INTENTOS ? "bloqueado" : "incorrecto";
  }
  codigos.delete(e);
  cuenta.verificado = true;
  guardar();
  return publico(cuenta);
}

export function existeCuenta(email: string): boolean {
  return cuentas.has(email.trim().toLowerCase());
}

export type ResultadoLogin = { token: string; expira: number; user: User } | "credenciales" | "no_verificado";

export function login(email: string, password: string): ResultadoLogin {
  const cuenta = cuentas.get(email.trim().toLowerCase());
  if (!cuenta || cuenta.password !== password) return "credenciales";
  if (!cuenta.verificado) return "no_verificado";
  return emitirToken(cuenta);
}

function emitirToken(cuenta: Cuenta) {
  const token = `tok-${crypto.randomUUID()}`;
  const expira = Date.now() + VIGENCIA_TOKEN_MS;
  tokens.set(token, { userId: cuenta.id, expira });
  guardar();
  return { token, expira, user: publico(cuenta) };
}

export function logout(token: string): void {
  tokens.delete(token);
  guardar();
}

export function usuarioPorToken(token: string | null): User | null {
  if (!token) return null;
  const t = tokens.get(token);
  if (!t || t.expira < Date.now()) return null;
  const cuenta = [...cuentas.values()].find((c) => c.id === t.userId);
  return cuenta ? publico(cuenta) : null;
}

/** Para los tests: cuenta verificada con sesión ya abierta. */
export function sesionDePrueba(email = "ana@clinica.es"): { token: string; expira: number; user: User } {
  const e = email.toLowerCase();
  let cuenta = cuentas.get(e);
  if (!cuenta) {
    contador += 1;
    cuenta = { id: `U-${contador}`, email: e, nombre: e.split("@")[0], verificado: true, password: "contraseña-de-prueba" };
    cuentas.set(e, cuenta);
  }
  return emitirToken(cuenta);
}

/** Para los tests: caduca un token sin esperar 7 días. */
export function caducarToken(token: string): void {
  const t = tokens.get(token);
  if (t) t.expira = 0;
}
