import { useState } from "react";

type Tema = "light" | "dark";

const CLAVE = "posiq-theme";
const COLOR_BARRA: Record<Tema, string> = { light: "#f7f4f2", dark: "#130e16" };

function temaActual(): Tema {
  return document.documentElement.dataset.theme === "dark" ? "dark" : "light";
}

/** Cambia entre claro y oscuro; index.html aplica la elección guardada antes del primer pintado. */
export function ThemeToggle({ className = "" }: { className?: string }) {
  const [tema, setTema] = useState<Tema>(temaActual);
  const siguiente: Tema = tema === "dark" ? "light" : "dark";

  function cambiar() {
    document.documentElement.dataset.theme = siguiente;
    document.querySelector<HTMLMetaElement>('meta[name="theme-color"]')?.setAttribute("content", COLOR_BARRA[siguiente]);
    try {
      localStorage.setItem(CLAVE, siguiente);
    } catch {
      // Sin almacenamiento el tema dura lo que la pestaña.
    }
    setTema(siguiente);
  }

  return (
    <button
      type="button"
      onClick={cambiar}
      aria-label={siguiente === "dark" ? "Activar tema oscuro" : "Activar tema claro"}
      title={siguiente === "dark" ? "Tema oscuro" : "Tema claro"}
      className={`grid size-10 flex-none place-items-center rounded-control text-muted transition-colors hover:bg-raised hover:text-ink ${className}`}
    >
      <svg aria-hidden="true" viewBox="0 0 20 20" className="size-[18px]" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
        {tema === "dark" ? (
          <>
            <circle cx="10" cy="10" r="3.4" />
            <path d="M10 2.2v1.6M10 16.2v1.6M2.2 10h1.6M16.2 10h1.6M4.5 4.5l1.1 1.1M14.4 14.4l1.1 1.1M4.5 15.5l1.1-1.1M14.4 5.6l1.1-1.1" />
          </>
        ) : (
          <path d="M16.4 12.3A6.6 6.6 0 0 1 7.7 3.6a6.6 6.6 0 1 0 8.7 8.7Z" />
        )}
      </svg>
    </button>
  );
}
