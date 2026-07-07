import "@testing-library/jest-dom/vitest";

// Radix UI primitives (Select, etc.) measure elements via ResizeObserver, which
// jsdom does not implement. Provide a no-op so any component that renders a
// Radix Select can mount in tests without a per-file mock.
globalThis.ResizeObserver = class {
  observe() {}
  unobserve() {}
  disconnect() {}
};

// Radix Select/Dropdown open via pointer-capture + scroll the active option
// into view — neither exists in jsdom, so the portal'd listbox never mounts and
// its options are unreachable in tests. These no-ops fix it. Do NOT add a
// PointerEvent shim: defining PointerEvent flips userEvent into pointer-event
// dispatch and regresses other suites.
Element.prototype.hasPointerCapture =
  Element.prototype.hasPointerCapture || (() => false);
Element.prototype.setPointerCapture =
  Element.prototype.setPointerCapture || (() => {});
Element.prototype.releasePointerCapture =
  Element.prototype.releasePointerCapture || (() => {});
Element.prototype.scrollIntoView =
  Element.prototype.scrollIntoView || (() => {});

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

// jsdom doesn't implement Blob object URLs. ResumeUpload's session-only
// résumé preview needs both to exist; the mock returns a distinct string per
// call so tests can assert on it (and spy on revokeObjectURL for real).
if (typeof URL.createObjectURL !== "function") {
  let objectUrlCounter = 0;
  URL.createObjectURL = () => `blob:mock-${(objectUrlCounter += 1)}`;
}
if (typeof URL.revokeObjectURL !== "function") {
  URL.revokeObjectURL = () => {};
}
