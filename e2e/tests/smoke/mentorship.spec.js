import { test, expect, settle, expectNoErrorToast } from "../../fixtures.js";

/**
 * Open the management page and return the round the Participants card
 * should look at: the one in progress, else the newest one with people in it.
 */
async function openManagement(page) {
  const roundsLoaded = page.waitForResponse(
    (r) => r.url().includes("/api/mentorship/rounds?need_details=true"),
    { timeout: 30_000 },
  );
  await page.goto("/mentorship-management");
  const rounds = (await (await roundsLoaded).json()).data;
  await expect(page.getByText("Mentorship Round Management")).toBeVisible();
  return (
    rounds.find((r) => r.isInProgress) ??
    rounds.find((r) => r.matchedParticipants)
  );
}

async function searchParticipants(page, round) {
  await page
    .getByRole("combobox")
    .filter({ hasText: /^Mentorship / })
    .last()
    .click();
  await page.getByRole("option", { name: round.name, exact: true }).click();
  await page.getByRole("button", { name: "Search", exact: true }).click();
  await settle(page);
}

test.describe("mentorship admin pages", { tag: "@smoke" }, () => {
  test("participant detail opens from the Participants list", async ({
    as,
  }) => {
    const page = await as("admin");
    const round = await openManagement(page);
    test.skip(!round, "no round to look at");
    await searchParticipants(page, round);

    // A person with no name gets an empty link, so take the first named one.
    const names = page
      .getByRole("row")
      .filter({ hasText: /ID \d+\b/ })
      .getByRole("link", { name: /\S/ });
    test.skip(
      (await names.count()) === 0,
      `${round.name} has no registered people`,
    );
    await names.first().click();

    await expect(page).toHaveURL(
      /\/mentorship-management\/participants\/\d+\?round=\d+/,
    );
    await expect(page.getByText("Participation history")).toBeVisible({
      timeout: 20_000,
    });
    await expect(page.getByText("Timeline", { exact: true })).toBeVisible();
    await settle(page);
    await expectNoErrorToast(page);
  });

  test("matching results open for a round that has a run", async ({ as }) => {
    const page = await as("admin");
    const round = await openManagement(page);
    test.skip(!round, "no round to look at");
    await searchParticipants(page, round);

    const button = page.getByRole("button", { name: "View matching results" });
    test.skip(await button.isDisabled(), `${round.name} has no matching run`);
    await button.click();

    await expect(page).toHaveURL(/\/mentorship-management\/matching\/\d+/);
    await settle(page);
    await expect(page.locator("main")).not.toBeEmpty();
    await expectNoErrorToast(page);
  });

  test("round feedback opens from the rounds table", async ({ as }) => {
    const page = await as("admin");
    await openManagement(page);

    const link = page.getByRole("link", { name: /^Feedback for / }).first();
    test.skip((await link.count()) === 0, "no round has feedback yet");
    await link.click();

    await expect(page).toHaveURL(
      /\/mentorship-management\/rounds\/\d+\/feedback/,
    );
    await settle(page);
    await expect(page.locator("main")).not.toBeEmpty();
    await expectNoErrorToast(page);
  });
});
