import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterAll, afterEach, beforeAll } from "vitest";
import { clearSession } from "../lib/session";
import { resetAuth } from "../mocks/auth";
import { config, resetDb } from "../mocks/db";
import { server } from "../mocks/server";

beforeAll(() => {
  config.pasoMs = 0;
  server.listen({ onUnhandledRequest: "error" });
});
afterEach(() => {
  cleanup();
  server.resetHandlers();
  resetDb();
  resetAuth();
  clearSession();
  localStorage.clear();
  sessionStorage.clear();
});
afterAll(() => server.close());
