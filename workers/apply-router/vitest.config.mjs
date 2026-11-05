import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    environment: "node",
    setupFiles: ["./vitest.setup.js"],
    exclude: ["node_modules", "dist", ".git", "bazel-*"],
  },
});
