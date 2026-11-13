import fs from "node:fs";
import path from "node:path";
import readline from "node:readline/promises";
import { fileURLToPath } from "node:url";
import { chromium } from "@playwright/test";
import { ENV } from "./env.js";
import { readLocal } from "./local.js";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
export const LOGIN_CACHE_FILE = path.join(ROOT, ".state", "logins.json");
export const CODES_DIR = path.join(ROOT, ".state", "codes");

/** How long a sign-in waits for its code; the code itself lasts 3 minutes. */
const CODE_WAIT_MS = 5 * 60_000;

/** The test mailbox's address from `e2e.local.json`, or null. */
export function mailbox() {
  return readLocal().mailbox?.address?.trim() || null;
}

/**
 * The address a role signs in with: what `logins` in `e2e.local.json`
 * names, else the mailbox's plus alias `<name>+e2e-<role>@<domain>`. The
 * super admin is never derived: an alias would be a new account without
 * its rights.
 */
export function loginAddress(role) {
  const named = readLocal().logins?.[role]?.trim();
  if (named) return named;
  if (role === "superadmin") return null;
  const box = mailbox();
  if (!box) return null;
  const [name, domain] = box.split("@");
  return `${name}+e2e-${role}@${domain}`;
}

export function readLoginCache() {
  if (!fs.existsSync(LOGIN_CACHE_FILE)) return {};
  return JSON.parse(fs.readFileSync(LOGIN_CACHE_FILE, "utf8"));
}

function writeLoginCache(cache) {
  fs.mkdirSync(path.dirname(LOGIN_CACHE_FILE), { recursive: true });
  fs.writeFileSync(LOGIN_CACHE_FILE, JSON.stringify(cache, null, 2));
}

/**
 * Wait for the person running the suite to hand over a code: typed at the
 * terminal when there is one, else written to `.state/codes/<name>.txt`
 * (how a run started by Claude receives it). `name` is the role for a
 * sign-in code, or e.g. `member-email` for an Add email code.
 */
export async function askForCode(role, address) {
  if (process.stdin.isTTY) {
    const rl = readline.createInterface({
      input: process.stdin,
      output: process.stdout,
    });
    try {
      return (
        await rl.question(`[setup] code sent to ${address} (${role}): `)
      ).trim();
    } finally {
      rl.close();
    }
  }
  const file = path.join(CODES_DIR, `${role}.txt`);
  console.log(`[setup] ${role}: waiting for its code in ${file}`);
  const deadline = Date.now() + CODE_WAIT_MS;
  while (Date.now() < deadline) {
    if (fs.existsSync(file)) {
      const code = fs.readFileSync(file, "utf8").trim();
      fs.rmSync(file);
      if (code) return code;
    }
    await new Promise((r) => setTimeout(r, 1_000));
  }
  throw new Error(
    `${role}: no code in ${file} within ${CODE_WAIT_MS / 60_000} minutes`,
  );
}

/** Open the sign-in page for `address` and have the code sent. */
async function requestCode(browser, address) {
  const page = await (await browser.newContext()).newPage();
  await page.goto(ENV.web);
  await page.locator('input[name="username"]').fill(address);
  await page.getByRole("button", { name: "Continue", exact: true }).click();
  try {
    await page.locator('input[name="code"]').waitFor({ timeout: 60_000 });
  } catch (e) {
    const shot = path.join(ROOT, ".state", `login-${address}.png`);
    await page.screenshot({ path: shot }).catch(() => {});
    throw new Error(
      `${address}: no code page (screenshot ${shot}): ${e.message}`,
    );
  }
  return page;
}

/**
 * Finish signing in with the code and return the Access cookie. Never
 * signs out: signing out ends the Access session the cookie belongs to.
 */
async function enterCode(page, address, code) {
  await page.locator('input[name="code"]').fill(code);
  await page.getByRole("button", { name: "Continue", exact: true }).click();
  await page.waitForURL((u) => u.origin === ENV.web, { timeout: 60_000 });
  const cookie = (await page.context().cookies(ENV.web)).find(
    (c) => c.name === "CF_Authorization",
  );
  if (!cookie) {
    throw new Error(`signed in as ${address} but got no Access cookie`);
  }
  return cookie.value;
}

/**
 * Make sure each role has a working cached cookie. Every role whose cached
 * one is missing or no longer accepted gets its code sent at once, so the
 * person running the suite can read them all from the one inbox and hand
 * them over together. `works(token)` tells whether Access and the API still
 * take a cookie.
 */
export async function refreshLogins(roles, works) {
  const cache = readLoginCache();
  const due = [];
  for (const role of roles) {
    const address = loginAddress(role);
    if (!address) continue;
    const cached = cache[role];
    if (cached?.address === address && (await works(cached.token))) continue;
    due.push({ role, address });
  }
  if (due.length === 0) return;

  fs.mkdirSync(CODES_DIR, { recursive: true });
  for (const { role } of due) {
    fs.rmSync(path.join(CODES_DIR, `${role}.txt`), { force: true });
  }
  const browser = await chromium.launch();
  try {
    const pages = [];
    for (const { role, address } of due) {
      pages.push({ role, address, page: await requestCode(browser, address) });
    }
    console.log(
      `[setup] codes sent to: ${due.map((d) => `${d.role} <${d.address}>`).join(", ")}`,
    );
    for (const { role, address, page } of pages) {
      const code = await askForCode(role, address);
      cache[role] = { address, token: await enterCode(page, address, code) };
      writeLoginCache(cache);
      console.log(`[setup] ${role}: signed in`);
    }
  } finally {
    await browser.close();
  }
}
