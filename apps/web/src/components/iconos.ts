/** Trazos (viewBox 20×20) de los iconos de las pantallas de cuentas. */
export const ICONOS = {
  mail: "M3 5.5h14v9H3zM3.5 6l6.5 5 6.5-5",
  lock: "M5.5 9h9v7.5h-9zM7 9V6.8a3 3 0 0 1 6 0V9",
  user: "M10 10a3.2 3.2 0 1 0 0-6.4 3.2 3.2 0 0 0 0 6.4ZM3.8 16.5c.8-2.9 3.2-4.4 6.2-4.4s5.4 1.5 6.2 4.4",
  eye: "M2 10s3-5.5 8-5.5S18 10 18 10s-3 5.5-8 5.5S2 10 2 10ZM10 12.3a2.3 2.3 0 1 0 0-4.6 2.3 2.3 0 0 0 0 4.6Z",
  eyeOff: "M3 3l14 14M8.3 8.4a2.3 2.3 0 0 0 3.3 3.2M6 5.7C3.6 7 2 10 2 10s3 5.5 8 5.5c1.4 0 2.6-.4 3.7-1M10.5 4.5C15.2 4.8 18 10 18 10s-.7 1.3-2 2.7",
  alert: "M10 6.5v4M10 13.5h.01M10 2.5l7.5 13h-15z",
  check: "M4.5 10.5l3.5 3.5 7.5-8",
};

/** Forma mínima de un correo: nombre@dominio.tld. */
export const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;
