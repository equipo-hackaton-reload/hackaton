import { useSyncExternalStore } from "react";
import type { User } from "../types/auth";

/**
 * Sesión contra la API de cuentas: el token Bearer que devuelve `POST /auth/login` y el usuario.
 *
 * «Recordarme» la guarda en localStorage; si no, en sessionStorage, que se borra al cerrar la
 * pestaña. La web nunca guarda la contraseña ni genera códigos de verificación: eso es de la API.
 */
export interface Sesion {
  token: string;
  /** Caducidad del token en ms desde epoch. */
  expiraEn: number;
  user: User;
}

const CLAVE = "posiq-session";
const ULTIMO_EMAIL = "posiq-last-email";
const EVENTO = "posiq:session";

function parsear(raw: string | null): Sesion | null {
  if (!raw) return null;
  try {
    const s = JSON.parse(raw) as Partial<Sesion>;
    // Una sesión antigua (solo cliente, sin token) no sirve contra la API.
    if (typeof s.token !== "string" || !s.user || typeof s.expiraEn !== "number") return null;
    return s as Sesion;
  } catch {
    return null;
  }
}

function crudo(): string | null {
  try {
    return localStorage.getItem(CLAVE) ?? sessionStorage.getItem(CLAVE);
  } catch {
    return null;
  }
}

// useSyncExternalStore exige la misma referencia mientras el almacén no cambie.
let cacheRaw: string | null | undefined;
let cacheSesion: Sesion | null = null;

/** Sesión vigente, o null si no hay o el token ha caducado. */
export function getSession(): Sesion | null {
  const raw = crudo();
  if (raw !== cacheRaw) {
    cacheRaw = raw;
    cacheSesion = parsear(raw);
  }
  return cacheSesion && cacheSesion.expiraEn > Date.now() ? cacheSesion : null;
}

/** Token Bearer de la sesión vigente. */
export function getToken(): string | null {
  return getSession()?.token ?? null;
}

function avisar(): void {
  if (typeof window !== "undefined") window.dispatchEvent(new Event(EVENTO));
}

/** `expira_en` de la API: fecha ISO o, si llega como número, segundos hasta caducar. */
export function caducidad(expira: string | number, ahora = Date.now()): number {
  if (typeof expira === "number") return ahora + expira * 1000;
  const t = Date.parse(expira);
  return Number.isNaN(t) ? ahora : t;
}

export function saveSession(sesion: Sesion, recordar: boolean): void {
  try {
    localStorage.removeItem(CLAVE);
    sessionStorage.removeItem(CLAVE);
    (recordar ? localStorage : sessionStorage).setItem(CLAVE, JSON.stringify(sesion));
  } catch {
    // Sin almacenamiento la sesión no persiste; la navegación sigue funcionando.
  }
  rememberEmail(sesion.user.email);
  avisar();
}

export function clearSession(): void {
  try {
    localStorage.removeItem(CLAVE);
    sessionStorage.removeItem(CLAVE);
  } catch {
    // Nada que borrar.
  }
  avisar();
}

function suscribir(fn: () => void): () => void {
  window.addEventListener(EVENTO, fn);
  window.addEventListener("storage", fn);
  return () => {
    window.removeEventListener(EVENTO, fn);
    window.removeEventListener("storage", fn);
  };
}

/** La sesión como estado de React: cambia al entrar, al salir o al recibir un 401. */
export function useSession(): Sesion | null {
  return useSyncExternalStore(suscribir, getSession, getSession);
}

export function rememberEmail(email: string): void {
  try {
    localStorage.setItem(ULTIMO_EMAIL, email);
  } catch {
    // Solo es una comodidad.
  }
}

/** Último correo usado: el formulario lo propone para que se reconozca en vez de recordarlo. */
export function lastEmail(): string {
  try {
    return localStorage.getItem(ULTIMO_EMAIL) ?? "";
  } catch {
    return "";
  }
}

/** Rutas que no piden sesión. */
export const RUTAS_PUBLICAS = ["/login", "/registro", "/verificar"];

export function esPublica(pathname: string): boolean {
  return RUTAS_PUBLICAS.includes(pathname);
}

/** Solo rutas internas: evita que `?next=` mande fuera de la app o de vuelta a las de cuentas. */
export function destinoSeguro(next: string | null): string {
  if (!next || !next.startsWith("/") || next.startsWith("//")) return "/";
  const ruta = next.split(/[?#]/)[0];
  return esPublica(ruta) ? "/" : next;
}

/** `/login?next=…` conservando la ruta en la que se estaba. */
export function rutaLogin(destino: string): string {
  return destino === "/" ? "/login" : `/login?next=${encodeURIComponent(destino)}`;
}
