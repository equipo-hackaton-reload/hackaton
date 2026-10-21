import "@fontsource-variable/bricolage-grotesque";
import "@fontsource-variable/geist";
import "./index.css";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";

async function arrancarMocks() {
  if (import.meta.env.VITE_USE_MOCKS !== "true") return;
  const { worker } = await import("./mocks/browser");
  await worker.start({
    onUnhandledRequest: "bypass",
    serviceWorker: { url: `${import.meta.env.BASE_URL}mockServiceWorker.js` },
    quiet: true,
  });
}

arrancarMocks().then(() => {
  createRoot(document.getElementById("root")!).render(
    <StrictMode>
      <App requireLogin />
    </StrictMode>,
  );
});
