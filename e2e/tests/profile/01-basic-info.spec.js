import { test, expect, expectNoErrorToast } from "../../fixtures.js";
import {
  callApi,
  editModal,
  field,
  loginAddress,
  needProfileSeed,
  openProfile,
  pickTimezone,
  profileCard,
  profileHeader,
  recordWrites,
  restoreAccountsAfterEach,
  storedProfile,
} from "./helpers.js";

// e2e-readonly edits its own name, preferred name, LinkedIn and timezone
// from the Profile page. The account has no name, and other layers assert
// that ("User 280"), so every test puts it back (restoreAccountsAfterEach).

restoreAccountsAfterEach();

async function openPersonalModal(page) {
  await page.getByRole("button", { name: "Edit Profile" }).click();
  const modal = editModal(page, "Edit Personal Information");
  await expect(modal).toBeVisible();
  return modal;
}

test.describe("basic information", { tag: "@profile" }, () => {
  test("edits name, preferred name, LinkedIn and timezone, and they survive a reload", async ({
    as,
  }) => {
    const page = await as("readonly");
    needProfileSeed(page);
    page.allowProfileWrites();
    const id = page.account.userId;
    const before = storedProfile(id);
    await openProfile(page);

    const modal = await openPersonalModal(page);
    await field(modal, "First Name").fill("E2E");
    await field(modal, "Last Name").fill("Profile Readonly");
    await field(modal, "Preferred Name").fill("Pro");
    await field(modal, "LinkedIn").fill(
      "https://www.linkedin.com/in/e2e-profile-readonly",
    );
    await pickTimezone(modal, "Tokyo", /Tokyo, Seoul/);
    const saved = page.waitForResponse(
      (r) =>
        r.request().method() === "PATCH" &&
        new URL(r.url()).pathname === "/api/profiles/me",
    );
    await modal.getByRole("button", { name: "Save" }).click();
    expect((await saved).status()).toBe(200);
    await expect(modal).toBeHidden();

    const check = async () => {
      await expect(profileHeader(page)).toContainText(
        "E2E (Pro) Profile Readonly",
      );
      await expect(profileHeader(page)).toContainText("Asia/Tokyo");
      await expect(
        profileCard(page, "LinkedIn link").getByRole("link", {
          name: "https://www.linkedin.com/in/e2e-profile-readonly",
        }),
      ).toHaveAttribute(
        "href",
        "https://www.linkedin.com/in/e2e-profile-readonly",
      );
    };
    await check();
    await openProfile(page);
    await check();

    const after = storedProfile(id);
    expect(after).toMatchObject({
      firstName: "E2E",
      lastName: "Profile Readonly",
      preferredName: "Pro",
      timezone: "Asia/Tokyo",
      linkedin: "https://www.linkedin.com/in/e2e-profile-readonly",
    });
    expect(Date.parse(after.timezoneUpdatedAt)).toBeGreaterThan(
      Date.parse(before.timezoneUpdatedAt),
    );
    await expectNoErrorToast(page);
  });

  test("first and last name are required, and nothing is sent until they are given", async ({
    as,
  }) => {
    const page = await as("readonly");
    needProfileSeed(page);
    page.allowProfileWrites();
    const before = storedProfile(page.account.userId);
    await openProfile(page);
    const writes = recordWrites(page);

    const modal = await openPersonalModal(page);
    await field(modal, "First Name").fill("   ");
    await field(modal, "Last Name").fill("");
    await field(modal, "Preferred Name").fill("Only Preferred");
    await modal.getByRole("button", { name: "Save" }).click();
    await expect(modal.getByText("First name is required")).toBeVisible();
    await expect(modal.getByText("Last name is required")).toBeVisible();
    await expect(modal.getByText("Timezone is required")).toHaveCount(0);

    // Typing clears that field's message only.
    await field(modal, "First Name").fill("E2E");
    await expect(modal.getByText("First name is required")).toHaveCount(0);
    await expect(modal.getByText("Last name is required")).toBeVisible();
    await modal.getByRole("button", { name: "Cancel" }).click();
    await expect(modal).toBeHidden();

    expect(writes).toEqual([]);
    expect(storedProfile(page.account.userId)).toEqual(before);
    await expect(profileHeader(page)).not.toContainText("Only Preferred");
  });

  test("a LinkedIn value that is not a web address is shown as text, not as a link", async ({
    as,
  }) => {
    const page = await as("readonly");
    needProfileSeed(page);
    page.allowProfileWrites();
    await openProfile(page);
    const modal = await openPersonalModal(page);
    await field(modal, "First Name").fill("E2E");
    await field(modal, "Last Name").fill("Profile Readonly");
    await field(modal, "LinkedIn").fill("javascript:alert(1)");
    await modal.getByRole("button", { name: "Save" }).click();
    await expect(modal).toBeHidden();

    const card = profileCard(page, "LinkedIn link");
    await expect(card.getByText("javascript:alert(1)")).toBeVisible();
    await expect(card.getByRole("link")).toHaveCount(0);
    expect(storedProfile(page.account.userId).linkedin).toBe(
      "javascript:alert(1)",
    );
  });

  test("the API refuses a timezone that is not an IANA name and changes nothing", async ({
    as,
  }) => {
    const page = await as("readonly");
    needProfileSeed(page);
    page.allowProfileWrites();
    const before = storedProfile(page.account.userId);
    await openProfile(page);
    page.expectApiError({
      method: "PATCH",
      path: /^\/api\/profiles\/me$/,
      status: 400,
    });
    const res = await callApi(page, "PATCH", "/api/profiles/me", {
      user: {
        firstName: "E2E",
        lastName: "Bad Timezone",
        timezone: "Mars/Olympus_Mons",
        communicationMethod: "email",
      },
    });
    expect(res.status).toBe(400);
    expect(res.json?.message).toContain("Invalid IANA timezone");
    expect(storedProfile(page.account.userId)).toEqual(before);
  });

  test("the Contact Email card shows the primary address and points to Sign in & security", async ({
    as,
  }) => {
    const page = await as("readonly");
    await openProfile(page);
    const card = profileCard(page, "Contact Email");
    await expect(card).toContainText(loginAddress("readonly"));
    const link = card.getByRole("link", { name: "Manage in Settings" });
    await expect(link).toHaveAttribute("href", "/settings/sign-in");
    await link.click();
    await expect(page).toHaveURL(/\/settings\/sign-in$/);
    await expect(page.getByText("Emails & sign-in methods")).toBeVisible();
  });

  test("an admitted mentee with an empty profile is asked to complete it", async ({
    as,
  }) => {
    const page = await as("member");
    needProfileSeed(page);
    await openProfile(page);
    const toast = page
      .locator("[data-sonner-toast]")
      .filter({ hasText: "Complete your profile" });
    await expect(toast).toBeVisible({ timeout: 15_000 });
    await expect(toast).toContainText(
      "Please fill in: Personal Information, Experience, Education.",
    );
    await toast.getByRole("button", { name: "Confirm" }).click();
    await expect(toast).toBeHidden();
    // Once per session.
    await openProfile(page);
    await expect(
      page
        .locator("[data-sonner-toast]")
        .filter({ hasText: "Complete your profile" }),
    ).toHaveCount(0);
  });
});
