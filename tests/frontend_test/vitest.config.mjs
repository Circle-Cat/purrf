import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import path from "path";

export default defineConfig({
  plugins: [
    react({
      jsxRuntime: "automatic",
    }),
  ],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "../../frontend/src"),
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    css: true,
    setupFiles: ["./setupTests.js"],
    exclude: ["node_modules", "dist", ".git", "bazel-*"],
    teardownTimeout: 120000,
    // vitest's default per-test timeout is 5000ms. The tests here run in
    // 350-900ms unloaded, so that default leaves under an order of magnitude
    // of headroom, and a CPU spike is enough to cross it -- which file trips
    // is arbitrary, so this surfaced as "three flaky files" when it is really
    // the whole suite having no margin. A timeout exists to catch a hung
    // test, not to enforce a performance budget; a hung test still fails
    // here, fifteen seconds later.
    testTimeout: 15000,
    // Bazel already runs the ten shards in parallel, and each shard used to
    // size its own worker pool to the whole machine (vitest defaults to
    // roughly the core count). On 24 cores that meant ten shards asking for
    // ~23 workers each -- about a tenfold oversubscription. The starvation
    // was enough to push tests that normally take 350-900ms past vitest's
    // 5000ms per-test timeout, which is what the "flaky" frontend tests
    // actually were. Two workers per shard keeps the total near the core
    // count.
    poolOptions: {
      threads: { minThreads: 1, maxThreads: 2 },
      forks: { minForks: 1, maxForks: 2 },
    },
  },
});
