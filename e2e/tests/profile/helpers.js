import { test, expect, settle } from "../../fixtures.js";
import {
  accountSnapshot,
  readSeedState,
  restoreAccounts,
  rowsOf,
} from "../../lib/seed.js";
import { loginAddress, mailbox } from "../../lib/login.js";

export { callApi, successToast } from "../mentorship/helpers.js";
export { rowsOf, loginAddress };

/**
 * Shared steps for the Profile, Sign in & security and Personal Dashboard
 * specs. Locators come from the English copy in frontend/src/pages/Profile,
 * SignInSecurity and PersonalDashboard.
 */

/** Skip a write test when global setup did not seed the profile people. */
export function needProfileSeed(page) {
  test.skip(
    !page.seed?.profile,
    "not seeded (needs E2E_DATABASE_URL and the admin and member tokens, on test)",
  );
  return page.seed.profile.people;
}

/**
 * Snapshot every test account before each test and put it back after,
 * failing the test when something cannot be put back. Global teardown does
 * the same with the snapshot of the whole run.
 */
export function restoreAccountsAfterEach() {
  let snapshot = null;
  test.beforeEach(() => {
    const ids = readSeedState()?.testAccounts;
    snapshot = ids?.length ? accountSnapshot(ids) : null;
  });
  test.afterEach(() => {
    if (!snapshot) return;
    const left = restoreAccounts(snapshot);
    snapshot = null;
    expect(left, "test accounts are back as the test found them").toEqual([]);
  });
}

/** `<mailbox>+e2e-<role>-<suffix>@…`, an address the guard lets be added. */
export function extraAlias(role, suffix) {
  const [name, domain] = mailbox().split("@");
  return `${name}+e2e-${role}-${suffix}@${domain}`;
}

/** The user row's profile fields and the experience row, from the database. */
export function storedProfile(userId) {
  const [[json]] = rowsOf(`
    SELECT jsonb_build_object(
      'firstName', u.first_name, 'lastName', u.last_name,
      'preferredName', u.preferred_name, 'timezone', u.timezone,
      'timezoneUpdatedAt', u.timezone_updated_at, 'linkedin', u.linkedin_link,
      'education', e.education, 'workHistory', e.work_history)::text
    FROM users u LEFT JOIN experience e USING (user_id)
    WHERE u.user_id = ${Number(userId)}`);
  return JSON.parse(json);
}

/** A user's address rows, oldest first. */
export function storedEmails(userId) {
  return rowsOf(`
    SELECT email_id, email, otp_confirmed, is_primary FROM user_emails
    WHERE user_id = ${Number(userId)} ORDER BY email_id`).map(
    ([id, email, confirmed, primary]) => ({
      emailId: Number(id),
      email,
      confirmed: confirmed === "t",
      primary: primary === "t",
    }),
  );
}

/** Add an address row to a test account straight in the database. */
export function insertEmail(userId, email, { confirmed }) {
  const [[id]] = rowsOf(`
    INSERT INTO user_emails (user_id, email, otp_confirmed, is_primary)
    VALUES (${Number(userId)}, '${email.replace(/'/g, "''")}', ${confirmed}, false)
    RETURNING email_id`);
  return Number(id);
}

/** Open the Profile page and wait for the profile to load. */
export async function openProfile(page) {
  const loaded = page.waitForResponse(
    (r) =>
      r.request().method() === "GET" &&
      new URL(r.url()).pathname === "/api/profiles/me",
    { timeout: 30_000 },
  );
  await page.goto("/profile");
  await loaded;
  await expect(page.getByRole("button", { name: "Edit Profile" })).toBeVisible({
    timeout: 20_000,
  });
  await settle(page);
}

/** The profile header: name, preferred name and the timezone badge. */
export const profileHeader = (page) => page.locator("h1").first();

/** One of the Profile page cards, by its heading. */
export const profileCard = (page, heading) =>
  page
    .locator('[data-slot="card"]')
    .filter({ has: page.getByRole("heading", { level: 3, name: heading }) });

/**
 * An edit modal of the Profile page, by its heading. They are plain overlays,
 * not dialogs, so they are found by the heading inside.
 */
export const editModal = (page, heading) =>
  page
    .locator("div.fixed")
    .filter({ has: page.getByRole("heading", { level: 3, name: heading }) })
    .first();

/** The input or selects under a label in a modal (its labels name no input). */
export const field = (scope, label) =>
  scope.locator(
    `xpath=.//label[starts-with(normalize-space(.), "${label}")]/following-sibling::*[1]`,
  );

/** Pick month and year in a date field ("Start date" / "End date"). */
export async function pickDate(scope, label, [month, year]) {
  const selects = field(scope, label).locator("select");
  await selects.nth(0).selectOption(month);
  await selects.nth(1).selectOption(String(year));
}

/** The entry forms of the education or experience modal, top first. */
export const entryForms = (modal) => modal.locator("div.relative.rounded-xl");

/** A field's inline error under a modal. */
export const fieldErrors = (scope) => scope.locator("span.text-destructive");

/** Pick a timezone in the react-timezone-select control. */
export async function pickTimezone(scope, search, label) {
  const box = scope.getByRole("combobox");
  await box.click();
  await box.fill(search);
  await scope.page().getByRole("option", { name: label }).first().click();
}

/** Record every write the page sends to the API, as "METHOD path". */
export function recordWrites(page) {
  const writes = [];
  page.on("request", (req) => {
    if (["GET", "HEAD", "OPTIONS"].includes(req.method())) return;
    const url = new URL(req.url());
    if (url.pathname.startsWith("/api/"))
      writes.push(`${req.method()} ${url.pathname}`);
  });
  return writes;
}

/** Open Sign in & security and wait for the address list. */
export async function openSignIn(page) {
  const loaded = page.waitForResponse(
    (r) =>
      r.request().method() === "GET" &&
      new URL(r.url()).pathname === "/api/auth/emails",
    { timeout: 30_000 },
  );
  await page.goto("/settings/sign-in");
  await loaded;
  await expect(page.getByText("Emails & sign-in methods")).toBeVisible({
    timeout: 20_000,
  });
  await expect(page.getByText("Loading…")).toBeHidden();
}

/** The row of one address on Sign in & security. */
export const addressRow = (page, address) =>
  page.locator("li").filter({ has: page.getByText(address, { exact: true }) });

/** An error toast with this text. */
export const errorToast = (page, text) =>
  page.locator('[data-sonner-toast][data-type="error"]').filter({
    hasText: text,
  });

/** Console errors of a page, collected as they happen. */
export function consoleErrors(page) {
  const errors = [];
  page.on("console", (msg) => {
    if (msg.type() === "error") errors.push(msg.text());
  });
  return errors;
}

/** Wait until the profile is read with its training section. */
export const trainingRead = (page) =>
  page.waitForResponse(
    (r) =>
      r.request().method() === "GET" &&
      new URL(r.url()).pathname === "/api/profiles/me" &&
      new URL(r.url()).searchParams.get("fields") === "training",
    { timeout: 30_000 },
  );
