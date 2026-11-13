import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
export const LOCAL_FILE = path.join(ROOT, "e2e.local.json");

/**
 * The run's private settings from `e2e.local.json` (copied from
 * `e2e.local.example.json`): tokens by role, the database URL and the
 * declared flags. Empty strings count as not given.
 */
export function readLocal() {
  if (!fs.existsSync(LOCAL_FILE)) return {};
  return JSON.parse(fs.readFileSync(LOCAL_FILE, "utf8"));
}
