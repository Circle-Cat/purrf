import { test, expect } from "../../fixtures.js";
import {
  beijingToday,
  callApi,
  ledgerOf,
  needLeaveSeed,
  openAdmin,
  personId,
  recordWrites,
  rowsOf,
  shiftDate,
} from "./helpers.js";

// Leave administration → Balances as e2e-admin (leave.admin). The list is
// the Redis employment population, real employees only, so nothing here
// names or totals them: figures are compared with the API's own answer.
// A correction through the dialog can only target a real person, so the
// guard must abort it; the successful correction goes through the API to a
// seed person (990510, "E2E Leave Adjust", seeded with 52 h).

const balancesRead = (page) =>
  page.waitForResponse(
    (r) =>
      r.request().method() === "GET" &&
      new URL(r.url()).pathname === "/api/leave/balances",
    { timeout: 30_000 },
  );

async function openBalances(page) {
  const read = balancesRead(page);
  await openAdmin(page, "Balances");
  return (await (await read).json()).data;
}

const ADJUST = (status) => ({
  method: "POST",
  path: /^\/api\/leave\/adjustments$/,
  status,
});

test.describe("leave balances", { tag: "@leave" }, () => {
  test("the title and rows agree with what the server sent", async ({ as }) => {
    const page = await as("admin");
    needLeaveSeed(page);
    const data = await openBalances(page);
    await expect(
      page.getByText(
        `Accruing: ${data.people.length} of ${data.profileCount} directory profiles`,
      ),
    ).toBeVisible();
    await expect(page.getByRole("button", { name: "Correct" })).toHaveCount(
      data.people.length,
    );
    const nonEmpty = Object.entries(data.excluded).filter(
      ([, list]) => list.length > 0,
    );
    for (const [, list] of nonEmpty) {
      await expect(
        page.getByText(list.join(", "), { exact: true }),
      ).toBeVisible();
    }
  });

  test("the correction dialog checks its own fields without sending anything", async ({
    as,
  }) => {
    const page = await as("admin");
    needLeaveSeed(page);
    const data = await openBalances(page);
    test.skip(data.people.length === 0, "nobody is accruing on test");
    const writes = recordWrites(page);
    await page.getByRole("button", { name: "Correct" }).first().click();
    const dialog = page.getByRole("dialog");
    await expect(dialog).toContainText(
      `Holding ${data.people[0].balanceHours} h now.`,
    );
    await dialog.getByRole("button", { name: "Write the correction" }).click();
    await expect(dialog).toContainText("This cannot be undone.");
    await dialog.getByRole("button", { name: "Yes, write it" }).click();
    await expect(dialog).toContainText(
      "Give the hours and the date they take effect.",
    );
    await dialog.getByRole("button", { name: "Cancel" }).click();
    await expect(dialog).toBeHidden();
    expect(writes).toEqual([]);
  });

  test("the guard stops a correction to a real person", async ({ as }) => {
    const page = await as("admin");
    needLeaveSeed(page);
    const data = await openBalances(page);
    test.skip(data.people.length === 0, "nobody is accruing on test");
    const target = data.people[0].userId;
    const before = ledgerOf(target);
    page.expectBlocked(
      /POST \/api\/leave\/adjustments: user \d+ is not a leave seed person/,
    );
    await page.getByRole("button", { name: "Correct" }).first().click();
    const dialog = page.getByRole("dialog");
    await dialog.getByLabel("Hours").fill("1");
    await dialog
      .getByLabel("Effective date")
      .fill(shiftDate(beijingToday(), -1));
    await dialog.getByLabel("Note").fill("E2E must never be written");
    await dialog.getByRole("button", { name: "Write the correction" }).click();
    await dialog.getByRole("button", { name: "Yes, write it" }).click();
    await expect(dialog.locator("p.text-red-700")).toBeVisible();
    await expect(dialog).not.toContainText("Wrote ");
    expect(ledgerOf(target)).toEqual(before);
  });

  test("a correction to a seed person is written as the admin and returns the new balance", async ({
    as,
  }) => {
    const page = await as("admin");
    needLeaveSeed(page);
    page.expectApiError(ADJUST(400));
    const target = personId(page, "Leave Adjust");
    await openAdmin(page, "Balances");
    const today = beijingToday();
    const post = (body) =>
      callApi(page, "POST", "/api/leave/adjustments", {
        userId: target,
        ...body,
      });

    // Refused: in the future, zero hours, no note. Nothing written.
    const refusals = [
      [
        { hours: "-1", effectiveDate: shiftDate(today, 1), note: "E2E" },
        "is in the future",
      ],
      [
        { hours: "0", effectiveDate: today, note: "E2E" },
        "zero hours changes nothing",
      ],
      [{ hours: "-1", effectiveDate: today, note: "   " }, "needs a note"],
    ];
    for (const [body, message] of refusals) {
      const res = await post(body);
      expect(res.status).toBe(400);
      expect(res.json.message).toContain(message);
    }
    expect(ledgerOf(target)).toHaveLength(1);

    const res = await post({
      hours: "-3.50",
      effectiveDate: today,
      note: "E2E correction",
    });
    expect(res.status).toBe(200);
    expect(res.json.data).toMatchObject({
      userId: target,
      hours: "-3.50",
      effectiveDate: today,
      note: "E2E correction",
      balanceHours: "48.50",
    });
    expect(ledgerOf(target)[0]).toEqual([
      "manual_adjustment",
      "-3.50",
      today,
      "E2E correction",
      String(page.account.userId),
    ]);
    expect(
      rowsOf(`SELECT count(*) FROM event WHERE actor_id = ${page.account.userId}
              AND event_type LIKE 'leave.%'`)[0][0],
    ).toBe("0");
  });
});
