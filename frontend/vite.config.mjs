import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";
import { createRequire } from "module";
import tailwindcss from "@tailwindcss/vite";

const require = createRequire(import.meta.url);

// Core helper:
// Used only during build time to resolve the physical path of a package.
// This ensures all imports point to the same module instance.
function resolvePackage(pkg) {
  try {
    return path.dirname(require.resolve(`${pkg}/package.json`));
  } catch {
    // Fallback to the package name if resolution fails
    return pkg;
  }
}

// https://vite.dev/config/
// Export config as a function so we can detect whether
// the current command is 'build' or 'serve'.
export default defineConfig(({ command }) => {
  // Base alias configuration (required for both dev and prod)
  const aliases = {
    "@": path.resolve(__dirname, "src"),
  };

  // Only enable this patch during production builds
  // (i.e. `bazel build //frontend:dist`).
  //
  // This fixes the runtime error in `vite preview` caused by
  // multiple instances of react / react-router-dom,
  // while keeping the dev server (`bazel run //frontend:dev_server`)
  // fast and unaffected.
  if (command === "build") {
    Object.assign(aliases, {
      react: resolvePackage("react"),
      "react-dom": resolvePackage("react-dom"),
      "react-router-dom": resolvePackage("react-router-dom"),
    });
  }

  return {
    plugins: [
      react({
        jsxRuntime: "automatic",
      }),
      tailwindcss(),
    ],
    server: {
      host: true,
      hmr: true,
      port: 5173,
      proxy: {
        "/api": {
          target: "http://localhost:5001",
          changeOrigin: true,
        },
      },
      allowedHosts: [""],
      watch: {
        usePolling: true,
      },
    },
    resolve: {
      // Use the dynamically generated alias map
      alias: aliases,
    },
    build: {
      sourcemap: true,
      rollupOptions: {
        preserveEntrySignatures: "strict",
      },
    },
  };
});
