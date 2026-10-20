import { test, expect, settle } from "../../fixtures.js";
import { rowsOf } from "../../lib/seed.js";
import {
  callApi,
  card,
  lane,
  openBoard,
  seedJob,
  successToast,
} from "./helpers.js";

// e2e-member applies to two seeded postings, both owned by e2e-admin:
//   open posting      answers both questions and lands in Recruiter screening
//   screened posting  answers "No", which the posting's screen rule rejects
// Profile write-back is declined, so the member's profile is left alone.

/** Open a posting as the member from Open Positions. */
async function openFromBrowse(member, title) {
  await member.goto("/recruiting/jobs");
  await expect(
    member.getByRole("heading", { name: "Open Positions" }),
  ).toBeVisible({
    timeout: 20_000,
  });
  const tile = member.getByRole("button").filter({ hasText: title });
  await expect(tile).toHaveCount(1, { timeout: 20_000 });
  await tile.click();
  await expect(
    member.getByRole("heading", { level: 1, name: title }),
  ).toBeVisible({
    timeout: 20_000,
  });
  await settle(member);
}

/** Fill whatever of the Personal block is empty, then submit. */
async function submitApplication(member) {
  for (const [label, value] of [
    ["First name *", "E2E"],
    ["Last name *", "Member"],
  ]) {
    const box = member.getByRole("textbox", { name: label });
    if ((await box.count()) && !(await box.inputValue())) await box.fill(value);
  }
  await member.getByRole("button", { name: "Submit application" }).click();
  // The form asks about profile write-back only when the member changed their
  // information while applying; otherwise it sends straight away.
  const ask = member
    .getByRole("dialog")
    .filter({ hasText: "Update your profile?" });
  const submitted = successToast(member, "Application submitted.");
  await expect(ask.or(submitted)).toBeVisible({ timeout: 20_000 });
  if (await ask.isVisible()) {
    await ask.getByRole("button", { name: "Don't update" }).click();
  }
  await expect(submitted).toBeVisible({ timeout: 20_000 });
  await expect(member).toHaveURL(/\/dashboard\/me$/);
}

test.describe("member applies", { tag: "@recruiting" }, () => {
  test("the member applies to an open posting, sees it as applied, and the recruiter sees the card", async ({
    as,
  }) => {
    test.setTimeout(120_000);
    const admin = await as("admin");
    const member = await as("member");
    const job = seedJob(member, "open");

    await openFromBrowse(member, job.title);
    await expect(
      member.getByText("E2E regression posting: e2e-member applies here."),
    ).toBeVisible();
    await member.getByRole("button", { name: "Apply", exact: true }).click();
    await expect(member).toHaveURL(
      new RegExp(`/recruiting/jobs/${job.id}/apply$`),
    );

    // Required questions are checked before anything is sent.
    await member.getByRole("button", { name: "Submit application" }).click();
    await expect(
      member.locator('[data-sonner-toast][data-type="error"]'),
    ).toContainText(/highlighted field/);
    await member
      .getByRole("radiogroup", {
        name: "E2E question: can you commit ten hours a week?",
      })
      .getByRole("radio", { name: "Yes" })
      .check();
    await member
      .getByRole("textbox", { name: "E2E question: why this posting?" })
      .fill("E2E regression answer");
    await submitApplication(member);

    await member.goto(`/recruiting/jobs/${job.id}`);
    const again = member.getByRole("button", {
      name: /^(Continue application|View your application)$/,
    });
    await expect(
      again,
      "an applied member is not offered Apply again",
    ).toBeVisible({
      timeout: 20_000,
    });
    const editable = (await again.textContent()) === "Continue application";
    await again.click();
    await expect(member).toHaveURL(
      new RegExp(`/recruiting/jobs/${job.id}/application$`),
    );
    if (editable) {
      await expect(
        member.getByRole("textbox", {
          name: "E2E question: why this posting?",
        }),
        "the submitted answer is loaded back for editing",
      ).toHaveValue("E2E regression answer", { timeout: 20_000 });
    } else {
      await expect(member.getByText("E2E regression answer")).toBeVisible({
        timeout: 20_000,
      });
    }

    const mine = await callApi(
      member,
      "GET",
      "/api/recruiting/my-applications",
    );
    expect(mine.status).toBe(200);
    expect(JSON.stringify(mine.json.data)).toContain(job.title);

    // A second application to the same posting is refused.
    member.expectApiError({
      method: "POST",
      path: /^\/api\/recruiting\/applications$/,
      status: 400,
    });
    const twice = await callApi(
      member,
      "POST",
      "/api/recruiting/applications",
      {
        jobId: job.id,
        personal: {
          firstName: "E2E",
          lastName: "Member",
          timezone: "UTC",
          linkedin: "",
        },
        education: [],
        experience: [],
        answers: { q1: "Yes", q2: "again" },
      },
    );
    expect(twice.status, JSON.stringify(twice.json)).toBe(400);
    expect(twice.json?.message).toBe(
      "you already have an application for this job; edit it instead",
    );

    const applied = (mine.json.data.applications ?? []).find(
      (a) => a.jobId === job.id,
    );
    expect(applied, "the member's own list has the application").toBeTruthy();
    expect(applied.stage).toBe("recruiter_screening");
    await openBoard(admin, job.id);
    const theirs = lane(admin, "recruiter_screening").locator(
      "[data-application-id]",
    );
    await expect(theirs).toHaveCount(1);
    await expect(theirs).toHaveAttribute(
      "data-application-id",
      String(applied.applicationId),
    );
    // PUR-788: an applicant is named by their account's legal name, else by
    // the name typed into their latest application.
    const [named] = rowsOf(
      `SELECT trim(concat_ws(' ', first_name, last_name)) FROM users
       WHERE user_id = ${member.account.userId}`,
    );
    await expect(theirs.locator("p").first()).toHaveText(
      named?.[0] || "E2E Member",
    );
  });

  test("an answer the screen rule rejects lands the application in Rejected", async ({
    as,
  }) => {
    test.setTimeout(120_000);
    const admin = await as("admin");
    const member = await as("member");
    const job = seedJob(member, "screened");

    await openFromBrowse(member, job.title);
    await member.getByRole("button", { name: "Apply", exact: true }).click();
    await member
      .getByRole("radiogroup", {
        name: "E2E question: do you accept the program rules?",
      })
      .getByRole("radio", { name: "No" })
      .check();
    await submitApplication(member);

    const mine = await callApi(
      member,
      "GET",
      `/api/recruiting/applications/mine?job_id=${job.id}`,
    );
    expect(mine.status).toBe(200);
    expect(mine.json.data.stage).toBe("rejected");

    await openBoard(admin, job.id);
    const rejected = lane(admin, "rejected");
    await expect(card(rejected, mine.json.data.id)).toHaveCount(1);
    await expect(
      lane(admin, "recruiter_screening").locator("[data-application-id]"),
    ).toHaveCount(0);
  });
});
