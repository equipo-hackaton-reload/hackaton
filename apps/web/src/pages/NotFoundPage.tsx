import { Link } from "react-router-dom";
import { AppShell } from "../components/AppShell";

export function NotFoundPage() {
  return (
    <AppShell>
      <h1 className="text-title">Esta página no existe</h1>
      <p className="mt-2 text-muted">
        Revisa el enlace o{" "}
        <Link to="/" className="font-medium text-ink underline">
          empieza un estudio nuevo
        </Link>
        .
      </p>
    </AppShell>
  );
}
