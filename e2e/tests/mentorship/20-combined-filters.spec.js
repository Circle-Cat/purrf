import { test, expect } from "../../fixtures.js";
import {
  idOf,
  listedIds,
  needSeed,
  openParticipants,
  participantRows,
  searchWith,
} from "./helpers.js";

// Read-only: several Participants filters at once, within the seeded people
// of the live round. Each filter alone lists more; together they narrow.
//   Mentor E1  the only internal seeded person
//   Mentee X1  the only deactivated one, and the only one with training not
//              done
// Each search returns as soon as the list answers (no settle) and the checks
// retry until the table shows it; settling after each of five searches put
// the test at the 60 s limit.

const SEEDED = "@e2e.purrf.test";
const NO_SETTLE = { settle: false };

test.describe("combined participant filters", { tag: "@mentorship" }, () => {
  test("role with internal / external, then account, training and role together", async ({
    as,
  }) => {
    const page = await as("admin");
    needSeed(page);
    const e1 = idOf(page, "Mentor E1");
    const x1 = idOf(page, "Mentee X1");
    await openParticipants(page, { round: page.seed.roundId, q: SEEDED });

    await searchWith(
      page,
      { Role: "Mentor", "Internal or external": "Internal" },
      NO_SETTLE,
    );
    await expect(page).toHaveURL(/role=mentor/);
    await expect(page).toHaveURL(/internal=internal/);
    await expect(page.getByText(/^1–1 of 1$/)).toBeVisible();
    expect(await listedIds(page)).toEqual([e1]);

    // The same internal filter with the other role leaves nobody.
    await searchWith(page, { Role: "Mentee" }, NO_SETTLE);
    await expect(page).toHaveURL(/role=mentee/);
    await expect(page).toHaveURL(/internal=internal/);
    await expect(participantRows(page)).toHaveCount(0);
    await expect(page.getByText(/^0–0 of 0$/)).toBeVisible();

    await searchWith(
      page,
      {
        "Internal or external": "External",
        Account: "Deactivated",
        "Onboarding status": "Training not done",
      },
      NO_SETTLE,
    );
    await expect(page).toHaveURL(/role=mentee/);
    await expect(page).toHaveURL(/account=deactivated/);
    await expect(page).toHaveURL(/training=incomplete/);
    await expect(page.getByText(/^1–1 of 1$/)).toBeVisible();
    expect(await listedIds(page)).toEqual([x1]);

    // Switching only the role empties it again; clearing the role brings X1 back.
    await searchWith(page, { Role: "Mentor" }, NO_SETTLE);
    await expect(page).toHaveURL(/role=mentor/);
    await expect(participantRows(page)).toHaveCount(0);
    await expect(page.getByText(/^0–0 of 0$/)).toBeVisible();
    await searchWith(page, { Role: "All roles" }, NO_SETTLE);
    await expect(page).not.toHaveURL(/role=/);
    await expect(page.getByText(/^1–1 of 1$/)).toBeVisible();
    expect(await listedIds(page)).toEqual([x1]);
  });
});
