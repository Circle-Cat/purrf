import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import path from "path";

// Dedicated build config for the static GitHub Pages bundle of the Recruiting v2
// prototype. Separate from vite.config.mjs (the full Bazel-built app) so it can:
//   - use prototype.html / src/prototype-main.jsx as the only entry (no Auth0/LD),
//   - emit relative asset URLs (base "./") so the bundle works under the
//     project-pages subpath https://circle-cat.github.io/purrf/ without hardcoding it,
//   - write to its own dist-pages/ dir, leaving the Bazel build graph untouched.
//
// __dirname is provided by Vite's esbuild-based config loader even in .mjs.
export default defineConfig({
  root: __dirname,
  base: "./",
  plugins: [
    react({
      jsxRuntime: "automatic",
    }),
    tailwindcss(),
  ],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "src"),
    },
  },
  build: {
    outDir: path.resolve(__dirname, "dist-pages"),
    emptyOutDir: true,
    rollupOptions: {
      input: path.resolve(__dirname, "prototype.html"),
    },
  },
});
