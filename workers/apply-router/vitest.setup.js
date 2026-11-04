// Node has no `caches.default`. This in-memory stand-in models only the
// match/put calls loadJobs() makes; it never expires entries.
if (typeof globalThis.caches === "undefined") {
  const { beforeEach } = await import("vitest");
  const store = new Map();
  beforeEach(() => store.clear());

  globalThis.caches = {
    default: {
      async match(request) {
        const url = typeof request === "string" ? request : request.url;
        return store.get(url)?.clone();
      },
      async put(request, response) {
        const url = typeof request === "string" ? request : request.url;
        store.set(url, response.clone());
      },
    },
  };
}
