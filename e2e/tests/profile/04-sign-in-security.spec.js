import { test, expect, expectNoErrorToast } from "../../fixtures.js";
import { askForCode } from "../../lib/login.js";
import {
  addressRow,
  callApi,
  errorToast,
  extraAlias,
  insertEmail,
  loginAddress,
  needProfileSeed,
  openSignIn,
  recordWrites,
  restoreAccountsAfterEach,
  rowsOf,
  storedEmails,
  successToast,
} from "./helpers.js";

// Sign in & security as e2e-member. The address it signs in with is never
// removed, replaced or demoted: every write here is about an extra alias
// (<mailbox>+e2e-member-<suffix>@…), added in the database or through Add
// email, and the guard refuses anything else. Codes Add email sends land in
// the test mailbox; only the E2E_EMAIL_OTP test reads one.

restoreAccountsAfterEach();

const dialog = (page, name) => page.getByRole("dialog", { name });

/** A user's sign-in identity ids, oldest first. */
const storedIdentities = (userId) =>
  rowsOf(`
    SELECT identity_id FROM user_identities
    WHERE user_id = ${Number(userId)} ORDER BY identity_id`).map(([id]) =>
    Number(id),
  );

test.describe("sign in and security", { tag: "@profile" }, () => {
  test("the sign-in address is the primary contact and the current session, and offers nothing to remove", async ({
    as,
  }) => {
    const page = await as("member");
    await openSignIn(page);
    const row = addressRow(page, loginAddress("member"));
    await expect(row).toHaveCount(1);
    await expect(
      row.getByText("Primary contact", { exact: true }),
    ).toBeVisible();
    await expect(
      row.getByText("Current session", { exact: true }),
    ).toBeVisible();
    await expect(row.getByText("Email OTP", { exact: true })).toBeVisible();
    await expect(row.getByText("Unverified")).toHaveCount(0);
    await expect(row.getByText("Internal", { exact: true })).toHaveCount(0);
    await expect(row.getByRole("button")).toHaveCount(0);
    await expectNoErrorToast(page);
  });

  test("a confirmed extra address can be removed; making it primary asks for a code sent to the current primary", async ({
    as,
  }) => {
    const page = await as("member");
    needProfileSeed(page);
    const id = page.account.userId;
    const alias = extraAlias("member", "extra");
    const emailId = insertEmail(id, alias, { confirmed: true });
    await openSignIn(page);

    const row = addressRow(page, alias);
    await expect(row.getByText("Email OTP", { exact: true })).toBeVisible();
    await expect(row.getByText("Primary contact", { exact: true })).toHaveCount(
      0,
    );
    await expect(row.getByText("Current session", { exact: true })).toHaveCount(
      0,
    );

    // Starting the switch mails a code to the sign-in address; closing the
    // dialog sends nothing more, and the primary stays.
    const started = page.waitForResponse(
      (r) =>
        new URL(r.url()).pathname ===
        `/api/auth/emails/${emailId}/primary/initiate`,
    );
    await row.getByRole("button", { name: "Make primary contact" }).click();
    expect((await started).status()).toBe(200);
    const confirm = dialog(page, "Change primary contact email");
    await expect(confirm).toBeVisible();
    await expect(confirm).toContainText(
      `To make ${alias} your primary contact email, enter the 6-digit code we sent to ${loginAddress("member")}.`,
    );
    const writes = recordWrites(page);
    await page.keyboard.press("Escape");
    await expect(confirm).toBeHidden();
    expect(writes).toEqual([]);
    expect(storedEmails(id).find((e) => e.primary).email).toBe(
      loginAddress("member"),
    );

    await row.getByRole("button", { name: "Remove email" }).click();
    await expect(successToast(page, "Email removed.")).toBeVisible();
    await expect(addressRow(page, alias)).toHaveCount(0);
    expect(storedEmails(id).map((e) => e.email)).toEqual([
      loginAddress("member"),
    ]);
  });

  test("an unverified address is badged, cannot be made primary, and can be removed", async ({
    as,
  }) => {
    const page = await as("member");
    needProfileSeed(page);
    const id = page.account.userId;
    const alias = extraAlias("member", "unverified");
    insertEmail(id, alias, { confirmed: false });
    await openSignIn(page);

    const row = addressRow(page, alias);
    await expect(row.getByText("Unverified", { exact: true })).toBeVisible();
    await expect(row).toContainText(
      `Verification required: Click "Add email" to re-add and verify this address.`,
    );
    await expect(row.getByText("Email OTP")).toHaveCount(0);
    await expect(
      row.getByRole("button", { name: "Make primary contact" }),
    ).toHaveCount(0);
    await row.getByRole("button", { name: "Remove email" }).click();
    await expect(successToast(page, "Email removed.")).toBeVisible();
    await expect(addressRow(page, alias)).toHaveCount(0);
    expect(storedEmails(id).map((e) => e.email)).toEqual([
      loginAddress("member"),
    ]);
  });

  test("Add email sends a code to the alias; a wrong code is refused and leaves nothing behind", async ({
    as,
  }) => {
    const page = await as("member");
    needProfileSeed(page);
    const id = page.account.userId;
    const alias = extraAlias("member", "extra");
    const before = storedEmails(id);
    await openSignIn(page);

    await page.getByRole("button", { name: "Add email" }).click();
    const add = dialog(page, "Add an email address");
    await add.getByLabel("Email address").fill(alias);
    await add.getByRole("button", { name: "Send code" }).click();
    await expect(
      successToast(page, `Verification code sent to ${alias}.`),
    ).toBeVisible({ timeout: 15_000 });
    await expect(
      add.getByLabel(`Enter the 6-digit code sent to ${alias}`),
    ).toBeVisible();

    page.expectApiError({
      method: "POST",
      path: /^\/api\/auth\/emails\/verify$/,
      status: 400,
    });
    await add
      .getByLabel(`Enter the 6-digit code sent to ${alias}`)
      .fill("000000");
    await add.getByRole("button", { name: "Verify" }).click();
    await expect(
      errorToast(
        page,
        "Incorrect or expired verification code. Please request a new one.",
      ),
    ).toBeVisible({ timeout: 15_000 });
    await expect(add).toBeVisible();

    // Change email goes back to the address step without sending anything.
    const writes = recordWrites(page);
    await add.getByRole("button", { name: "Change email" }).click();
    await expect(add.getByLabel("Email address")).toHaveValue(alias);
    await page.keyboard.press("Escape");
    await expect(add).toBeHidden();
    expect(writes).toEqual([]);
    await expect(addressRow(page, alias)).toHaveCount(0);
    expect(storedEmails(id)).toEqual(before);
  });

  test("an address another account holds is refused before any code is sent", async ({
    as,
  }) => {
    const page = await as("member");
    const people = needProfileSeed(page);
    const before = storedEmails(page.account.userId);
    await openSignIn(page);
    await page.getByRole("button", { name: "Add email" }).click();
    const add = dialog(page, "Add an email address");
    page.expectApiError({
      method: "POST",
      path: /^\/api\/auth\/emails\/initiate$/,
      status: 409,
    });
    await add.getByLabel("Email address").fill(people.owner.email);
    await add.getByRole("button", { name: "Send code" }).click();
    await expect(
      errorToast(page, "This email is already in use by another account."),
    ).toBeVisible({ timeout: 15_000 });
    await expect(add.getByRole("button", { name: "Send code" })).toBeVisible();
    await expect(add.getByLabel(/Enter the 6-digit code/)).toHaveCount(0);
    expect(storedEmails(page.account.userId)).toEqual(before);
  });

  test("the API refuses to remove an address of another account", async ({
    as,
  }) => {
    const page = await as("member");
    const people = needProfileSeed(page);
    await openSignIn(page);
    page.expectApiError({
      method: "DELETE",
      path: /^\/api\/auth\/emails\/\d+$/,
      status: 400,
    });
    const res = await callApi(
      page,
      "DELETE",
      `/api/auth/emails/${people["owner-old"].emailId}`,
    );
    expect(res.status).toBe(400);
    expect(res.json?.message).toBe("Email address not found.");
    expect(storedEmails(people.owner.userId).map((e) => e.email)).toContain(
      people["owner-old"].email,
    );
  });

  test("the guard stops removing or replacing the sign-in address", async ({
    as,
  }) => {
    // What the server would answer is not tried: a server bug would cost
    // the account its way in. This pins that the suite cannot send it.
    const page = await as("member");
    needProfileSeed(page);
    const id = page.account.userId;
    const primary = storedEmails(id).find((e) => e.primary);
    const extra = insertEmail(id, extraAlias("member", "extra"), {
      confirmed: true,
    });
    // An account that signs in by email code has no identity row; the guard
    // blocks by path, and 0 matches no identity should one slip through.
    const identities = storedIdentities(id);
    const identity = identities[0] ?? 0;
    await openSignIn(page);
    const attempts = [
      ["DELETE", `/api/auth/emails/${primary.emailId}`, undefined],
      // Unlinking a sign-in identity deletes its Auth0 user.
      ["POST", `/api/auth/identities/${identity}/unlink/initiate`, undefined],
      [
        "POST",
        `/api/auth/identities/${identity}/unlink/confirm`,
        { state: "x", code: "000000" },
      ],
      [
        "POST",
        `/api/auth/emails/${extra}/primary/confirm`,
        { state: "x", code: "000000" },
      ],
      [
        "POST",
        `/api/auth/emails/${primary.emailId}/primary/initiate`,
        undefined,
      ],
      [
        "POST",
        "/api/auth/emails/initiate",
        { email: loginAddress("reviewer") },
      ],
    ];
    for (const [method, path, body] of attempts) {
      page.expectBlocked(
        new RegExp(`^blocked ${method} ${path.replace(/[/]/g, "\\/")}:`),
      );
      const outcome = await callApi(page, method, path, body).catch(
        (e) => e.message,
      );
      expect(String(outcome)).toContain("Failed to fetch");
    }
    expect(storedEmails(id).find((e) => e.primary)).toEqual(primary);
    expect(storedIdentities(id)).toEqual(identities);
  });

  test("with a code from the inbox, Add email confirms the alias, and it can be removed", async ({
    as,
  }) => {
    test.skip(
      !process.env.E2E_EMAIL_OTP,
      "set E2E_EMAIL_OTP=1 and hand over the code in .state/codes/member-email.txt",
    );
    test.setTimeout(8 * 60_000);
    const page = await as("member");
    needProfileSeed(page);
    const id = page.account.userId;
    const alias = extraAlias("member", "otp");
    await openSignIn(page);

    await page.getByRole("button", { name: "Add email" }).click();
    const add = dialog(page, "Add an email address");
    await add.getByLabel("Email address").fill(alias);
    await add.getByRole("button", { name: "Send code" }).click();
    await expect(
      successToast(page, `Verification code sent to ${alias}.`),
    ).toBeVisible({ timeout: 15_000 });
    const code = await askForCode("member-email", alias);
    await add.getByLabel(`Enter the 6-digit code sent to ${alias}`).fill(code);
    await add.getByRole("button", { name: "Verify" }).click();
    await expect(
      successToast(page, "Email address successfully added."),
    ).toBeVisible({ timeout: 20_000 });
    await expect(add).toBeHidden();

    const row = addressRow(page, alias);
    await expect(row.getByText("Email OTP", { exact: true })).toBeVisible();
    await expect(row.getByText("Primary contact", { exact: true })).toHaveCount(
      0,
    );
    expect(storedEmails(id).find((e) => e.email === alias)).toMatchObject({
      confirmed: true,
      primary: false,
    });

    await row.getByRole("button", { name: "Remove email" }).click();
    await expect(successToast(page, "Email removed.")).toBeVisible();
    await expect(addressRow(page, alias)).toHaveCount(0);
    expect(storedEmails(id).map((e) => e.email)).toEqual([
      loginAddress("member"),
    ]);
  });
});
