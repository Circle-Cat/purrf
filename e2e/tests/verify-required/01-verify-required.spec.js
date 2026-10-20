import { test, expect, settle } from "../../fixtures.js";
import { ENV } from "../../lib/env.js";
import { askForCode, mailbox } from "../../lib/login.js";
import { readAccountState } from "../../lib/accounts.js";
import {
  SEED_USER_ID_FLOOR,
  databaseUrl,
  readSeedState,
} from "../../lib/seed.js";
import {
  callApi,
  errorToast,
  extraAlias,
  insertEmail,
  loginAddress,
  needProfileSeed,
  recordWrites,
  restoreAccountsAfterEach,
  rowsOf,
  storedEmails,
  successToast,
} from "../profile/helpers.js";

// The email verification wall (/verify-required) as e2e-member. No test
// account can really be unverified (SIDE-EFFECTS.md: flipping its sign-in
// row forks the account), so the browser is handed the real
// GET /api/permissions/me with only has_verified_email turned false; every
// call the wall makes goes to the real backend. Codes go only to
// <mailbox>+e2e-member-wall…@ aliases; the guard stops the sign-in address
// and company addresses.

restoreAccountsAfterEach();

const PERMISSIONS_ME = `${ENV.api}/api/permissions/me`;
const INITIATE = /^\/api\/auth\/emails\/initiate$/;
const VERIFY = /^\/api\/auth\/emails\/verify$/;

/**
 * Answer /permissions/me with the real body and has_verified_email false,
 * plus `extra` fields over it. Once a verify call has answered 200 the real
 * answer passes through, so refreshAuth() sees the account as it is.
 */
async function fakeUnverified(page, extra = {}) {
  let faking = true;
  page.on("response", (res) => {
    if (
      res.request().method() === "POST" &&
      VERIFY.test(new URL(res.url()).pathname) &&
      res.status() === 200
    )
      faking = false;
  });
  await page.route(PERMISSIONS_ME, async (route) => {
    if (!faking) return route.fallback();
    const res = await route.fetch();
    const json = await res.json();
    json.data = { ...json.data, ...extra, has_verified_email: false };
    return route.fulfill({ response: res, json });
  });
}

/** Answer /permissions/me with an error instead. */
async function failPermissions(page, status, message) {
  page.expectApiError({
    method: "GET",
    path: /^\/api\/permissions\/me$/,
    status,
  });
  await page.route(PERMISSIONS_ME, (route) =>
    route.fulfill({
      status,
      json: { success: false, message, data: null },
      headers: {
        "access-control-allow-origin": ENV.web,
        "access-control-allow-credentials": "true",
      },
    }),
  );
}

const wallTitle = (page) => page.getByText("Verify your email address");
const addressField = (page) => page.getByLabel("Email address");
const codeField = (page, address) =>
  page.getByLabel(`Enter the 6-digit code sent to ${address}`);
const button = (page, name) => page.getByRole("button", { name, exact: true });

/** Open a path as an unverified member and wait for the wall. */
async function openWall(page, path = "/verify-required") {
  await page.goto(path);
  await expect(wallTitle(page)).toBeVisible({ timeout: 20_000 });
  await expect(page).toHaveURL(/\/verify-required$/);
}

/** Type an address and press Send code; resolves to the initiate response. */
async function sendTo(page, address) {
  await addressField(page).fill(address);
  const answered = page.waitForResponse(
    (r) =>
      r.request().method() === "POST" &&
      INITIATE.test(new URL(r.url()).pathname),
    { timeout: 20_000 },
  );
  await button(page, "Send code").click();
  return answered;
}

/**
 * The member's address rows, how many accounts sit below the seed range,
 * and how many test-mailbox addresses sit on one of them that is not a
 * test account: a fork would change all three.
 */
function fingerprint() {
  const { testAccounts = [], profile } = readSeedState() ?? {};
  const memberId = readAccountState().member?.userId;
  const box = mailbox();
  if (!box) throw new Error("e2e.local.json names no mailbox");
  // The mailbox's local part as a LIKE prefix: quotes doubled, wildcards escaped.
  const prefix = box
    .split("@")[0]
    .replace(/'/g, "''")
    .replace(/[\\%_]/g, "\\$&");
  const [[users, strays]] = rowsOf(`
    SELECT (SELECT count(*) FROM users WHERE user_id < ${SEED_USER_ID_FLOOR}),
           (SELECT count(*) FROM user_emails
            WHERE email ILIKE '${prefix}%' AND user_id < ${SEED_USER_ID_FLOOR}
              ${testAccounts.length ? `AND user_id NOT IN (${testAccounts.join(",")})` : ""})`);
  return {
    member: profile && memberId ? storedEmails(memberId) : null,
    users: Number(users),
    strays: Number(strays),
  };
}

test.describe("email verification wall", { tag: "@verify" }, () => {
  let before = null;
  test.beforeAll(() => {
    if (databaseUrl()) before = fingerprint();
  });
  test.afterAll(() => {
    if (before)
      expect(
        fingerprint(),
        "the member as found, and no account forked",
      ).toEqual(before);
  });

  test(
    "a verified account opening /verify-required lands on its profile",
    { tag: "@smoke" },
    async ({ as }) => {
      const page = await as("member");
      await page.goto("/verify-required");
      await expect(page).toHaveURL(/\/profile$/, { timeout: 20_000 });
      await expect(
        page.getByRole("button", { name: "Edit Profile" }),
      ).toBeVisible({ timeout: 20_000 });
      await expect(wallTitle(page)).toHaveCount(0);
    },
  );

  test("an unverified account is held at the wall from any page; the header and sidebar stay and lead back to it", async ({
    as,
  }) => {
    const page = await as("member");
    await fakeUnverified(page);
    for (const path of ["/profile", "/dashboard/me", "/recruiting/jobs"]) {
      await openWall(page, path);
    }
    const header = page.getByRole("banner");
    await expect(header).toBeVisible();
    await expect(
      header.getByRole("button", { name: "User menu" }),
    ).toBeVisible();
    const sidebar = page.getByRole("link", {
      name: "Open Positions",
      exact: true,
    });
    await expect(sidebar).toBeVisible();
    await expect(sidebar).toHaveAttribute("href", "/recruiting/jobs");
    await expect(
      page.getByRole("link", { name: "Personal Dashboard", exact: true }),
    ).toBeVisible();

    // The page already sits on the wall, so the click has to be seen
    // reaching /recruiting/jobs before the gate sends it back.
    const visited = [];
    page.on("framenavigated", (frame) => {
      if (frame === page.mainFrame())
        visited.push(new URL(frame.url()).pathname);
    });
    await sidebar.click();
    await expect
      .poll(() => visited)
      .toEqual(
        expect.arrayContaining(["/recruiting/jobs", "/verify-required"]),
      );
    expect(visited.indexOf("/recruiting/jobs")).toBeLessThan(
      visited.lastIndexOf("/verify-required"),
    );
    await expect(page).toHaveURL(/\/verify-required$/);
    await expect(wallTitle(page)).toBeVisible();
    await expect(header).toBeVisible();
    await expect(sidebar).toBeVisible();
  });

  test("the wall asks for an address, prefilled with the sign-in one, and offers Log out; a company sign-in gets the Workspace copy", async ({
    as,
  }) => {
    const page = await as("member");
    await fakeUnverified(page);
    await openWall(page);
    const card = page
      .locator('[data-slot="card"]')
      .filter({ has: wallTitle(page) });
    await expect(card).toContainText(
      "Enter your email address to receive a verification code. This email will be used for sign-in and account notifications.",
    );
    await expect(addressField(page)).toHaveValue(loginAddress("member"));
    await expect(addressField(page)).toBeEditable();
    await expect(button(page, "Send code")).toBeEnabled();
    await expect(button(page, "Log out")).toBeVisible();
    await expect(page.getByText(/6-digit code/)).toHaveCount(0);

    // The copy keys off the address in /permissions/me alone; nothing is
    // sent to it here.
    const internal = await as("member");
    await fakeUnverified(internal, { email: "e2e-wall@circlecat.org" });
    const writes = recordWrites(internal);
    await openWall(internal);
    await expect(
      internal.getByText(
        "Please verify your Google Workspace email (@circlecat.org) to continue. If you don't receive the code, please contact your manager.",
      ),
    ).toBeVisible();
    await expect(addressField(internal)).toHaveValue("e2e-wall@circlecat.org");
    expect(writes).toEqual([]);
  });

  test("a 403, 401 or 400 from /permissions/me is never taken for the wall", async ({
    as,
  }) => {
    const cases = [
      [403, "Account deactivated.", "403 Forbidden", "Account deactivated."],
      [401, "Unauthorized", "Your session has expired", "Please log in again"],
      [
        400,
        "Sign-in with this connection is not allowed.",
        "Sign-in was refused",
        "Sign-in with this connection is not allowed.",
      ],
    ];
    for (const [status, message, title, body] of cases) {
      const page = await as("member");
      await failPermissions(page, status, message);
      await page.goto("/profile");
      await expect(page.getByText(title)).toBeVisible({ timeout: 20_000 });
      await expect(page.getByText(body).first()).toBeVisible();
      await settle(page);
      await expect(page).toHaveURL(/\/profile$/);
      await expect(wallTitle(page)).toHaveCount(0);
    }
  });

  test("an empty or malformed address is refused before any code is sent", async ({
    as,
  }) => {
    const page = await as("member");
    needProfileSeed(page);
    await fakeUnverified(page);
    await openWall(page);

    const writes = recordWrites(page);
    await addressField(page).fill("   ");
    await button(page, "Send code").click();
    await expect(
      errorToast(page, "Please enter your email address."),
    ).toBeVisible();
    expect(writes).toEqual([]);

    page.expectApiError({ method: "POST", path: INITIATE, status: 400 });
    const res = await sendTo(page, "not-an-email");
    expect(res.status()).toBe(400);
    await expect(
      errorToast(page, "Please enter a valid email address."),
    ).toBeVisible();
    await expect(button(page, "Send code")).toBeVisible();
    await expect(page.getByText(/6-digit code/)).toHaveCount(0);
  });

  test("an address another account has confirmed is refused with 409 before any code is sent", async ({
    as,
  }) => {
    const page = await as("member");
    needProfileSeed(page);
    const reviewerId = readAccountState().reviewer.userId;
    const taken = extraAlias("reviewer", "wall");
    insertEmail(reviewerId, taken, { confirmed: true });
    const mine = storedEmails(page.account.userId);
    await fakeUnverified(page);
    await openWall(page);

    page.expectApiError({ method: "POST", path: INITIATE, status: 409 });
    const res = await sendTo(page, taken);
    expect(res.status()).toBe(409);
    await expect(
      errorToast(
        page,
        "This email is already in use by another account. If it's yours, sign in with a code sent to that address instead.",
      ),
    ).toBeVisible();
    await expect(button(page, "Send code")).toBeVisible();
    expect(storedEmails(page.account.userId)).toEqual(mine);
    expect(storedEmails(reviewerId).find((e) => e.email === taken)).toEqual(
      expect.objectContaining({ confirmed: true }),
    );
  });

  test("the guard stops Send to the prefilled sign-in address and to a company address", async ({
    as,
  }) => {
    // What the server would do is not tried: a code would go to the
    // sign-in address, or to a company mailbox.
    const page = await as("member");
    needProfileSeed(page);
    await fakeUnverified(page);
    await openWall(page);
    const failed = errorToast(page, "Something went wrong. Please try again.");
    for (const address of [loginAddress("member"), "e2e-wall@circlecat.org"]) {
      // The previous round's toast has to be gone, or it would answer for
      // this one.
      await expect(failed).toHaveCount(0, { timeout: 15_000 });
      page.expectBlocked(/^blocked POST \/api\/auth\/emails\/initiate:/);
      await addressField(page).fill(address);
      await button(page, "Send code").click();
      await expect(failed).toBeVisible();
      await expect(button(page, "Send code")).toBeEnabled();
    }
  });

  test("a code goes to the typed alias; an empty or wrong code is refused, Resend sends again, Change email keeps the address", async ({
    as,
  }) => {
    const page = await as("member");
    needProfileSeed(page);
    const id = page.account.userId;
    const alias = extraAlias("member", "wall");
    const mine = storedEmails(id);
    await fakeUnverified(page);
    await openWall(page);

    expect((await sendTo(page, alias)).status()).toBe(200);
    await expect(
      successToast(page, `Verification code sent to ${alias}.`),
    ).toBeVisible();
    await expect(codeField(page, alias)).toBeVisible();
    await expect(addressField(page)).toHaveCount(0);

    const writes = recordWrites(page);
    await button(page, "Verify").click();
    await expect(
      errorToast(page, "Please enter the 6-digit verification code."),
    ).toBeVisible();
    expect(writes).toEqual([]);

    page.expectApiError({ method: "POST", path: VERIFY, status: 400 });
    await codeField(page, alias).fill("000000");
    const verified = page.waitForResponse(
      (r) =>
        r.request().method() === "POST" &&
        VERIFY.test(new URL(r.url()).pathname),
      { timeout: 20_000 },
    );
    await button(page, "Verify").click();
    expect((await verified).status()).toBe(400);
    await expect(
      errorToast(
        page,
        "Incorrect or expired verification code. Please request a new one.",
      ),
    ).toBeVisible();
    await expect(page).toHaveURL(/\/verify-required$/);
    await expect(codeField(page, alias)).toHaveValue("000000");
    expect(storedEmails(id)).toEqual(mine);

    // Resend's toast reads the same as the first; wait the first one out so
    // the one seen below is new.
    const sent = successToast(page, `Verification code sent to ${alias}.`);
    await expect(sent).toHaveCount(0, { timeout: 15_000 });
    const resent = page.waitForResponse(
      (r) =>
        r.request().method() === "POST" &&
        INITIATE.test(new URL(r.url()).pathname),
      { timeout: 20_000 },
    );
    await button(page, "Resend code").click();
    const again = await resent;
    expect(again.status()).toBe(200);
    expect(JSON.parse(again.request().postData())).toEqual({ email: alias });
    await expect(sent).toBeVisible();

    const quiet = recordWrites(page);
    await page.getByRole("button", { name: "Change email" }).click();
    await expect(addressField(page)).toHaveValue(alias);
    await expect(codeField(page, alias)).toHaveCount(0);
    expect(quiet).toEqual([]);
    expect(storedEmails(id)).toEqual(mine);
  });

  test("Log out heads to Auth0's logout, which the test stops", async ({
    as,
  }) => {
    // Letting it through would end the Access session the cached cookie
    // belongs to.
    const page = await as("member");
    await fakeUnverified(page);
    await page.route("**/v2/logout**", (route) => route.abort());
    await openWall(page);
    const leaving = page.waitForRequest(/\/v2\/logout/);
    await button(page, "Log out").click();
    const url = new URL((await leaving).url());
    expect(url.pathname).toBe("/v2/logout");
    expect(url.searchParams.get("client_id")).toBeTruthy();
    const returnTo = url.searchParams.get("returnTo");
    expect(returnTo).toMatch(/^https:\/\/[^/]+\/cdn-cgi\/access\/logout\?/);
    expect(new URL(returnTo).searchParams.get("returnTo")).toBe(
      `${ENV.web}/cdn-cgi/access/logout?returnTo=${encodeURIComponent(`${ENV.web}/`)}`,
    );
  });

  test("with a code from the inbox, the wall confirms the alias and goes to the profile", async ({
    as,
  }) => {
    test.skip(
      !process.env.E2E_EMAIL_OTP,
      "set E2E_EMAIL_OTP=1 and hand over the code in .state/codes/member-verify.txt",
    );
    test.setTimeout(8 * 60_000);
    const page = await as("member");
    needProfileSeed(page);
    const id = page.account.userId;
    const alias = extraAlias("member", "wall-otp");
    await fakeUnverified(page);
    await openWall(page);

    expect((await sendTo(page, alias)).status()).toBe(200);
    const code = await askForCode("member-verify", alias);
    await codeField(page, alias).fill(code);
    await button(page, "Verify").click();
    await expect(page).toHaveURL(/\/profile$/, { timeout: 20_000 });
    await expect(
      page.getByRole("button", { name: "Edit Profile" }),
    ).toBeVisible({ timeout: 20_000 });

    const added = storedEmails(id).find((e) => e.email === alias);
    expect(added).toMatchObject({ confirmed: true, primary: false });
    expect(storedEmails(id).find((e) => e.primary).email).toBe(
      loginAddress("member"),
    );
    const res = await callApi(
      page,
      "DELETE",
      `/api/auth/emails/${added.emailId}`,
    );
    expect(res.status).toBe(200);
    expect(storedEmails(id).map((e) => e.email)).toEqual([
      loginAddress("member"),
    ]);
  });
});
