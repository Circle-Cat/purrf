// The pinned Node 18.20.4 toolchain used by Bazel's vitest_test does not
// expose the WebCrypto `crypto` global that browsers and the Workers runtime
// provide unflagged. Node's own `node:crypto` module ships the identical
// `webcrypto` implementation, so wire it up under the same global name the
// Worker code (and the test file's token-signing helper) expects.
if (typeof globalThis.crypto === "undefined") {
  const { webcrypto } = await import("node:crypto");
  globalThis.crypto = webcrypto;
}

// The real Cloudflare Workers runtime exposes a `caches.default` Cache API
// (see loadKeys() in src/index.js) so a burst of Pub/Sub pushes reuses one
// JWKS fetch instead of hammering Google for every push. Plain Node -- which
// is what these tests run under, via Bazel's vitest_test -- has no such
// global.
//
// This is a fake, not a faithful reimplementation. It models only the two
// methods loadKeys() actually calls, `match` and `put`, as an in-memory Map
// keyed by request URL. It never expires or evicts entries -- there is no TTL
// enforcement here, unlike the real Cache API's `cache-control` handling --
// and it has none of the real Cache API's other behaviour (headers matching,
// partial responses, multiple named caches, eviction under memory pressure).
// The Worker code under test runs on Node in these tests, not on workerd, so
// nothing that depends on real Cache API semantics is exercised or covered
// by this test suite -- only the "second call reuses the first response"
// property loadKeys() relies on.
//
// The backing store is cleared before every test so cache reuse can be
// asserted deterministically within a single test (see
// "caches the JWKS response..." in index.test.js) instead of depending on
// whatever earlier tests happened to warm it with.
if (typeof globalThis.caches === "undefined") {
  const { beforeEach } = await import("vitest");
  const store = new Map();
  beforeEach(() => store.clear());

  const defaultCache = {
    async match(request) {
      const url = typeof request === "string" ? request : request.url;
      const cached = store.get(url);
      return cached ? cached.clone() : undefined;
    },
    async put(request, response) {
      const url = typeof request === "string" ? request : request.url;
      store.set(url, response.clone());
    },
  };
  globalThis.caches = { default: defaultCache };
}
