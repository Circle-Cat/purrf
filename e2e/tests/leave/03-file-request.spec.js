import { test, expect } from "../../fixtures.js";
import {
  beijingToday,
  needLeaveSeed,
  openDashboard,
  recordWrites,
  requestCount,
  rowsOf,
  shiftDate,
  timeOffCard,
} from "./helpers.js";

// Request leave, from the Time off card, as e2e-member. Filing successfully
// is not tested: it needs a company address and a Redis employment profile
// (see SIDE-EFFECTS.md). What is tested is the form's own checks, which send
// nothing, and the server's refusals, which write nothing.

const FILE = { method: "POST", path: /^\/api\/leave\/requests$/, status: 400 };

async function openForm(page) {
  await openDashboard(page);
  await timeOffCard(page)
    .getByRole("button", { name: "Request time off" })
    .click();
  const dialog = page.getByRole("dialog", { name: "Request leave" });
  await expect(dialog).toBeVisible();
  return dialog;
}

const leaveEvents = (userId) =>
  Number(
    rowsOf(`
    SELECT count(*) FROM event e JOIN leave_request r
      ON e.subject_type = 'leave_request' AND e.subject_id = r.leave_request_id
    WHERE r.user_id = ${Number(userId)}`)[0][0],
  );

test.describe("request leave", { tag: "@leave" }, () => {
  test("the form refuses what it can see is wrong without sending anything", async ({
    as,
  }) => {
    const page = await as("member");
    needLeaveSeed(page);
    const writes = recordWrites(page);
    const dialog = await openForm(page);
    const submit = dialog.getByRole("button", { name: "Submit" });

    await submit.click();
    await expect(dialog).toContainText("Pick both dates.");

    await dialog.getByLabel("First day").fill("2099-09-02");
    await dialog.getByLabel("Last day").fill("2099-09-01");
    await submit.click();
    await expect(dialog).toContainText(
      "The last day cannot come before the first.",
    );

    await dialog.getByLabel("First day").fill("2099-09-01");
    await dialog.getByLabel("From (optional)").fill("09:00");
    await submit.click();
    await expect(dialog).toContainText("Give both times, or neither.");

    await dialog.getByLabel("From (optional)").fill("13:00");
    await dialog.getByLabel("To (optional)").fill("09:00");
    await submit.click();
    await expect(dialog).toContainText(
      "The end time has to come after the start time.",
    );
    expect(writes).toEqual([]);
  });

  test("times are offered only for a single day of leave, and Cancel clears the form", async ({
    as,
  }) => {
    const page = await as("member");
    needLeaveSeed(page);
    const writes = recordWrites(page);
    const dialog = await openForm(page);
    const from = dialog.getByLabel("From (optional)");

    await expect(from).toHaveCount(0);
    await dialog.getByLabel("First day").fill("2099-09-01");
    await dialog.getByLabel("Last day").fill("2099-09-01");
    await expect(from).toBeVisible();
    await dialog.getByLabel("Last day").fill("2099-09-02");
    await expect(from).toHaveCount(0);
    await dialog.getByLabel("Last day").fill("2099-09-01");
    await expect(from).toBeVisible();
    await dialog.getByLabel("Type").selectOption("exchange");
    await expect(from).toHaveCount(0);
    await dialog.getByLabel("Reason (optional)").fill("E2E never sent");

    await dialog.getByRole("button", { name: "Cancel" }).click();
    await expect(dialog).toBeHidden();
    await timeOffCard(page)
      .getByRole("button", { name: "Request time off" })
      .click();
    await expect(dialog.getByLabel("Type")).toHaveValue("paid");
    await expect(dialog.getByLabel("First day")).toHaveValue("");
    await expect(dialog.getByLabel("Last day")).toHaveValue("");
    await expect(dialog.getByLabel("Reason (optional)")).toHaveValue("");
    expect(writes).toEqual([]);
  });

  test("leave starting in the past is refused by the server and nothing is written", async ({
    as,
  }) => {
    const page = await as("member");
    needLeaveSeed(page);
    page.expectApiError(FILE);
    const me = page.account.userId;
    const before = requestCount(me);
    const yesterday = shiftDate(beijingToday(), -1);
    const dialog = await openForm(page);
    await dialog.getByLabel("First day").fill(yesterday);
    await dialog.getByLabel("Last day").fill(yesterday);
    await dialog.getByRole("button", { name: "Submit" }).click();
    await expect(dialog).toContainText(
      `Leave cannot start on ${yesterday}, which has passed.`,
    );
    await expect(dialog).toBeVisible();
    expect(requestCount(me)).toBe(before);
  });

  test("a test account has no company address, so even a valid request is refused", async ({
    as,
  }) => {
    const page = await as("member");
    needLeaveSeed(page);
    page.expectApiError(FILE);
    const me = page.account.userId;
    const before = requestCount(me);
    const events = leaveEvents(me);
    const dialog = await openForm(page);
    await dialog.getByLabel("First day").fill("2099-09-01");
    await dialog.getByLabel("Last day").fill("2099-09-02");
    await dialog.getByLabel("Reason (optional)").fill("E2E refused");
    await dialog.getByRole("button", { name: "Submit" }).click();
    await expect(dialog).toContainText(
      "This account has no corporate address, so its Azure record cannot be found.",
    );
    expect(requestCount(me)).toBe(before);
    expect(leaveEvents(me)).toBe(events);
  });

  test("a refusal does not stay on the form after it is closed and opened again", async ({
    as,
  }) => {
    // PUR-800: the form used to reopen still showing the last refusal.
    const page = await as("member");
    needLeaveSeed(page);
    page.expectApiError(FILE);
    const dialog = await openForm(page);
    await dialog.getByLabel("First day").fill("2099-09-01");
    await dialog.getByLabel("Last day").fill("2099-09-01");
    await dialog.getByRole("button", { name: "Submit" }).click();
    const refusal = dialog.getByText(
      "This account has no corporate address, so its Azure record cannot be found.",
    );
    await expect(refusal).toBeVisible();
    await dialog.getByRole("button", { name: "Cancel" }).click();
    await expect(dialog).toBeHidden();
    await timeOffCard(page)
      .getByRole("button", { name: "Request time off" })
      .click();
    await expect(dialog.getByLabel("First day")).toHaveValue("");
    await expect(refusal).toHaveCount(0);
  });
});
