/**
 * Contrato HTTP de cuentas (`/auth/*`) tal como lo consume la web.
 *
 * Lo implementa la zona C; mientras no exista, `src/mocks` lo simula con el mismo contrato.
 */

export interface User {
  id: string;
  email: string;
  nombre: string;
  verificado: boolean;
}

/** `POST /auth/register` */
export interface RegisterRequest {
  email: string;
  password: string;
  nombre?: string;
}

export interface VerificacionEnviada {
  enviado: boolean;
  /** Solo en modo demo (`settings.auth_dev_codes`): el código, porque no se envían correos. */
  codigo_dev?: string;
}

export interface RegisterResponse {
  user: User;
  verificacion: VerificacionEnviada;
}

/** `POST /auth/verify` */
export interface VerifyRequest {
  email: string;
  codigo: string;
}

export interface UserResponse {
  user: User;
}

/** `POST /auth/login` */
export interface LoginRequest {
  email: string;
  password: string;
}

export interface LoginResponse {
  token: string;
  /** Caducidad del token: fecha ISO 8601 (o segundos hasta caducar, si la API lo da como número). */
  expira_en: string | number;
  user: User;
}

/** Contraseña mínima que acepta `POST /auth/register` (si no, 422). */
export const MIN_PASSWORD = 8;
