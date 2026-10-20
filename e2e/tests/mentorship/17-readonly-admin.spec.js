import { test, expect, settle } from "../../fixtures.js";
import {
  callApi,
  idOf,
  needFlagOn,
  needSeed,
  openDetail,
  openParticipants,
  roundSection,
  rowFor,
  timeline,
} from "./helpers.js";

// e2e-readonly holds only mentorship.admin.read: it sees the console, the
// lists and the detail pages of the live round, and nothing that writes.
// Two writes it sends straight to the API are refused. The matching results
// page is checked in 18-edit-lock, which leaves a succeeded run behind.
//   Mentee S1   detail page (no Change status / flag, Mark as notified or
//               Send email where e2e-admin has them); the note and the
//               withdrawal it tries to raise
//   Mentee G1   detail page with a v2 meeting log (no Edit)
//   Mentee H2   on Needs exemption (no Request exemption)

const SEEDED = "@e2e.purrf.test";

test.describe("read-only mentorship admin", { tag: "@mentorship" }, () => {
  test("the console and detail pages show no write buttons", async ({ as }) => {
    // Five pages, each waited on until it stops fetching.
    test.setTimeout(150_000);
    const page = await as("readonly");
    needSeed(page);
    const { roundId, roundName } = page.seed;
    expect(page.account.permissions).toEqual(["mentorship.admin.read"]);

    await page.goto("/mentorship-management");
    await expect(page.getByText("Mentorship Round Management")).toBeVisible({
      timeout: 20_000,
    });
    await settle(page);
    await expect(
      page.getByRole("button", { name: "Create New Round" }),
    ).toHaveCount(0);
    const row = page
      .locator("table")
      .first()
      .locator("tbody tr")
      .filter({
        has: page.getByRole("cell", { name: roundName, exact: true }),
      });
    await expect(row.getByRole("button", { name: "View round" })).toHaveCount(
      1,
    );
    await expect(row.getByRole("button", { name: "Edit round" })).toHaveCount(
      0,
    );

    await openParticipants(page, {
      round: roundId,
      q: SEEDED,
      needsExemption: "1",
    });
    const h2 = rowFor(page, idOf(page, "Mentee H2"));
    await expect(h2).toContainText(/Quit after being matched/);
    await expect(
      h2.getByRole("button", { name: "Request exemption" }),
    ).toHaveCount(0);

    await openDetail(page, idOf(page, "Mentee S1"), roundId);
    await expect(
      page.getByRole("button", { name: "Block from Purrf" }),
    ).toHaveCount(0);
    await expect(
      timeline(page).getByRole("button", { name: "Add a note" }),
    ).toHaveCount(0);

    await openDetail(page, idOf(page, "Mentee G1"), roundId);
    const section = roundSection(page, roundName);
    await expect(section.getByText(/^Meetings \d+\/\d+$/)).toBeVisible();
    await expect(
      section.getByRole("button", { name: "Edit", exact: true }),
    ).toHaveCount(0);
  });

  // Status requests sit behind the matching-run flag.
  test(
    "a reader gets no Change status / flag where a writer has one",
    { tag: "@flag:matching-run" },
    async ({ as }) => {
      needFlagOn("matching-run");
      const admin = await as("admin");
      const page = await as("readonly");
      needSeed(page);
      const { roundId } = page.seed;
      const s1 = idOf(page, "Mentee S1");
      const change = (p) =>
        p.getByRole("button", { name: "Change status / flag" });

      await openDetail(admin, s1, roundId);
      await expect(change(admin)).toBeVisible();
      await openDetail(page, s1, roundId);
      await expect(change(page)).toHaveCount(0);
    },
  );

  // Mark as notified sits behind the Kit email flag.
  test(
    "a reader gets no Mark as notified where a writer has one",
    { tag: "@flag:mentorship-kit-email" },
    async ({ as }) => {
      needFlagOn("mentorship-kit-email");
      const admin = await as("admin");
      const page = await as("readonly");
      needSeed(page);
      const { roundId } = page.seed;
      const s1 = idOf(page, "Mentee S1");
      const mark = (p) =>
        timeline(p).getByRole("button", { name: "Mark as notified" });

      await openDetail(admin, s1, roundId);
      await expect(mark(admin)).toBeVisible();
      await openDetail(page, s1, roundId);
      await expect(mark(page)).toHaveCount(0);
    },
  );

  // The list's selection and Send notification exist only while the Kit
  // email flag is on; the Notifications column shows the flag is on here.
  test(
    "the lists offer a reader no selection and no Send notification",
    { tag: "@flag:mentorship-kit-email" },
    async ({ as }) => {
      needFlagOn("mentorship-kit-email");
      const page = await as("readonly");
      needSeed(page);
      await openParticipants(page, { round: page.seed.roundId, q: SEEDED });
      const s1 = rowFor(page, idOf(page, "Mentee S1"));
      await expect(s1).toHaveCount(1);
      await expect(
        // The table's header cells carry the cell role, not columnheader.
        page.getByRole("cell", { name: "Notifications", exact: true }),
      ).toBeVisible();
      await expect(
        page.getByRole("checkbox", { name: "Select all on this page" }),
      ).toHaveCount(0);
      await expect(s1.getByRole("checkbox")).toHaveCount(0);
      await expect(
        page.getByRole("button", { name: /^Send notification/ }),
      ).toHaveCount(0);
    },
  );

  // Send email needs a sender set up in the environment as well as write.
  test("a reader gets no Send email where a writer has one", async ({ as }) => {
    const admin = await as("admin");
    const page = await as("readonly");
    needSeed(page);
    const { roundId } = page.seed;
    const s1 = idOf(page, "Mentee S1");

    await openDetail(admin, s1, roundId);
    test.skip(
      (await admin.getByRole("button", { name: "Send email" }).count()) === 0,
      "no sender is set up for participant email in this environment",
    );

    await openDetail(page, s1, roundId);
    await expect(page.getByRole("button", { name: "Send email" })).toHaveCount(
      0,
    );
  });

  // PUR-782: starting a run needs write; a reader keeps the results button.
  test(
    "the Eligible list offers a reader no Run matching",
    { tag: "@flag:matching-run" },
    async ({ as }) => {
      needFlagOn("matching-run");
      const page = await as("readonly");
      needSeed(page);
      await openParticipants(page, {
        round: page.seed.roundId,
        q: SEEDED,
        eligible: "1",
      });
      await expect(
        page.getByRole("button", { name: "View matching results" }),
      ).toBeVisible({ timeout: 20_000 });
      await expect(
        page.getByRole("button", { name: /^Run matching/ }),
        "a reader cannot start a matching run",
      ).toHaveCount(0);
      await expect(
        page.getByRole("checkbox", { name: "Select all on this page" }),
      ).toHaveCount(0);
    },
  );

  test("writes sent straight to the API are refused", async ({ as }) => {
    const reviewer = await as("reviewer");
    const page = await as("readonly");
    needSeed(page);
    const { roundId } = page.seed;
    const s1 = idOf(page, "Mentee S1");
    const base = `/api/mentorship/admin/rounds/${roundId}/participants/${s1}`;
    page.expectApiError({
      method: "POST",
      path: new RegExp(`^${base}/notes$`),
      status: 403,
    });
    page.expectApiError({
      method: "POST",
      path: new RegExp(`^${base}/withdraw-request$`),
      status: 403,
    });

    await openDetail(page, s1, roundId);
    const note = await callApi(page, "POST", `${base}/notes`, {
      body: "e2e regression: a reader's note",
    });
    expect(note.status, JSON.stringify(note.json)).toBe(403);
    const withdraw = await callApi(page, "POST", `${base}/withdraw-request`, {
      reviewerId: reviewer.account.userId,
      reason: "e2e regression: a reader's request",
    });
    expect(withdraw.status, JSON.stringify(withdraw.json)).toBe(403);

    // Nothing landed.
    await openDetail(page, s1, roundId);
    await expect(
      timeline(page)
        .getByRole("listitem")
        .filter({ hasText: "a reader's note" }),
    ).toHaveCount(0);
    await expect(
      page.getByRole("region", { name: "Waiting on a decision" }),
    ).toHaveCount(0);
  });
});
