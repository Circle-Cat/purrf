import { test, expect } from "../../fixtures.js";
import {
  callApi,
  needRound,
  openMemberDashboard,
  openParticipants,
  rowFor,
  searchWith,
  successToast,
} from "./helpers.js";

// The member's side of the other phases, each in its own seeded round.
//   registration round  e2e-member, admitted as a mentee, registers. The
//                       dashboard keeps offering the real round open for
//                       registration (the seeded one closes later), so the
//                       registration is sent the way the dashboard's form
//                       sends it, from the member's page, to the seeded
//                       round. Registering into the live round, whose
//                       registration closed, is refused.
//   feedback round      e2e-member and Mentor F1 met all their meetings; the
//                       member writes feedback, and it shows on the round's
//                       feedback page.

const ROUND_PREFERENCES = {
  participantRole: "mentee",
  maxPartners: 1,
  goal: "E2E regression goal: land a software engineering role.",
  currentStage: "job_searching",
  timeUrgency: "within_6_months",
};

test.describe("registration and feedback", { tag: "@mentorship" }, () => {
  test("the member registers into the open seeded round, and the dashboard still points at the real one", async ({
    as,
  }) => {
    const member = await as("member");
    const page = await as("admin");
    const round = needRound(page, "registration");
    const { memberId, roundId: liveId } = page.seed;

    // Not registered yet: on the round's Not registered list.
    await openParticipants(page, { round: round.id, id: memberId });
    await searchWith(page, { List: "Not registered" });
    await expect(rowFor(page, memberId)).toHaveCount(1);
    await expect(rowFor(page, memberId)).toContainText("mentee");

    const slotsLoaded = member.waitForResponse(
      (r) => new URL(r.url()).pathname === "/api/mentorship/rounds/slots",
      { timeout: 30_000 },
    );
    await openMemberDashboard(member);
    const slots = (await (await slotsLoaded).json()).data;
    expect(slots.isRegistrationOpen).toBe(true);
    expect(
      slots.registrationRoundName,
      "registration and the admission email point at the real round",
    ).not.toMatch(/^E2E /);
    expect(slots.registrationRoundId).not.toBe(round.id);

    const path = `/api/mentorship/rounds/${round.id}/registration`;
    const form = await callApi(member, "GET", `${path}?role=mentee`);
    expect(form.status, JSON.stringify(form.json)).toBe(200);
    expect(form.json.data.isRegistered).toBe(false);
    const saved = await callApi(member, "POST", path, {
      globalPreferences: form.json.data.globalPreferences,
      roundPreferences: ROUND_PREFERENCES,
    });
    expect(saved.status, JSON.stringify(saved.json)).toBe(200);
    expect(saved.json.data.isRegistered).toBe(true);
    expect(saved.json.data.roundName).toBe(round.name);

    // The live round's registration closed with its onboarding deadline.
    const closedPath = `/api/mentorship/rounds/${liveId}/registration`;
    member.expectApiError({
      method: "POST",
      path: new RegExp(`^${closedPath}$`),
      status: 400,
    });
    const late = await callApi(member, "POST", closedPath, {
      globalPreferences: form.json.data.globalPreferences,
      roundPreferences: ROUND_PREFERENCES,
    });
    expect(late.status).toBe(400);
    expect(late.json?.message).toMatch(/^Registration period has ended/);

    // Registered: in the round's list as a signed-up mentee, off Not registered.
    await openParticipants(page, { round: round.id, id: memberId });
    const row = rowFor(page, memberId);
    await expect(row).toHaveCount(1);
    await expect(row).toContainText("signed_up");
    await searchWith(page, { List: "Not registered" });
    await expect(rowFor(page, memberId)).toHaveCount(0);
  });

  test("the member's feedback shows on the round's feedback page", async ({
    as,
  }) => {
    const member = await as("member");
    const page = await as("admin");
    const round = needRound(page, "feedback");
    const { memberId } = page.seed;

    const card = await openMemberDashboard(member, round.name);
    await expect(card.getByText("E2E Mentor F1")).toBeVisible();
    const open = card.getByRole("button", { name: "Submit Feedback" });
    await expect(open, "the round's feedback window is open").toBeVisible();
    await open.click();
    const dialog = member.getByRole("dialog");
    const said = `E2E regression feedback ${Date.now()}`;
    await dialog
      .getByPlaceholder("Share what you found most valuable...")
      .fill(said);
    await dialog.getByRole("radio", { name: "5", exact: true }).check();
    await dialog.getByRole("radio", { name: "Excellent" }).check();
    await dialog.getByRole("button", { name: "Submit", exact: true }).click();
    await expect(successToast(member, /^Feedback Submitted/)).toBeVisible();

    await page.goto(`/mentorship-management/rounds/${round.id}/feedback`);
    const row = page.locator("table tbody tr").filter({
      has: page.getByRole("cell", { name: String(memberId), exact: true }),
    });
    await expect(row).toContainText(said, { timeout: 20_000 });
  });
});
