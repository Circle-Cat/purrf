import { test, expect, settle } from "../../fixtures.js";
import { flag } from "../../lib/flags.js";

/**
 * Shared steps for the mentorship regression specs. Every locator comes from
 * the English copy in frontend/src/pages/MentorshipManagement and
 * frontend/src/pages/PersonalDashboard.
 */

/** Skip a write test when global setup did not seed the round. */
export function needSeed(page) {
  test.skip(
    !page.seed,
    "not seeded (needs E2E_DATABASE_URL and the admin and member tokens, on test)",
  );
}

/** Skip unless the run declared the flag on in .flags.json / E2E_FLAGS. */
export function needFlagOn(key) {
  test.skip(flag(key) !== true, `${key} is not declared on`);
}

/** Skip unless the run declared the flag off. */
export function needFlagOff(key) {
  test.skip(flag(key) !== false, `${key} is not declared off`);
}

/** A seeded person's user id by last name ("Mentee A1"). */
export function idOf(page, lastName) {
  const id = page.seed?.byName?.[lastName];
  if (!id) throw new Error(`seed has no "${lastName}"`);
  return id;
}

/** Seeded people are named "E2E <last name>". */
export const nameOf = (lastName) => `E2E ${lastName}`;

/** Open one person's detail page in a round and wait for it to load. */
export async function openDetail(page, userId, roundId) {
  const loaded = page.waitForResponse(
    (r) =>
      r.request().method() === "GET" &&
      new URL(r.url()).pathname.endsWith(
        `/rounds/${roundId}/participants/${userId}`,
      ),
    { timeout: 30_000 },
  );
  await page.goto(
    `/mentorship-management/participants/${userId}?round=${roundId}`,
  );
  await loaded;
  await expect(page.getByText("Participation history")).toBeVisible({
    timeout: 20_000,
  });
  await settle(page);
}

/** The section of the detail page about the round being looked at. */
export const roundSection = (page, roundName) =>
  page.getByRole("region", { name: roundName, exact: true });

/** The detail page's Waiting on a decision section. */
export const waitingSection = (page) =>
  page.getByRole("region", { name: "Waiting on a decision" });

/** The detail page's Timeline section. */
export const timeline = (page) =>
  page.locator("section").filter({
    has: page.getByRole("heading", { name: "Timeline", exact: true }),
  });

/** The success toast with this text. */
export const successToast = (page, text) =>
  page.locator('[data-sonner-toast][data-type="success"]').filter({
    hasText: text,
  });

/** Pick a reviewer by user id in an approval request dialog. */
export async function pickReviewer(dialog, reviewerId) {
  const select = dialog.getByLabel("Reviewer", { exact: true });
  await expect(
    select.locator(`option[value="${reviewerId}"]`),
    "the reviewer account is offered as a reviewer",
  ).toBeAttached({ timeout: 15_000 });
  await select.selectOption(String(reviewerId));
}

/** The option labels of a native select. */
export const optionLabels = (select) =>
  select.locator("option").allTextContents();

/** The option values of a native select. */
export const optionValues = (select) =>
  select
    .locator("option")
    .evaluateAll((opts) => opts.map((o) => o.value).filter(Boolean));

/**
 * Raise a request from the detail page's "Change status / flag" dialog. The
 * pair is left as the dialog picks it (the only pair, when one is required).
 */
export async function raiseStatusRequest(
  page,
  { type, reviewerId, reason = "e2e regression" },
) {
  await page.getByRole("button", { name: "Change status / flag" }).click();
  const dialog = page.getByRole("dialog");
  await expect(dialog).toBeVisible();
  const typeSelect = dialog.getByLabel("What are you asking for");
  if (await typeSelect.count()) {
    await typeSelect.selectOption({ label: type });
  } else {
    await expect(dialog.getByText(type, { exact: true })).toBeVisible();
  }
  await pickReviewer(dialog, reviewerId);
  await dialog.getByLabel("Reason (optional)").fill(reason);
  await dialog.getByRole("button", { name: "Send for approval" }).click();
  await expect(successToast(page, "Sent for approval.")).toBeVisible();
  await expect(dialog).toBeHidden();
}

/**
 * Approve or reject the pending request whose row starts with `label`, as
 * its reviewer, from the Waiting on a decision section.
 */
export async function decideOnDetail(page, label, decision, comment) {
  const row = waitingSection(page)
    .getByRole("listitem")
    .filter({ hasText: label });
  await expect(row).toHaveCount(1);
  const verb = decision === "approve" ? "Approve" : "Reject";
  await row.getByRole("button", { name: verb, exact: true }).click();
  const dialog = page.getByRole("dialog");
  await expect(dialog).toBeVisible();
  const confirm = dialog.getByRole("button", { name: verb, exact: true });
  if (decision === "reject") {
    await expect(confirm, "a rejection needs a reason").toBeDisabled();
    await dialog.getByLabel("Reason", { exact: true }).fill(comment);
  }
  await confirm.click();
  await expect(
    successToast(
      page,
      decision === "approve" ? "Request approved." : "Request rejected.",
    ),
  ).toBeVisible();
}

/**
 * Open the Participants list with a committed search (the search lives in
 * the URL) and wait until it has answered.
 */
export async function openParticipants(page, params) {
  const searched = page.waitForResponse(
    (r) =>
      r.request().method() === "GET" &&
      /\/mentorship\/admin\/.*participants/.test(new URL(r.url()).pathname),
    { timeout: 30_000 },
  );
  await page.goto(`/mentorship-management?${new URLSearchParams(params)}`);
  await searched;
  await expect(page.getByText(/^\d+–\d+ of \d+$/)).toBeVisible({
    timeout: 20_000,
  });
  await settle(page);
}

/**
 * The Participants table's rows: the only rows on the page that carry a
 * person's "ID <n>" (the rounds table above has none).
 */
export const participantRows = (page) =>
  page.getByRole("row").filter({ hasText: /ID \d+\b/ });

/** The Participants row of one person, found by the "ID <n>" under the name. */
export const rowFor = (page, userId) =>
  participantRows(page).filter({ hasText: new RegExp(`ID ${userId}\\b`) });
