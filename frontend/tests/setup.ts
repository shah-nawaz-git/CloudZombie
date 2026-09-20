import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterAll, afterEach, beforeAll } from "vitest";
import { setupServer } from "msw/node";
export const server = setupServer();
const nativeFetch = global.fetch;
global.fetch = ((input: RequestInfo | URL, init?: RequestInit) =>
  nativeFetch(
    typeof input === "string" ? new URL(input, "http://localhost") : input,
    init,
  )) as typeof fetch;
beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => {
  server.resetHandlers();
  cleanup();
});
afterAll(() => server.close());
Object.assign(navigator, { clipboard: { writeText: () => Promise.resolve() } });
global.ResizeObserver = class {
  observe() {}
  unobserve() {}
  disconnect() {}
};
Object.defineProperty(HTMLElement.prototype, "clientWidth", { configurable: true, value: 800 });
Object.defineProperty(HTMLElement.prototype, "clientHeight", { configurable: true, value: 300 });
