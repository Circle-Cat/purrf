import { test, expect } from "../../fixtures.js";
import {
  idOf,
  nameOf,
  needFlagOn,
  needSeed,
  openParticipants,
  rowFor,
  searchWith,
} from "./helpers.js";

// The Send notification dialog, opened from the Participants list and
// cancelled. Nothing is created or sent: Create (which makes the send and
// loads its preview) and Confirm are never clicked, and the guard aborts
// every Kit write anyway.
//   Mentee X1    picked in the Registered list
//   Mentor H-M1  picked in the Not registered list

const STAGES = [
  "New round invitation",
  "Admission & onboarding",
  "Onboarding reminder",
  "Match result",
  "First contact reminder",
  "Mentor check-in",
  "Mid-term reminder",
  "Final follow-up",
  "Feedback invitation",
];

/** Tick one person and open the dialog, waiting for the Kit drafts. */
async function openSendDialog(page, userId) {
  await rowFor(page, userId).getByRole("checkbox").check();
  await expect(page.getByText("1 people selected")).toBeVisible();
  const drafts = page.waitForResponse(
    (r) =>
      r.request().method() === "GET" &&
      new URL(r.url()).pathname.endsWith("/mentorship/admin/kit-drafts"),
    { timeout: 30_000 },
  );
  await page.getByRole("button", { name: "Send notification · 1" }).click();
  const dialog = page.getByRole("dialog");
  await expect(
    dialog.getByRole("heading", { name: "Send notification" }),
  ).toBeVisible();
  await drafts;
  return dialog;
}

test.describe(
  "Kit notification dialog",
  { tag: ["@mentorship", "@flag:mentorship-kit-email"] },
  () => {
    test("picking a stage and a draft for one person, up to Create", async ({
      as,
    }) => {
      needFlagOn("mentorship-kit-email");
      const page = await as("admin");
      needSeed(page);
      const x1 = idOf(page, "Mentee X1");
      await openParticipants(page, { round: page.seed.roundId, id: x1 });

      const dialog = await openSendDialog(page, x1);
      await expect(dialog).toContainText("To 1 person");
      await expect(dialog).toContainText(nameOf("Mentee X1"));

      const stage = dialog.getByLabel("Stage");
      await expect(stage).toHaveValue("");
      const labels = (await stage.locator("option").allTextContents()).slice(1);
      expect(labels).toEqual(STAGES);
      const create = dialog.getByRole("button", { name: "Create" });
      await expect(create).toBeDisabled();

      await stage.selectOption({ label: "Mid-term reminder" });
      await expect(create, "a draft is still to pick").toBeDisabled();

      const draft = dialog.getByLabel("Kit draft");
      const usable = draft.locator("option:not([disabled])").filter({
        hasNotText: "Select a draft",
      });
      await expect(dialog.getByRole("alert")).toHaveCount(0);
      if ((await usable.count()) === 0) {
        test.info().annotations.push({
          type: "not checked",
          description: "Kit has no draft that can be sent; Create stays off",
        });
      } else {
        await draft.selectOption(await usable.first().getAttribute("value"));
        await expect(create).toBeEnabled();
      }

      // Stop here: Create would make the send and load its preview.
      await dialog.getByRole("button", { name: "Cancel" }).click();
      await expect(dialog).toBeHidden();
    });

    test("from the Not registered list the stage starts at the new round invitation", async ({
      as,
    }) => {
      needFlagOn("mentorship-kit-email");
      const page = await as("admin");
      needSeed(page);
      const hm1 = idOf(page, "Mentor H-M1");
      await openParticipants(page, { round: page.seed.roundId, id: hm1 });
      await searchWith(page, { List: "Not registered" });

      const dialog = await openSendDialog(page, hm1);
      await expect(dialog).toContainText(nameOf("Mentor H-M1"));
      await expect(dialog.getByLabel("Stage")).toHaveValue("round_recruitment");
      await dialog.getByRole("button", { name: "Cancel" }).click();
      await expect(dialog).toBeHidden();
    });
  },
);
