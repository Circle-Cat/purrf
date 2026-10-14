import { test as base, expect } from "@playwright/test";
import { ENV } from "./lib/env.js";
import { readAccountState, readToken } from "./lib/accounts.js";
import { browserCookies } from "./lib/cookies.js";
import { guardContext } from "./lib/guard.js";

/**
 * `as(role)` opens a page logged in as that test account. Writes are blocked
 * for `@smoke` tests and on environments that forbid them; the test fails if
 * anything was blocked or the API answered with an unexpected error.
 */
export const test = base.extend({
  as: async ({ browser }, use, testInfo) => {
    const accounts = readAccountState();
    const writesAllowed =
      ENV.writesAllowed && !testInfo.tags.includes("@smoke");
    const problems = [];
    const contexts = [];

    await use(async (role) => {
      const token = readToken(role);
      testInfo.skip(!token || !accounts[role], `no ${role} token`);
      const context = await browser.newContext();
      await context.addCookies(browserCookies(token));
      await guardContext(context, { writesAllowed, problems });
      contexts.push(context);
      const page = await context.newPage();
      page.account = accounts[role];
      return page;
    });

    for (const context of contexts) await context.close();
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
