import { useState, type KeyboardEvent, type ReactNode, type Ref } from "react";
import { ICONOS } from "./iconos";
import { ThemeToggle } from "./ThemeToggle";
import { Wordmark } from "./Wordmark";

/** Tres pasos, no más: lo que el producto hace cabe de un vistazo (ley de Miller). */
const PASOS = [
  ["Lee tu brief", "y propone el mercado: tu marca, sus competidores y el líder."],
  ["Mide la visibilidad", "en ChatGPT, Gemini, Perplexity y Claude."],
  ["Hace el seguimiento", "cada trimestre, con el mismo método, y solo avisa de cambios fuera del margen de error."],
] as const;

export function Icono({ d, className = "" }: { d: string; className?: string }) {
  return (
    <svg aria-hidden="true" viewBox="0 0 20 20" className={`size-[18px] flex-none ${className}`} fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
      <path d={d} />
    </svg>
  );
}


/** Mensaje de error de un formulario de cuentas, anunciado al lector de pantalla. */
export function AlertaFormulario({ id, children }: { id?: string; children: ReactNode }) {
  return (
    <div id={id} role="alert" className="flex items-start gap-2 rounded-control bg-pill-neg-bg px-3 py-2.5 text-body text-pill-neg-ink">
      <Icono d={ICONOS.alert} className="mt-px" />
      <div>{children}</div>
    </div>
  );
}

interface CampoPasswordProps {
  id: string;
  inputRef?: Ref<HTMLInputElement>;
  value: string;
  onChange: (v: string) => void;
  onBlur: () => void;
  error: string | null;
  autoComplete: "current-password" | "new-password";
  autoFocus?: boolean;
  ayuda?: string;
}

/** Contraseña con «mostrar» y aviso de mayúsculas. */
export function CampoPassword({ id, inputRef, value, onChange, onBlur, error, autoComplete, autoFocus, ayuda }: CampoPasswordProps) {
  const [ver, setVer] = useState(false);
  const [mayusculas, setMayusculas] = useState(false);
  const detectar = (e: KeyboardEvent<HTMLInputElement>) => setMayusculas(e.getModifierState("CapsLock"));
  const describe = [ayuda && `${id}-ayuda`, error && `${id}-error`, mayusculas && `${id}-caps`].filter(Boolean).join(" ");
  return (
    <div>
      <label htmlFor={id} className="label">Contraseña</label>
      <div className={`field-icon ${error ? "is-invalid" : ""}`}>
        <Icono d={ICONOS.lock} className="text-faint" />
        <input
          ref={inputRef}
          id={id}
          type={ver ? "text" : "password"}
          autoComplete={autoComplete}
          autoFocus={autoFocus}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onBlur={onBlur}
          onKeyDown={detectar}
          onKeyUp={detectar}
          aria-invalid={Boolean(error)}
          aria-describedby={describe || undefined}
        />
        <button
          type="button"
          onClick={() => setVer((v) => !v)}
          aria-label={ver ? "Ocultar contraseña" : "Mostrar contraseña"}
          aria-pressed={ver}
          className="-mr-1.5 grid size-9 flex-none place-items-center rounded-control text-muted hover:bg-raised hover:text-ink"
        >
          <Icono d={ver ? ICONOS.eyeOff : ICONOS.eye} />
        </button>
      </div>
      {ayuda && !error && (
        <p id={`${id}-ayuda`} className="mt-1.5 text-meta text-muted">{ayuda}</p>
      )}
      {error && (
        <p id={`${id}-error`} className="field-error">
          <Icono d={ICONOS.alert} /> {error}
        </p>
      )}
      {mayusculas && (
        <p id={`${id}-caps`} role="status" className="mt-1.5 flex items-center gap-1.5 text-meta text-pill-warn-ink">
          <Icono d={ICONOS.alert} /> Tienes activadas las mayúsculas.
        </p>
      )}
    </div>
  );
}

interface CampoEmailProps {
  id: string;
  inputRef?: Ref<HTMLInputElement>;
  value: string;
  onChange: (v: string) => void;
  onBlur: () => void;
  error: string | null;
  valido: boolean;
  autoFocus?: boolean;
}

export function CampoEmail({ id, inputRef, value, onChange, onBlur, error, valido, autoFocus }: CampoEmailProps) {
  return (
    <div>
      <label htmlFor={id} className="label">Correo</label>
      <div className={`field-icon ${error ? "is-invalid" : ""}`}>
        <Icono d={ICONOS.mail} className="text-faint" />
        <input
          ref={inputRef}
          id={id}
          type="email"
          inputMode="email"
          autoComplete="email"
          autoFocus={autoFocus}
          placeholder="nombre@empresa.com"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onBlur={onBlur}
          aria-invalid={Boolean(error)}
          aria-describedby={error ? `${id}-error` : undefined}
        />
        {valido && <Icono d={ICONOS.check} className="text-positive" />}
      </div>
      {error && (
        <p id={`${id}-error`} className="field-error">
          <Icono d={ICONOS.alert} /> {error}
        </p>
      )}
    </div>
  );
}

export function Spinner() {
  return <span aria-hidden="true" className="size-4 animate-spin rounded-full border-2 border-current border-r-transparent" />;
}

/** Pantalla partida de las cuentas: panel de marca a la izquierda y el formulario a la derecha. */
export function AuthLayout({ children }: { children: ReactNode }) {
  return (
    <div className="grid min-h-dvh lg:grid-cols-[minmax(0,1.05fr)_minmax(0,1fr)]">
      {/* Panel de marca: en móvil se reduce a una franja para que el formulario quede a mano. */}
      <aside className="login-hero relative flex flex-col justify-between overflow-hidden px-6 pb-8 pt-6 text-white sm:px-10 lg:px-14 lg:py-12">
        <div aria-hidden="true" className="login-blob left-[-8%] top-[-10%] size-[340px] bg-[#ff9a7a]" />
        <div aria-hidden="true" className="login-blob bottom-[-14%] right-[-10%] size-[420px] bg-[#4a0a20]" />

        <span className="relative text-white [&_span_span]:text-[#ffc9b0]">
          <Wordmark className="text-[26px]" />
        </span>

        <div className="relative mt-8 max-w-[34rem] lg:mt-0">
          <p className="font-display text-[32px] font-bold leading-[1.08] tracking-[-0.03em] sm:text-[42px] lg:text-[52px]">
            ¿Te recomiendan los asistentes de IA?
          </p>
          <p className="mt-4 max-w-[30rem] text-[15px] leading-relaxed text-white/90 sm:text-base">
            posiq. mide cuánto aparece tu marca cuando alguien pregunta a una IA, la compara con tu competencia y
            sigue su evolución con método.
          </p>

          <ol className="mt-8 hidden gap-3 sm:grid">
            {PASOS.map(([titulo, texto], i) => (
              <li key={titulo} className="flex gap-3 rounded-[14px] bg-white/12 px-4 py-3 ring-1 ring-white/20 backdrop-blur-sm">
                <span className="grid size-7 flex-none place-items-center rounded-full bg-white text-[13px] font-semibold text-[#8f1347]">
                  {i + 1}
                </span>
                <p className="text-[14px] leading-snug text-white/90">
                  <strong className="font-semibold text-white">{titulo}</strong> {texto}
                </p>
              </li>
            ))}
          </ol>
        </div>

        <p className="relative mt-8 hidden text-meta text-white/80 lg:block">Hackatón · Zona D</p>
      </aside>

      <main id="contenido" className="relative flex items-center justify-center px-4 py-10 sm:px-8">
        <div className="absolute right-4 top-4 sm:right-6">
          <ThemeToggle />
        </div>
        <div className="w-full max-w-[400px]">{children}</div>
      </main>
    </div>
  );
}
