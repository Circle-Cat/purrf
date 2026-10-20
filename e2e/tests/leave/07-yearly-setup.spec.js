import { test, expect } from "../../fixtures.js";
import {
  beijingYear,
  needLeaveSeed,
  openAdmin,
  rowsOf,
  segmentsOf,
} from "./helpers.js";

// Leave administration → Yearly setup as e2e-admin. Saving replaces a whole
// year of the one company calendar, so only 2019 is edited (a past year:
// nothing can be filed or approved in it, and accrual never reads holidays),
// always with "E2E …" names; the guard aborts any other year. Global setup
// seeds 2019 with "E2E National Day 2019" (Oct 1–7) and 2099 for approvals.

const SAVE = {
  method: "PUT",
  path: /^\/api\/leave\/holidays\/2019$/,
  status: 400,
};

const holidaysOf = (year) =>
  rowsOf(`
    SELECT date, name, is_exchangeable FROM leave_holiday
    WHERE year = ${year} ORDER BY date`);

const title = (page) => page.locator('[data-slot="card-title"]').first();

async function openYear(page, year) {
  await openAdmin(page, "Yearly setup");
  const picker = page.getByLabel("Year", { exact: true });
  await expect(picker.locator(`option[value="${year}"]`)).toBeAttached();
  await picker.selectOption(String(year));
  await expect(title(page)).toContainText(`${year} —`);
  await expect(page.getByText("Loading…")).toHaveCount(0);
}

/** Fill the last segment row. */
async function fillLast(page, { name, start, end, exchangeable = false }) {
  const rows = page.locator("li").filter({ has: page.getByLabel("Name") });
  const row = rows.last();
  await row.getByLabel("Name").fill(name);
  await row.getByLabel("First day").fill(start);
  await row.getByLabel("Last day").fill(end);
  if (exchangeable) await row.getByLabel("Exchangeable").check();
}

async function saveYear(page, year) {
  await page.getByRole("button", { name: "Save the year" }).click();
  const confirm = page.getByRole("dialog", { name: `Replace all of ${year}?` });
  await expect(confirm).toBeVisible();
  const text = await confirm.textContent();
  await confirm.getByRole("button", { name: `Replace ${year}` }).click();
  await expect(confirm).toBeHidden();
  return text;
}

test.describe("yearly setup", { tag: "@leave" }, () => {
  test("offers every entered year plus this year and next, opening on this year", async ({
    as,
  }) => {
    const page = await as("admin");
    needLeaveSeed(page);
    const thisYear = beijingYear();
    const entered = rowsOf(
      "SELECT DISTINCT year FROM leave_holiday ORDER BY year",
    ).map(([y]) => Number(y));
    const years = [...new Set([...entered, thisYear, thisYear + 1])].sort();
    await openAdmin(page, "Yearly setup");
    const picker = page.getByLabel("Year", { exact: true });
    await expect(picker.locator("option")).toHaveText(years.map(String));
    await expect(picker).toHaveValue(String(thisYear));
    const segments = segmentsOf(thisYear);
    if (segments.length === 0) {
      await expect(
        page.getByText(
          `Nothing entered for ${thisYear} yet. A year left empty refuses every leave request dated in it.`,
        ),
      ).toBeVisible();
    } else {
      const days = segments.reduce((n, s) => n + s.days, 0);
      await expect(title(page)).toHaveText(
        `${thisYear} — ${segments.length} holidays, ${days} days`,
      );
      const names = page.getByLabel("Name");
      await expect(names).toHaveCount(segments.length);
      for (const [at, { name }] of segments.entries()) {
        await expect(names.nth(at)).toHaveValue(name);
      }
    }
    await expect(
      page.getByRole("button", { name: "Save the year" }),
    ).toBeDisabled();
  });

  test("adding a holiday to 2019 and saving replaces the year after a confirmation", async ({
    as,
  }) => {
    const page = await as("admin");
    needLeaveSeed(page);
    await openYear(page, 2019);
    await expect(title(page)).toHaveText("2019 — 1 holidays, 7 days");
    await page.getByRole("button", { name: "Add a holiday" }).click();
    await fillLast(page, {
      name: "E2E Spring 2019",
      start: "2019-02-05",
      end: "2019-02-06",
      exchangeable: true,
    });
    await expect(title(page)).toHaveText("2019 — 2 holidays, 9 days");
    const confirmText = await saveYear(page, 2019);
    expect(confirmText).toContain(
      "Saving replaces every company holiday in 2019 with the 2 on this page, covering 9 days.",
    );
    await expect(
      page.getByRole("button", { name: "Save the year" }),
    ).toBeDisabled();
    await expect(page.locator("p.text-red-700")).toHaveCount(0);
    const rows = holidaysOf(2019);
    expect(rows).toHaveLength(9);
    expect(rows.slice(0, 2)).toEqual([
      ["2019-02-05", "E2E Spring 2019", "t"],
      ["2019-02-06", "E2E Spring 2019", "t"],
    ]);
    expect(
      rows.filter(([, name]) => name === "E2E National Day 2019"),
    ).toHaveLength(7);
    // Read back from the server, in date order.
    await expect(page.getByLabel("Name").first()).toHaveValue(
      "E2E Spring 2019",
    );
  });

  test("the server refuses a year that does not add up, and 2019 is left as it was", async ({
    as,
  }) => {
    const page = await as("admin");
    needLeaveSeed(page);
    page.expectApiError(SAVE);
    const before = holidaysOf(2019);
    const cases = [
      [
        { name: "E2E Wrong Year", start: "2020-01-07", end: "2020-01-07" },
        "E2E Wrong Year falls in 2020, not 2019.",
      ],
      [
        { name: "E2E Overlap", start: "2019-10-07", end: "2019-10-08" },
        "E2E Overlap and E2E National Day 2019 both cover 2019-10-07.",
      ],
      [
        { name: "E2E Backwards", start: "2019-03-06", end: "2019-03-05" },
        "E2E Backwards ends before it starts.",
      ],
    ];
    for (const [segment, message] of cases) {
      await openYear(page, 2019);
      await page.getByRole("button", { name: "Add a holiday" }).click();
      await fillLast(page, segment);
      await saveYear(page, 2019);
      await expect(page.locator("p.text-red-700")).toHaveText(message);
      expect(holidaysOf(2019)).toEqual(before);
    }
  });

  test("a year cannot be saved empty", async ({ as }) => {
    const page = await as("admin");
    needLeaveSeed(page);
    page.expectApiError(SAVE);
    const before = holidaysOf(2019);
    await openYear(page, 2019);
    const remove = page.getByRole("button", { name: "Remove" });
    while ((await remove.count()) > 0) await remove.first().click();
    await expect(title(page)).toHaveText("2019 — 0 holidays, 0 days");
    await saveYear(page, 2019);
    await expect(page.locator("p.text-red-700")).toHaveText(
      "A year needs at least one company holiday. Leaving 2019 empty would refuse every leave request dated in it.",
    );
    expect(holidaysOf(2019)).toEqual(before);
  });

  test("the guard stops saving any year but 2019", async ({ as }) => {
    const page = await as("admin");
    needLeaveSeed(page);
    // Next year: the picker always offers it (the server's nextYear), and
    // it is never 2019.
    const year = beijingYear() + 1;
    const before = holidaysOf(year);
    page.expectBlocked(
      new RegExp(
        `PUT /api/leave/holidays/${year}: holidays of ${year} are real`,
      ),
    );
    await openYear(page, year);
    await page.getByRole("button", { name: "Add a holiday" }).click();
    await fillLast(page, {
      name: `E2E Guard ${year}`,
      start: `${year}-02-02`,
      end: `${year}-02-02`,
    });
    await saveYear(page, year);
    await expect(page.locator("p.text-red-700")).toBeVisible();
    expect(holidaysOf(year)).toEqual(before);
  });
});
