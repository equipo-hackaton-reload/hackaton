import type { Brand, Rol } from "../types/schemas";
import { slug } from "./format";

/** Fila editable de la revisión de competidores. */
export interface BrandDraft {
  /** Clave estable de la fila; coincide con `id` en las marcas que vienen de la API. */
  key: string;
  id: string;
  nombre: string;
  rol: Rol;
  aliases: string;
  dominio: string;
  rol_detalle: string;
  nueva: boolean;
}

export function toDrafts(marcas: Brand[]): BrandDraft[] {
  return marcas.map((b) => ({
    key: b.id,
    id: b.id,
    nombre: b.nombre,
    rol: b.rol,
    aliases: b.aliases.join(", "),
    dominio: b.dominio ?? "",
    rol_detalle: b.rol_detalle,
    nueva: false,
  }));
}

export function fromDrafts(drafts: BrandDraft[]): Brand[] {
  return drafts.map((d) => ({
    id: d.nueva ? slug(d.nombre) : d.id,
    nombre: d.nombre.trim(),
    aliases: d.aliases
      .split(",")
      .map((a) => a.trim())
      .filter(Boolean),
    rol: d.rol,
    dominio: d.dominio.trim() || null,
    rol_detalle: d.rol_detalle,
  }));
}

/** Problemas que impiden confirmar el mercado; vacío si se puede confirmar. */
export function validar(drafts: BrandDraft[]): string[] {
  const out: string[] = [];
  if (drafts.some((d) => !d.nombre.trim())) out.push("Hay marcas sin nombre.");
  const ids = fromDrafts(drafts.filter((d) => d.nombre.trim())).map((b) => b.id);
  const repetidos = ids.filter((id, i) => ids.indexOf(id) !== i);
  if (repetidos.length) out.push(`Hay marcas repetidas: ${[...new Set(repetidos)].join(", ")}.`);
  if (!drafts.some((d) => d.rol === "foco")) out.push("Falta al menos una marca foco.");
  if (drafts.filter((d) => d.rol === "lider").length > 1) out.push("Solo puede haber un líder.");
  return out;
}
