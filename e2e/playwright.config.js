import { defineConfig } from "@playwright/test";
import { ENV } from "./lib/env.js";

export default defineConfig({
  testDir: "tests",
  globalSetup: "./global-setup.js",
  globalTeardown: "./global-teardown.js",
  // Write tests share one set of seeded people, so nothing runs in parallel.
  workers: 1,
  fullyParallel: false,
  retries: 0,
  timeout: 60_000,
  // Staging only ever gets the read-only pass.
  grep: ENV.writesAllowed ? undefined : /@smoke/,
  reporter: [["list"], ["html", { open: "never" }]],
  use: {
    baseURL: ENV.web,
    viewport: { width: 1440, height: 900 },
    screenshot: "only-on-failure",
    trace: "retain-on-failure",
  },
});
