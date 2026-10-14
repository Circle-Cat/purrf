import { ENV } from "./env.js";

/**
 * Non-GET calls the app makes on its own just to read something. They are
 * let through even where writes are forbidden.
 */
const READ_STYLE_CALLS = [
  { method: "POST", path: "/api/summary" },
  { method: "POST", path: "/api/summary/me" },
];

/** API errors that show up on every run and are not regressions. */
const KNOWN_API_ERRORS = [
  {
    method: "POST",
    path: "/api/summary/me",
    status: 403,
    why: "personal dashboard asks for an activity summary the account may not have",
  },
];

const matches = (rule, method, path) =>
  rule.method === method && rule.path === path;

/**
 * Watch one browser context: abort writes the test is not allowed to make
 * and record every API error that is not on the known list. `problems` is
 * filled in place and checked when the test ends.
 */
export async function guardContext(context, { writesAllowed, problems }) {
  await context.route(`${ENV.api}/**`, (route) => {
    const req = route.request();
    const method = req.method();
    const path = new URL(req.url()).pathname;
    const isRead =
      ["GET", "HEAD", "OPTIONS"].includes(method) ||
      READ_STYLE_CALLS.some((r) => matches(r, method, path));
    if (isRead || writesAllowed) return route.continue();
    problems.push(`blocked write: ${method} ${path}`);
    return route.abort("blockedbyclient");
  });

  context.on("response", (res) => {
    if (!res.url().startsWith(ENV.api) || res.status() < 400) return;
    const method = res.request().method();
    const path = new URL(res.url()).pathname;
    const known = KNOWN_API_ERRORS.some(
      (k) => matches(k, method, path) && k.status === res.status(),
    );
    if (!known) problems.push(`API ${res.status()}: ${method} ${path}`);
  });

  context.on("weberror", (err) => {
    problems.push(`page error: ${err.error().message}`);
  });
}
