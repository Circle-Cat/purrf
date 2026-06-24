import "@testing-library/jest-dom/vitest";

// Radix UI primitives (Select, etc.) measure elements via ResizeObserver, which
// jsdom does not implement. Provide a no-op so any component that renders a
// Radix Select can mount in tests without a per-file mock.
globalThis.ResizeObserver = class {
  observe() {}
  unobserve() {}
  disconnect() {}
};
