import { test as base, expect } from "@playwright/test";
import { ENV } from "./lib/env.js";
import { readAccountState, readToken } from "./lib/accounts.js";
import { browserCookies } from "./lib/cookies.js";
import { allowed, guardContext } from "./lib/guard.js";
import { readSeedState } from "./lib/seed.js";

/**
 * `as(role)` opens a page logged in as that test account. Writes are blocked
 * for `@smoke` tests and on environments that forbid them; the test fails if
 * anything was blocked or the API answered with an unexpected error.
 * `page.expectApiError({method, path, status})` names an error the test
 * provokes on purpose; it is accepted for this test only, from any of its
 * pages. `page.expectBlocked(regex)` names a write the guard must abort; the
 * test fails if it was not aborted. `page.allowProfileWrites()` lets the
 * role save its own profile and `page.allowResumeUploads()` lets résumés
 * be uploaded, for this test only.
 */
export const test = base.extend({
  as: async ({ browser }, use, testInfo) => {
    const accounts = readAccountState();
    const writesAllowed =
      ENV.writesAllowed && !testInfo.tags.includes("@smoke");
    const problems = [];
    const expectedErrors = [];
    const expectedBlocks = [];
    const contexts = [];
    const seed = readSeedState();
    for (const id of seed?.people ?? []) allowed.people.add(id);
    for (const round of Object.values(seed?.rounds ?? {})) {
      allowed.seedRounds.add(round.id);
    }
    for (const id of seed?.testAccounts ?? []) allowed.testAccounts.add(id);
    for (const id of seed?.recruiting?.candidates ?? []) allowed.people.add(id);
    for (const job of Object.values(seed?.recruiting?.jobs ?? {})) {
      allowed.jobs.add(job.id);
    }
    for (const a of Object.values(seed?.recruiting?.applications ?? {})) {
      allowed.applications.add(a.applicationId);
    }
    for (const id of seed?.training?.trainees ?? []) allowed.trainees.add(id);
    for (const id of Object.values(seed?.inboxAdmin?.people ?? {})) {
      allowed.opsPeople.add(id);
    }
    for (const id of Object.values(seed?.leave?.people ?? {})) {
      allowed.leavePeople.add(id);
    }
    allowed.profileWriters.clear();
    allowed.resumeUploads = false;

    await use(async (role) => {
      const token = readToken(role);
      testInfo.skip(!token || !accounts[role], `no ${role} token`);
      const context = await browser.newContext();
      await context.addCookies(browserCookies(token));
      await guardContext(context, {
        role,
        writesAllowed,
        problems,
        expectedErrors,
      });
      contexts.push(context);
      const page = await context.newPage();
      page.account = accounts[role];
      // This test restores the account's profile itself, so it may write it.
      page.allowProfileWrites = () => allowed.profileWriters.add(role);
      page.allowResumeUploads = () => {
        allowed.resumeUploads = true;
      };
      page.seed = seed;
      page.expectApiError = (error) => expectedErrors.push(error);
      page.expectBlocked = (pattern) => expectedBlocks.push(pattern);
      return page;
    });

    for (const context of contexts) await context.close();
    for (const pattern of expectedBlocks) {
      const at = problems.findIndex(
        (p) => p.startsWith("blocked ") && pattern.test(p),
      );
      expect(at, `the guard blocked ${pattern}`).toBeGreaterThanOrEqual(0);
      problems.splice(at, 1);
    }
    if (problems.length > 0) {
      await testInfo.attach("problems", { body: problems.join("\n") });
    }
    expect(problems, "blocked writes and unexpected API errors").toEqual([]);
  },
});

export { expect };

/** Wait until the page stops fetching, or give up quietly after a while. */
export async function settle(page) {
  await page
    .waitForLoadState("networkidle", { timeout: 8_000 })
    .catch(() => {});
}

/** Fail if the app is showing an error toast. */
export async function expectNoErrorToast(page) {
  await expect(
    page.locator('[data-sonner-toast][data-type="error"]'),
  ).toHaveCount(0);
}
