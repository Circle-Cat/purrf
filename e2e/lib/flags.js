import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "@playwright/test";
import { ENV } from "./env.js";
import { apiAs } from "./api.js";
import { browserCookies } from "./cookies.js";
import { readLocal } from "./local.js";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const FLAGS_FILE = path.join(ROOT, ".flags.json");

/**
 * What the person running the suite says the flags are for the test
 * accounts, from E2E_FLAGS, the `flags` of `e2e.local.json`, or
 * `.flags.json` (all the same JSON). A flag left out is undeclared and its
 * tests are skipped.
 */
export function declaredFlags() {
  if (process.env.E2E_FLAGS)
    return normalize(JSON.parse(process.env.E2E_FLAGS));
  const local = readLocal().flags;
  if (local && Object.keys(local).length > 0) return normalize(local);
  if (fs.existsSync(FLAGS_FILE)) {
    return normalize(JSON.parse(fs.readFileSync(FLAGS_FILE, "utf8")));
  }
  return {};
}

/**
 * Accept plain booleans or LaunchDarkly's own evaluation objects
 * (`{"value": true, "variation": 0, …}`), as copied from the browser.
 */
function normalize(flags) {
  return Object.fromEntries(
    Object.entries(flags).map(([k, v]) => [
      k,
      v && typeof v === "object" && "value" in v ? v.value : v,
    ]),
  );
}

/** true / false as declared, or undefined when the run did not say. */
export const flag = (key) => declaredFlags()[key];

/** The flag values LaunchDarkly hands this account's browser. */
async function browserFlags(token) {
  const browser = await chromium.launch();
  try {
    const context = await browser.newContext();
    await context.addCookies(browserCookies(token));
    const page = await context.newPage();
    // The SDK first evaluates for an anonymous context, then for the user;
    // only the second one counts.
    const forUser = page.waitForResponse(
      (r) => {
        const m = r.url().match(/\/sdk\/evalx\/[^/]+\/contexts\/([^/?]+)/);
        if (!m) return false;
        const ctx = JSON.parse(Buffer.from(m[1], "base64url").toString());
        return ctx.kind === "user";
      },
      { timeout: 30_000 },
    );
    await page.goto(ENV.web);
    const body = await (await forUser).json();
    return Object.fromEntries(
      Object.entries(body).map(([k, v]) => [k, v.value]),
    );
  } finally {
    await browser.close();
  }
}

/**
 * Backend-only flags the browser never sees, checked by how the endpoint
 * they guard answers.
 */
const PROBES = {
  "view-personal-summary": async (token) => {
    const api = await apiAs(token);
    try {
      const res = await api.post("/api/summary/me", { data: {} });
      if (res.status() === 403) return false;
      if (res.status() === 200) return true;
      return undefined;
    } finally {
      await api.dispose();
    }
  },
};

/**
 * Compare the declared flags with what each account actually gets, and
 * throw naming every account and flag that disagrees.
 */
export async function verifyFlags(tokensByRole) {
  const declared = declaredFlags();
  const keys = Object.keys(declared);
  if (keys.length === 0) return;
  const wrong = [];
  for (const [role, token] of Object.entries(tokensByRole)) {
    const seen = await browserFlags(token);
    for (const key of keys) {
      let actual = seen[key];
      if (actual === undefined && PROBES[key])
        actual = await PROBES[key](token);
      if (actual === undefined) {
        wrong.push(`${role}: cannot tell whether ${key} is on`);
      } else if (actual !== declared[key]) {
        wrong.push(
          `${role}: ${key} is ${actual ? "on" : "off"}, declared ${declared[key] ? "on" : "off"}`,
        );
      }
    }
  }
  if (wrong.length > 0) {
    throw new Error(
      `Flags do not match what was declared:\n  ${wrong.join("\n  ")}`,
    );
  }
  console.log(
    `[setup] flags as declared: ${keys.map((k) => `${k}=${declared[k]}`).join(", ")}`,
  );
}
