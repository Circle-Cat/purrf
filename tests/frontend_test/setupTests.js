import "@testing-library/jest-dom/vitest";

// Radix UI primitives (Select, etc.) measure elements via ResizeObserver, which
// jsdom does not implement. Provide a no-op so any component that renders a
// Radix Select can mount in tests without a per-file mock.
globalThis.ResizeObserver = class {
  observe() {}
  unobserve() {}
  disconnect() {}
};

// pdfjs-dist (4.x) calls Promise.withResolvers, which is native in modern
// browsers (the production target) but absent in the pinned Node 18 test
// toolchain. Provide the standard ponyfill so the resume parser can be tested.
if (typeof Promise.withResolvers !== "function") {
  Promise.withResolvers = function withResolvers() {
    let resolve;
    let reject;
    const promise = new Promise((res, rej) => {
      resolve = res;
      reject = rej;
    });
    return { promise, resolve, reject };
  };
}
