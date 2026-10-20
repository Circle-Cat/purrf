import { test, expect, settle } from "../../fixtures.js";
import { opsId, opsName, rowsOf } from "./helpers.js";

// Granting and revoking on the permission page, as e2e-admin
// (permission.manage), only to the seeded Ops Grant. A grant is one
// user_permissions row: it reads "granted" in the audit log until it is
// revoked, then "revoked". internal_activity.read reaches no notification
// or picker, so holding it for a moment changes nothing anyone sees.

const PERMISSION = "internal_activity.read";

const activeGrants = (userId) =>
  rowsOf(`
    SELECT permission_name, granted_by FROM user_permissions
    WHERE user_id = ${userId} AND revoked_timestamp IS NULL`);

async function openPermissions(page, userId) {
  await page.goto(`/admin/users?user_id=${userId}`);
  const dialog = page.getByRole("dialog");
  await expect(
    dialog.getByRole("heading", { name: opsName("grant") }),
  ).toBeVisible({
    timeout: 20_000,
  });
  await expect(
    dialog.getByRole("checkbox", { name: PERMISSION }),
  ).toBeVisible();
  await settle(page);
  return dialog;
}

async function auditFor(page, userId) {
  await page.keyboard.press("Escape");
  await page.getByRole("tab", { name: "Audit Log" }).click();
  const panel = page.getByRole("tabpanel");
  await panel.getByPlaceholder("User ID").fill(String(userId));
  await panel.getByRole("button", { name: "Search", exact: true }).click();
  return panel.locator("tbody tr").filter({ hasText: String(userId) });
}

test.describe("permission page", { tag: "@accounts" }, () => {
  test("grants and revokes a permission and the audit log records each", async ({
    as,
  }) => {
    test.setTimeout(90_000);
    const page = await as("admin");
    const id = opsId(page, "grant");
    let dialog = await openPermissions(page, id);
    await expect(
      dialog.getByRole("link", { name: "Account state →" }),
    ).toHaveAttribute("href", `/admin/accounts?user_id=${id}`);
    const box = dialog.getByRole("checkbox", { name: PERMISSION });
    await expect(box).not.toBeChecked();
    const save = dialog.getByRole("button", { name: "Save" });
    await expect(save).toBeDisabled();
    await box.click();
    await save.click();
    await expect(
      page.locator('[data-sonner-toast][data-type="success"]').filter({
        hasText: "Permissions updated",
      }),
    ).toBeVisible();
    expect(activeGrants(id)).toEqual([
      [PERMISSION, String(page.account.userId)],
    ]);

    let rows = await auditFor(page, id);
    await expect(rows).toHaveCount(1);
    await expect(rows).toContainText("granted");
    await expect(rows).toContainText("admin");

    await page.getByRole("tab", { name: "Users" }).click();
    dialog = await openPermissions(page, id);
    await expect(
      dialog.getByRole("checkbox", { name: PERMISSION }),
    ).toBeChecked();
    await dialog.getByRole("checkbox", { name: PERMISSION }).click();
    await dialog.getByRole("button", { name: "Save" }).click();
    await expect.poll(() => activeGrants(id).length).toBe(0);
    const [[revokedBy]] = rowsOf(
      `SELECT revoked_by FROM user_permissions WHERE user_id = ${id} AND permission_name = '${PERMISSION}'`,
    );
    expect(Number(revokedBy)).toBe(page.account.userId);

    rows = await auditFor(page, id);
    await expect(rows).toHaveCount(1);
    await expect(rows).toContainText("revoked");
  });
});
