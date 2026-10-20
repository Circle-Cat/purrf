import { test, expect } from "../../fixtures.js";
import {
  cellIn,
  idOf,
  listedIds,
  needSeed,
  openParticipants,
  participantRows,
  rowFor,
  searchWith,
} from "./helpers.js";

// Read-only: the Participants card's lists, filters and sorting, each
// searched within the seeded people (by their @e2e.purrf.test addresses).
//   Mentee H2      Needs exemption (quit after being matched, previous round).
//                  Mentee H1 is seeded the same way, but 04 grants H1 the
//                  exemption, so H2 is the one still listed after it.
//   Mentor H-M1    Not registered: admitted as a mentor, only in the
//                  previous round
//   Mentor B1, Mentee B1  the plain registered mentor and mentee
//   Mentor E1      the only internal seeded person
//   Mentee X1      deactivated account, onboarding training not done
//   Mentee W1      withdrawn; Mentor W-M1 un_matched

const SEEDED = "@e2e.purrf.test";

/** The Participants list of the seeded people in the round, unfiltered. */
async function openSeeded(page) {
  await openParticipants(page, { round: page.seed.roundId, q: SEEDED });
}

test.describe("participant lists and filters", { tag: "@mentorship" }, () => {
  test("Needs exemption lists a person who quit after being matched, with the reason", async ({
    as,
  }) => {
    const page = await as("admin");
    needSeed(page);
    await openSeeded(page);
    await searchWith(page, { List: "Needs exemption" });
    await expect(page).toHaveURL(/needsExemption=1/);

    await expect(
      page.getByRole("cell", { name: "Why", exact: true }),
    ).toBeVisible();
    const h2 = rowFor(page, idOf(page, "Mentee H2"));
    await expect(h2).toHaveCount(1);
    await expect(h2).toContainText(
      /Quit after being matched in (?!this round)/,
    );
    await expect(
      h2.getByRole("button", { name: "Request exemption" }),
    ).toBeVisible();
    for (const name of ["Mentor B1", "Mentee B1", "Mentor H-M1"]) {
      await expect(rowFor(page, idOf(page, name)), name).toHaveCount(0);
    }
  });

  test("Not registered lists an admitted person with no registration in the round", async ({
    as,
  }) => {
    const page = await as("admin");
    needSeed(page);
    await openSeeded(page);
    await searchWith(page, { List: "Not registered" });
    await expect(page).toHaveURL(/notRegistered=1/);

    await expect(
      page.getByRole("cell", { name: "Admitted as", exact: true }),
    ).toBeVisible();
    const hm1 = rowFor(page, idOf(page, "Mentor H-M1"));
    await expect(hm1).toHaveCount(1);
    await expect(await cellIn(page, hm1, "Admitted as")).toHaveText("mentor");
    await expect(await cellIn(page, hm1, "Int / ext")).toHaveText("External");
    await expect(await cellIn(page, hm1, "Rounds taken part")).toHaveText("1");
    await expect(await cellIn(page, hm1, "Last round")).not.toHaveText("Never");
    // Registered in the round, so not on this list.
    for (const name of ["Mentor B1", "Mentee B1", "Mentee H2"]) {
      await expect(rowFor(page, idOf(page, name)), name).toHaveCount(0);
    }
  });

  test("the role filter keeps one role", async ({ as }) => {
    const page = await as("admin");
    needSeed(page);
    await openSeeded(page);
    await searchWith(page, { Role: "Mentor" });
    await expect(page).toHaveURL(/role=mentor/);
    await expect(rowFor(page, idOf(page, "Mentor B1"))).toHaveCount(1);
    await expect(rowFor(page, idOf(page, "Mentee B1"))).toHaveCount(0);
    for (const row of await participantRows(page).all()) {
      await expect(await cellIn(page, row, "Role")).toHaveText("mentor");
    }

    await searchWith(page, { Role: "Mentee" });
    await expect(rowFor(page, idOf(page, "Mentee B1"))).toHaveCount(1);
    await expect(rowFor(page, idOf(page, "Mentor B1"))).toHaveCount(0);
  });

  test("the internal / external filter", async ({ as }) => {
    const page = await as("admin");
    needSeed(page);
    const e1 = idOf(page, "Mentor E1");
    await openSeeded(page);
    await searchWith(page, { "Internal or external": "Internal" });
    await expect(page).toHaveURL(/internal=internal/);
    expect(await listedIds(page)).toEqual([e1]);
    await expect(rowFor(page, e1)).toContainText("Internal");

    await searchWith(page, { "Internal or external": "External" });
    await expect(rowFor(page, e1)).toHaveCount(0);
    await expect(rowFor(page, idOf(page, "Mentee B1"))).toContainText(
      "External",
    );
  });

  test("the account filter", async ({ as }) => {
    const page = await as("admin");
    needSeed(page);
    const x1 = idOf(page, "Mentee X1");
    await openSeeded(page);
    await searchWith(page, { Account: "Deactivated" });
    await expect(page).toHaveURL(/account=deactivated/);
    expect(await listedIds(page)).toEqual([x1]);
    await expect(rowFor(page, x1)).toContainText("Deactivated");

    await searchWith(page, { Account: "Active" });
    await expect(rowFor(page, x1)).toHaveCount(0);
    await expect(rowFor(page, idOf(page, "Mentee B1"))).toHaveCount(1);
  });

  test("the training filter", async ({ as }) => {
    const page = await as("admin");
    needSeed(page);
    const x1 = idOf(page, "Mentee X1");
    await openSeeded(page);
    await searchWith(page, { "Onboarding status": "Training not done" });
    await expect(page).toHaveURL(/training=incomplete/);
    expect(await listedIds(page)).toEqual([x1]);
    await expect(await cellIn(page, rowFor(page, x1), "Training")).toHaveText(
      "Not done",
    );

    await searchWith(page, { "Onboarding status": "Training done" });
    await expect(rowFor(page, x1)).toHaveCount(0);
    await expect(
      await cellIn(page, rowFor(page, idOf(page, "Mentee B1")), "Training"),
    ).toHaveText("Done");
  });

  test("the approval filter", async ({ as }) => {
    const page = await as("admin");
    needSeed(page);
    await openSeeded(page);
    await searchWith(page, { "Approval status": "Withdrawn" });
    await expect(page).toHaveURL(/approval=withdrawn/);
    await expect(rowFor(page, idOf(page, "Mentee W1"))).toContainText(
      "withdrawn",
    );
    await expect(rowFor(page, idOf(page, "Mentee B1"))).toHaveCount(0);

    await searchWith(page, { "Approval status": "Un-Matched" });
    await expect(rowFor(page, idOf(page, "Mentor W-M1"))).toContainText(
      "un_matched",
    );
    await expect(rowFor(page, idOf(page, "Mentee W1"))).toHaveCount(0);
  });

  // PUR-814: the Name header no longer sorts (it sorted by user id, under a
  // column that reads as names). A saved link that carries the old sort still
  // applies it, since the URL param is still read.
  test("the Name header does not sort; a saved link's user id sort still applies", async ({
    as,
  }) => {
    const page = await as("admin");
    needSeed(page);
    await openSeeded(page);
    const name = page.getByRole("cell", { name: "Name", exact: true });
    const before = await listedIds(page);
    expect(before.length).toBeGreaterThan(1);

    let fetched = 0;
    page.on("request", (r) => {
      if (
        r.method() === "GET" &&
        new URL(r.url()).pathname.endsWith("/mentorship/admin/participants")
      )
        fetched += 1;
    });
    await name.click();
    // Nothing to wait for: a click that does nothing sends nothing, so give a
    // stray request a moment to show up before counting.
    await page.waitForTimeout(1_500);
    expect(fetched).toBe(0);
    await expect(page).not.toHaveURL(/sort=/);
    await expect(name).not.toHaveAttribute("aria-sort", /.*/);
    expect(await listedIds(page)).toEqual(before);

    await openParticipants(page, {
      round: page.seed.roundId,
      q: SEEDED,
      sort: "user_id",
      order: "asc",
    });
    const asc = await listedIds(page);
    expect(asc).toEqual([...asc].sort((a, b) => a - b));
    expect(asc[0]).toBe(idOf(page, "Mentor A1"));
  });
});
