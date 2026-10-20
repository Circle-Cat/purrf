import { test, expect } from "../../fixtures.js";
import {
  candidateName,
  card,
  lane,
  openApplication,
  openBoard,
  seedApplication,
  seedJob,
} from "./helpers.js";

// The seeded board posting, read by e2e-admin (its recruiter):
//   Recruiter screening  A1, C1, K1
//   Behavioral 1 / 2     B1, I1 / O1
//   Rejected             R01-R25, newest first, 20 to a page
// Nothing here writes.

const ids = (locator) =>
  locator.evaluateAll((cards) =>
    cards.map((c) => Number(c.getAttribute("data-application-id"))),
  );

/** Search the board and return the hits panel. */
async function search(page, term) {
  const box = page.getByPlaceholder("Search by name or email");
  await box.fill(term);
  const answered = page.waitForResponse(
    (r) => new URL(r.url()).pathname === "/api/recruiting/board/applicants",
    { timeout: 20_000 },
  );
  await page.getByRole("button", { name: "Search", exact: true }).click();
  await answered;
  return page.getByRole("listbox");
}

test.describe("applications board", { tag: "@recruiting" }, () => {
  test("lanes hold the seeded applications and the Rejected lane pages", async ({
    as,
  }) => {
    const page = await as("admin");
    const job = seedJob(page, "board");
    const app = (name) => seedApplication(page, name).applicationId;

    await openBoard(page, job.id);
    await expect(page.getByRole("combobox", { name: "Job" })).toContainText(
      job.title,
    );
    const screening = lane(page, "recruiter_screening").locator(
      "[data-application-id]",
    );
    expect((await ids(screening)).sort()).toEqual(
      ["Candidate A1", "Candidate C1", "Candidate K1"].map(app).sort(),
    );
    await expect(
      card(lane(page, "behavioral:1"), app("Candidate B1")),
    ).toHaveCount(1);
    await expect(
      card(lane(page, "behavioral:1"), app("Candidate I1")),
    ).toHaveCount(1);
    await expect(
      card(lane(page, "behavioral:2"), app("Candidate O1")),
    ).toHaveCount(1);
    await expect(
      card(lane(page, "behavioral:1"), app("Candidate B1")),
      "an interview-stage card names its reviewer",
    ).toContainText(/Reviewer: /);
    // An employment posting has an Offer lane.
    await expect(lane(page, "offer")).toBeVisible();

    const rejected = lane(page, "rejected");
    await expect(rejected.locator("span").first()).toHaveText("25");
    const firstPage = await ids(rejected.locator("[data-application-id]"));
    expect(firstPage).toHaveLength(20);
    expect(firstPage[0], "newest rejection first").toBe(app("Candidate R01"));
    await rejected.getByRole("button", { name: "Load more" }).click();
    await expect(rejected.locator("[data-application-id]")).toHaveCount(25);
    await expect(
      rejected.getByRole("button", { name: "Load more" }),
    ).toHaveCount(0);
    expect(
      new Set(await ids(rejected.locator("[data-application-id]"))).size,
    ).toBe(25);
  });

  test("search finds an applicant by name and by a second address, and opens them", async ({
    as,
  }) => {
    const page = await as("admin");
    const job = seedJob(page, "board");
    const b1 = seedApplication(page, "Candidate B1");
    await openBoard(page, job.id);

    let hits = await search(page, "Candidate B1");
    await expect(hits.getByRole("option")).toHaveCount(1);
    await expect(hits.getByRole("option")).toContainText(
      candidateName("Candidate B1"),
    );

    hits = await search(page, "e2e-cand-2-alt");
    const option = hits.locator(`[data-application-id="${b1.applicationId}"]`);
    await expect(
      option,
      "a confirmed second address finds the applicant",
    ).toHaveCount(1);

    await search(page, "e2e-no-such-applicant");
    await expect(
      page.getByRole("status").filter({ hasText: "No matches" }),
    ).toBeVisible();

    hits = await search(page, "e2e-cand-2-alt");
    await hits.locator(`[data-application-id="${b1.applicationId}"]`).click();
    await expect(page).toHaveURL(
      new RegExp(`/recruiting/applications/${b1.applicationId}$`),
    );
    await expect(
      page.getByRole("heading", {
        level: 1,
        name: candidateName("Candidate B1"),
      }),
    ).toBeVisible({ timeout: 20_000 });
  });

  test("?focus= pages the Rejected lane to the card, and the detail page leads back to it", async ({
    as,
  }) => {
    const page = await as("admin");
    const job = seedJob(page, "board");
    const oldest = seedApplication(page, "Candidate R25").applicationId;

    await openBoard(page, job.id, { focus: oldest });
    const target = card(lane(page, "rejected"), oldest);
    await expect(
      target,
      "the focused card is loaded from the second page",
    ).toBeVisible({
      timeout: 20_000,
    });
    // The highlight fades after three seconds; being scrolled to stays.
    await expect(target).toBeInViewport();
    await expect(page).not.toHaveURL(/focus=/);

    // R24 is also on the Rejected lane's second page, so the board has to
    // page and scroll to bring it back from its detail page.
    const r24 = seedApplication(page, "Candidate R24").applicationId;
    await openApplication(page, r24, candidateName("Candidate R24"));
    // The board drops ?focus= as soon as it has acted on it, so the URL the
    // link led to is recorded rather than read afterwards.
    const visited = [];
    const record = (frame) => {
      if (frame === page.mainFrame()) visited.push(new URL(frame.url()));
    };
    page.on("framenavigated", record);
    await page
      .locator("main")
      .getByRole("link", { name: "Applications Board" })
      .click();
    const back = card(lane(page, "rejected"), r24);
    await expect(back, "the card is loaded from the second page").toBeVisible({
      timeout: 20_000,
    });
    await expect(back).toBeInViewport();
    page.off("framenavigated", record);
    expect(
      visited.some(
        (u) =>
          u.pathname === "/recruiting/board" &&
          u.searchParams.get("jobId") === String(job.id) &&
          u.searchParams.get("focus") === String(r24),
      ),
      visited.map(String).join("\n"),
    ).toBe(true);
    await expect(page).not.toHaveURL(/focus=/);
  });
});
