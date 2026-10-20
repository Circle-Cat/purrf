import { test, expect } from "../../fixtures.js";
import {
  decideOnDetail,
  idOf,
  nameOf,
  needFlagOn,
  needSeed,
  openDetail,
  openParticipants,
  raiseStatusRequest,
  rowFor,
  timeline,
} from "./helpers.js";

// Each test raises and approves one mark.
//   Mentor W-M1  no show, about their ended pair with Mentee W1 (W-M1 is
//                un_matched, so still taking part and can need an exemption;
//                W1 has withdrawn and would never be listed there)
//   Mentee S1    red flag, about no pair

const MARKS = [
  {
    person: "Mentor W-M1",
    type: "Mark as no show",
    action: "No show mark",
    badge: "No show",
    why: "No show in this round",
  },
  {
    person: "Mentee S1",
    type: "Raise a red flag",
    action: "Red flag",
    badge: "Red flag",
    why: "Red flag in this round",
  },
];

test.describe("marks", { tag: ["@mentorship", "@flag:matching-run"] }, () => {
  for (const mark of MARKS) {
    test(`${mark.badge}: approved, it shows on the header and timeline and needs an exemption`, async ({
      as,
    }) => {
      needFlagOn("matching-run");
      const reviewer = await as("reviewer");
      const page = await as("admin");
      needSeed(page);
      const { roundId } = page.seed;
      const id = idOf(page, mark.person);
      const header = page
        .getByRole("heading", { level: 2, name: nameOf(mark.person) })
        .locator("..");

      await openDetail(page, id, roundId);
      await expect(header.getByText(mark.badge, { exact: true })).toHaveCount(
        0,
      );
      await raiseStatusRequest(page, {
        type: mark.type,
        reviewerId: reviewer.account.userId,
      });

      await openDetail(reviewer, id, roundId);
      await decideOnDetail(reviewer, mark.action, "approve");

      await openDetail(page, id, roundId);
      await expect(header.getByText(mark.badge, { exact: true })).toBeVisible();
      const entry = timeline(page)
        .getByRole("listitem")
        .filter({ has: page.getByText(mark.badge, { exact: true }) });
      await expect(entry).toHaveCount(1);
      await expect(entry).toContainText("(via approval)");

      await openParticipants(page, {
        round: roundId,
        id,
        needsExemption: "1",
      });
      await expect(rowFor(page, id)).toContainText(mark.why);
    });
  }
});
