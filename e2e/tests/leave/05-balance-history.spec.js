import { test, expect } from "../../fixtures.js";
import { ledgerOf, needLeaveSeed } from "./helpers.js";

// Balance history as e2e-member: every ledger row, newest first, and the
// total. Compared with the database, since an earlier spec may have added
// the M2 deduction; the seeded rows are checked by their own figures.

const LABELS = {
  leave_deduction: "Leave taken",
  manual_adjustment: "Adjustment by administrator",
  exchange_credit: "Holiday worked",
};
const MONTHS = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split(" ");
const shown = (iso) => {
  const [y, m, d] = iso.split("-").map(Number);
  return `${MONTHS[m - 1]} ${d}, ${y}`;
};

test.describe("balance history", { tag: "@leave" }, () => {
  test("lists every ledger row newest first with the total on record", async ({
    as,
  }) => {
    const page = await as("member");
    needLeaveSeed(page);
    const rows = ledgerOf(page.account.userId);
    await page.goto("/leave/balance-history");
    await expect(
      page.getByRole("heading", { name: "Balance history" }),
    ).toBeVisible({ timeout: 20_000 });
    const items = page
      .locator('[data-slot="card"]')
      .filter({ hasText: "Total on record" })
      .locator("li");
    await expect(items).toHaveCount(rows.length);
    for (const [at, [type, hours, date, note]] of rows.entries()) {
      const item = items.nth(at);
      await expect(item).toContainText(LABELS[type]);
      await expect(item).toContainText(
        `${Number(hours) > 0 ? "+" : ""}${hours} h`,
      );
      await expect(item).toContainText(shown(date));
      if (note) await expect(item).toContainText(note);
    }
    const opening = items.filter({ hasText: "E2E opening balance" });
    await expect(opening).toContainText("Adjustment by administrator");
    await expect(opening).toContainText("+60.00 h");
    await expect(opening).toContainText("Dec 31, 2019");
    await expect(items.filter({ hasText: "-12.00 h" })).toContainText(
      "Leave taken",
    );

    const total = rows.reduce((sum, [, hours]) => sum + Number(hours), 0);
    await expect(
      page.locator("div").filter({ hasText: /^Total on record/ }),
    ).toContainText(`${total.toFixed(2)} h`);
  });
});
