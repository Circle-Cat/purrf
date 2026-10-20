import { test, expect, settle } from "../../fixtures.js";
import {
  lastEventId,
  needOps,
  openAccount,
  opsEmail,
  opsId,
  opsName,
  rowsOf,
  successToast,
  userEventRecipients,
  userState,
} from "./helpers.js";

// The account console as e2e-admin (user.admin and permission.manage), on
// the seeded ops people only. Deactivating, reactivating, blocking and
// unblocking write the user row and a timeline event that notifies nobody;
// none calls Auth0 (backend/admin/user_account_service.py,
// block_service.py), and the ops people have no applications, pairs or
// meetings for a block to sweep. Whether the person is then turned away
// (403 from every endpoint) is not checked here: that needs them signed in,
// and a test account must never be deactivated or blocked.
//
//   Ops Search      searched by name, address and alternative address
//   Ops Deactivate  deactivated and reactivated
//   Ops Block       blocked directly and unblocked

/** Fill the console's search box, run it, and wait for the answer. */
async function searchAccounts(page, term) {
  const loaded = page.waitForResponse(
    (r) =>
      r.request().method() === "GET" &&
      new URL(r.url()).pathname === "/api/admin/accounts" &&
      new URL(r.url()).searchParams.get("search") === term,
    { timeout: 15_000 },
  );
  await page.getByLabel("Search accounts").fill(term);
  await page.getByRole("button", { name: "Search", exact: true }).click();
  await loaded;
}

const accountRow = (page, userId) => page.getByTestId(`account-row-${userId}`);

test.describe("account console", { tag: "@accounts" }, () => {
  test("finds an account by name, address or alternative address and shows it in full", async ({
    as,
  }) => {
    const page = await as("admin");
    const id = opsId(page, "search");
    await page.goto("/admin/accounts");
    await expect(
      page.getByRole("heading", { level: 1, name: "Accounts" }),
    ).toBeVisible({
      timeout: 20_000,
    });
    await settle(page);
    for (const term of [
      "Ops Search",
      opsEmail(id),
      "e2e-ops-3-alt",
      "WANGYANPEI76+E2E-OPS-3-ALT@GMAIL.COM",
    ]) {
      await searchAccounts(page, term);
      await expect(accountRow(page, id), term).toBeVisible();
      await expect(page.locator("tbody tr"), term).toHaveCount(1);
    }
    const row = accountRow(page, id);
    await expect(row).toContainText(opsEmail(id));
    await expect(row).toContainText("External");
    await expect(row).toContainText("Active");

    await row.getByRole("button", { name: `Open account ${id}` }).click();
    await expect(
      page.getByRole("heading", { level: 1, name: opsName("search") }),
    ).toBeVisible();
    await expect(
      page.getByText(`${opsEmail(id)} · User ID ${id} · External`),
    ).toBeVisible();
    const methods = page.locator("section").filter({
      has: page.getByRole("heading", { name: "Sign-in methods" }),
    });
    await expect(methods).toContainText(
      `${opsEmail(id)} · Primary · Confirmed · never signed in`,
    );
    await expect(methods).toContainText(
      "wangyanpei76+e2e-ops-3-alt@gmail.com · Alternative · Confirmed · never signed in",
    );
    await expect(methods).toContainText("No linked identity");
    await expect(
      page.getByRole("button", { name: "Deactivate" }),
    ).toBeEnabled();
    await expect(
      page.getByRole("button", { name: "Block", exact: true }),
    ).toBeEnabled();
    await expect(
      page.getByRole("link", { name: "Manage permissions →" }),
    ).toHaveAttribute("href", `/admin/users?user_id=${id}`);

    // The back link (the sidebar has an "Accounts" link too) rings the row.
    await page.locator(`a[href*="focus=${id}"]`).click();
    await expect(accountRow(page, id)).toHaveAttribute("data-focused", "true");

    // Your own account cannot be deactivated or blocked from here.
    await openAccount(page, page.account.userId, /.+/);
    await expect(
      page.getByRole("button", { name: "Deactivate" }),
    ).toBeDisabled();
    await expect(
      page.getByRole("button", { name: "Block", exact: true }),
    ).toBeDisabled();
  });

  test("deactivating turns an account off without notifying anyone; reactivating restores it", async ({
    as,
  }) => {
    const page = await as("admin");
    const id = opsId(page, "deactivate");
    const since = lastEventId();
    await openAccount(page, id, opsName("deactivate"));
    await page.getByRole("button", { name: "Deactivate" }).click();
    const dialog = page.getByRole("dialog");
    await expect(
      dialog.getByRole("heading", {
        name: `Deactivate account — ${opsName("deactivate")}`,
      }),
    ).toBeVisible();
    await dialog.getByLabel(/^Note/).fill("e2e regression: asked to leave");
    await dialog.getByRole("button", { name: "Deactivate" }).click();
    await expect(successToast(page, "Account deactivated.")).toBeVisible();
    await expect(dialog).toBeHidden();
    const header = page
      .getByRole("heading", { level: 1, name: opsName("deactivate") })
      .locator("..");
    await expect(
      header.getByText("Deactivated", { exact: true }),
    ).toBeVisible();
    await expect(
      page.getByText("e2e regression: asked to leave"),
    ).toBeVisible();
    await expect(
      page.getByRole("button", { name: "Reactivate" }),
    ).toBeVisible();
    expect(userState(id)).toEqual({ active: false, blocked: false });
    const [[by]] = rowsOf(
      `SELECT deactivated_by FROM users WHERE user_id = ${id}`,
    );
    expect(Number(by)).toBe(page.account.userId);

    await page.goto("/admin/accounts");
    await page.getByLabel("Status").selectOption("deactivated");
    await page.getByLabel("Search by user id").fill(String(id));
    await page.getByRole("button", { name: "Search", exact: true }).click();
    await expect(accountRow(page, id)).toContainText("Deactivated");

    await openAccount(page, id, opsName("deactivate"));
    await page.getByRole("button", { name: "Reactivate" }).click();
    await expect(successToast(page, "Account reactivated.")).toBeVisible();
    await expect(header.getByText("Active", { exact: true })).toBeVisible();
    expect(userState(id)).toEqual({ active: true, blocked: false });
    expect(userEventRecipients(id, since)).toEqual([
      { type: "user.deactivated", to: [] },
      { type: "user.reactivated", to: [] },
    ]);
  });

  test("blocking directly takes a reason and notifies nobody; unblocking lifts it", async ({
    as,
  }) => {
    const page = await as("admin");
    needOps(page);
    const id = opsId(page, "block");
    const reason = `e2e regression block ${Date.now()}`;
    const since = lastEventId();
    await openAccount(page, id, opsName("block"));
    await page.getByRole("button", { name: "Block", exact: true }).click();
    const dialog = page.getByRole("dialog");
    await expect(
      dialog.getByRole("heading", {
        name: `Block account — ${opsName("block")}`,
      }),
    ).toBeVisible();
    const confirm = dialog.getByRole("button", { name: "Block", exact: true });
    await expect(confirm, "a reason is required").toBeDisabled();
    await dialog.getByLabel(/^Reason/).fill(reason);
    await confirm.click();
    await expect(successToast(page, "Account blocked.")).toBeVisible();
    const header = page
      .getByRole("heading", { level: 1, name: opsName("block") })
      .locator("..");
    await expect(header.getByText("Blocked", { exact: true })).toBeVisible();
    await expect(page.getByText(reason)).toBeVisible();
    expect(userState(id)).toEqual({ active: true, blocked: true });
    expect(
      rowsOf(
        `SELECT count(*) FROM user_identities WHERE user_id = ${id}`,
      )[0][0],
      "no Auth0 identity for a block to reach",
    ).toBe("0");

    // The Blocked filter also searches the block reason.
    await page.goto("/admin/accounts");
    await page.getByLabel("Status").selectOption("blocked");
    await searchAccounts(page, reason);
    await expect(accountRow(page, id)).toContainText("Blocked");
    await expect(page.locator("tbody tr")).toHaveCount(1);

    await openAccount(page, id, opsName("block"));
    await page.getByRole("button", { name: "Unblock" }).click();
    await expect(successToast(page, "Account unblocked.")).toBeVisible();
    await expect(header.getByText("Active", { exact: true })).toBeVisible();
    expect(userState(id)).toEqual({ active: true, blocked: false });
    expect(userEventRecipients(id, since)).toEqual([
      { type: "user.blocked", to: [] },
      { type: "user.unblocked", to: [] },
    ]);
  });
});
