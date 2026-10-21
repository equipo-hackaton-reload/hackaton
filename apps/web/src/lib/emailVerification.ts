/**
 * Verificación de correo por código de 6 cifras contra `POST /auth/verify`.
 *
 * El código lo genera y guarda la API (como hash, caduca a los 15 min, máximo 5 intentos). La web
 * nunca lo genera: solo enseña `codigo_dev` cuando la API lo devuelve en modo demo.
 */
import { ApiError } from "../api/client";

export const CODIGO_LONGITUD = 6;
export const VIGENCIA_MIN = 15;
export const ESPERA_REENVIO_S = 30;

/** Deja solo cifras y corta a la longitud del código: así pegar «123 456» funciona. */
export function limpiarCodigo(valor: string): string {
  return valor.replace(/\D/g, "").slice(0, CODIGO_LONGITUD);
}

/** Mensaje para el error de `POST /auth/verify`. */
export function mensajeVerificacion(e: unknown): string {
  if (!(e instanceof ApiError)) return "No se pudo conectar con la API. Inténtalo de nuevo.";
  // La API responde 400 `codigo_no_valido` tanto si el código no coincide como si ha caducado.
  if (e.status === 429) return "Demasiados intentos. Pide un código nuevo para seguir.";
  if (e.status === 400 || e.status === 422) {
    return "El código no coincide o ha caducado. Revísalo o pide uno nuevo.";
  }
  if (e.status === 404) return "No hay ninguna cuenta pendiente de verificar con ese correo.";
  return `La API respondió ${e.status}: ${e.message}`;
}
