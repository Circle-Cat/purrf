import { test, expect, settle } from "../../fixtures.js";

export { callApi, successToast } from "../mentorship/helpers.js";

/**
 * Shared steps for the recruiting specs. Locators come from the English copy
 * in frontend/src/pages/Recruiting.
 */

/** Skip a write test when global setup did not seed the postings. */
export function needRecruiting(page) {
  test.skip(
    !page.seed?.recruiting,
    "not seeded (needs E2E_DATABASE_URL and the admin and member tokens, on test)",
  );
  return page.seed.recruiting;
}

/** A seeded posting ({id, title}): "board", "open" or "screened". */
export const seedJob = (page, kind) => {
  const job = needRecruiting(page).jobs[kind];
  if (!job) throw new Error(`seed has no ${kind} posting`);
  return job;
};

/** A seeded application ({applicationId, userId}) by the candidate's last name. */
export const seedApplication = (page, lastName) => {
  const app = needRecruiting(page).applications[lastName];
  if (!app) throw new Error(`seed has no application of ${lastName}`);
  return app;
};

/** Seeded candidates are named "E2E <last name>". */
export const candidateName = (lastName) => `E2E ${lastName}`;

/** A seeded candidate's only (or first) address. */
export const candidateEmail = (n) => `wangyanpei76+e2e-cand-${n}@gmail.com`;

/** Open an application's detail page and wait for its header. */
export async function openApplication(page, applicationId, heading) {
  const loaded = page.waitForResponse(
    (r) =>
      r.request().method() === "GET" &&
      new URL(r.url()).pathname ===
        `/api/recruiting/applications/${applicationId}`,
    { timeout: 30_000 },
  );
  await page.goto(`/recruiting/applications/${applicationId}`);
  await loaded;
  if (heading) {
    await expect(
      page.getByRole("heading", { level: 1, name: heading }),
    ).toBeVisible({ timeout: 20_000 });
  }
  await settle(page);
}

/** Open a posting's page in the Job Postings console. */
export async function openPosting(page, jobId) {
  const loaded = page.waitForResponse(
    (r) =>
      r.request().method() === "GET" &&
      new URL(r.url()).pathname === `/api/recruiting/jobs/${jobId}/activity`,
    { timeout: 30_000 },
  );
  await page.goto(`/recruiting/postings/${jobId}`);
  await loaded;
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible({
    timeout: 20_000,
  });
  await settle(page);
}

/** Open the Applications Board on one posting and wait for its lanes. */
export async function openBoard(page, jobId, extra = {}) {
  const loaded = page.waitForResponse(
    (r) =>
      r.request().method() === "GET" &&
      new URL(r.url()).pathname === `/api/recruiting/jobs/${jobId}/board`,
    { timeout: 30_000 },
  );
  await page.goto(
    `/recruiting/board?${new URLSearchParams({ jobId, ...extra })}`,
  );
  await loaded;
  await expect(page.getByTestId("lane-rejected")).toBeVisible({
    timeout: 20_000,
  });
  await settle(page);
}

/** One lane of the board by stage key ("recruiter_screening", "behavioral:2"…). */
export const lane = (page, key) => page.getByTestId(`lane-${key}`);

/** The board card of one application. */
export const card = (page, applicationId) =>
  page.locator(`[data-application-id="${applicationId}"]`);

/** Pick a person by email in a Radix PeoplePicker select. */
export async function pickPerson(page, label, email) {
  await page.getByRole("combobox", { name: label, exact: true }).click();
  await page
    .getByRole("option", { name: new RegExp(`\\(${escape(email)}\\)$`) })
    .click();
}

/** Pick a person by email in a radio-list PeoplePicker. */
export async function pickPersonRadio(scope, email) {
  await scope
    .getByRole("radio", { name: new RegExp(`\\(${escape(email)}\\)$`) })
    .check();
}

const escape = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

/** Pick a reviewer by user id in an approval request dialog. */
export async function pickReviewer(dialog, reviewerId) {
  const select = dialog.getByLabel("Reviewer", { exact: true });
  await expect(
    select.locator(`option[value="${reviewerId}"]`),
    "the test account is offered as a reviewer",
  ).toBeAttached({ timeout: 15_000 });
  await select.selectOption(String(reviewerId));
}

/** A tab of the application detail page's right column. */
export async function openTab(page, name) {
  await page.getByRole("tab", { name, exact: true }).click();
}

/** The open tab panel. */
export const tabPanel = (page) => page.getByRole("tabpanel");
