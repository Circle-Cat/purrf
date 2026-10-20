import { test, expect } from "../../fixtures.js";
import { rowsOf } from "../../lib/seed.js";
import {
  assign,
  expectCourseLoaded,
  liveCourse,
  needTraining,
  nextSave,
  profileRow,
  progressRow,
  publishPackage,
  trainingRow,
} from "./helpers.js";

// e2e-member taking courses the spec publishes and assigns to it: start from
// the profile, leave on page 2, resume where it left off, finish. Package A
// reports "completed"; package B, published over A while the member is part
// way through, reports "passed" and starts from the beginning. The member's
// own mentee onboarding row is read before and after and must not move.

const REPLACED = {
  method: "POST",
  path: /^\/api\/training\/\d+\/progress$/,
  status: 409,
};

/** e2e-member's mentorship onboarding rows (those carry a category). */
const onboardingRows = (userId) =>
  rowsOf(`
    SELECT training_id, category, status, course_id FROM training
    WHERE user_id = ${userId} AND category IS NOT NULL ORDER BY 1`);

/** Wait until a save answers with the assignment's status. */
const saveWithStatus = (page, trainingId, status) =>
  page.waitForResponse(
    async (r) =>
      r.request().method() === "POST" &&
      new URL(r.url()).pathname === `/api/training/${trainingId}/progress` &&
      r.status() === 200 &&
      (await r.json().catch(() => null))?.data?.status === status,
    { timeout: 30_000 },
  );

test.describe("training as a learner", { tag: "@training" }, () => {
  test("package A: start, leave on page 2, resume there, finish as completed", async ({
    as,
  }) => {
    test.setTimeout(180_000);
    const admin = await as("admin");
    needTraining(admin);
    const member = await as("member");
    const memberId = member.account.userId;
    const onboarding = onboardingRows(memberId);
    const course = await liveCourse(admin, "learner course");
    await assign(admin, course.id, [memberId]);
    const assigned = trainingRow(memberId, course.id);
    expect(assigned).toMatchObject({ status: "to_do", category: "", link: "" });

    let row = await profileRow(member, course.name);
    await expect(row).toContainText("Not Started");
    await row.getByRole("link", { name: "Start" }).click();
    await expect(member).toHaveURL(new RegExp(`/training/${assigned.id}$`));
    let frame = await expectCourseLoaded(member, "AAAAaaaa");
    await expect(frame.locator("#entry")).toHaveText("ab-initio");
    await expect(frame.locator("#location")).toHaveText("(empty)");
    const saved = saveWithStatus(member, assigned.id, "in_progress");
    await frame.locator("#next").click();
    await saved;
    expect(progressRow(assigned.id)).toMatchObject({
      lessonStatus: "incomplete",
      lessonLocation: "page-2",
      suspendLength: 19,
    });

    row = await profileRow(member, course.name);
    await expect(row).toContainText("In Progress");
    await row.getByRole("link", { name: "Continue" }).click();
    frame = await expectCourseLoaded(member, "AAAAaaaa");
    await expect(frame.locator("#entry")).toHaveText("resume");
    await expect(frame.locator("#location")).toHaveText("page-2");
    await expect(frame.locator("#page")).toHaveText("2");
    await expect(frame.locator("#suspend")).toHaveText("19");
    await expect(frame.locator("#status")).toHaveText("incomplete");

    const done = saveWithStatus(member, assigned.id, "done");
    await frame.locator("#finish").click();
    await done;
    expect(trainingRow(memberId, course.id)).toMatchObject({
      status: "done",
      completed: true,
    });

    row = await profileRow(member, course.name);
    await expect(row).toContainText("Completed");
    await expect(row.getByRole("link", { name: "Review" })).toBeVisible();
    expect(
      onboardingRows(memberId),
      "the mentee onboarding row is untouched",
    ).toEqual(onboarding);
  });

  test("package B replaces A mid-course: the open tab stops saving, reopening starts over and finishes as passed", async ({
    as,
  }) => {
    test.setTimeout(240_000);
    const admin = await as("admin");
    needTraining(admin);
    const member = await as("member");
    const memberId = member.account.userId;
    const onboarding = onboardingRows(memberId);
    const course = await liveCourse(admin, "replace course");
    await assign(admin, course.id, [memberId]);
    const assigned = trainingRow(memberId, course.id);

    const row = await profileRow(member, course.name);
    await row.getByRole("link", { name: "Start" }).click();
    let frame = await expectCourseLoaded(member, "AAAAaaaa");
    const saved = nextSave(member, assigned.id);
    await frame.locator("#next").click();
    expect((await saved).status()).toBe(200);
    expect(progressRow(assigned.id)).toMatchObject({
      lessonLocation: "page-2",
    });

    const published = await publishPackage(admin, course.id, "b");
    expect(published).toMatchObject({ packageVersion: "BBBBbbbb" });
    expect(published.learnersReset).toBeGreaterThanOrEqual(1);
    expect(progressRow(assigned.id)).toMatchObject({
      lessonStatus: "",
      lessonLocation: "",
      suspendLength: 0,
    });
    expect(trainingRow(memberId, course.id)).toMatchObject({
      status: "in_progress",
    });

    member.expectApiError(REPLACED);
    const refused = nextSave(member, assigned.id);
    await frame.locator("#finish").click();
    expect((await refused).status()).toBe(409);
    await expect(
      member.getByText(
        "This course was updated while this page was open. Reload the page to continue; this page cannot save any more.",
      ),
    ).toBeVisible();
    expect(
      trainingRow(memberId, course.id),
      "the stale tab's finish is not stored",
    ).toMatchObject({
      status: "in_progress",
    });

    const reopened = await profileRow(member, course.name);
    await expect(reopened).toContainText("In Progress");
    await reopened.getByRole("link", { name: "Continue" }).click();
    frame = await expectCourseLoaded(member, "BBBBbbbb");
    await expect(frame.locator("h1")).toHaveText("E2E course BBBBbbbb");
    await expect(frame.locator("#entry")).toHaveText("ab-initio");
    await expect(frame.locator("#location")).toHaveText("(empty)");
    await expect(frame.locator("#suspend")).toHaveText("0");

    const done = saveWithStatus(member, assigned.id, "done");
    await frame.locator("#finish").click();
    await done;
    expect(progressRow(assigned.id)).toMatchObject({ lessonStatus: "passed" });
    expect(trainingRow(memberId, course.id)).toMatchObject({
      status: "done",
      completed: true,
    });
    await expect(
      (await profileRow(member, course.name)).getByText("Completed"),
    ).toBeVisible();
    expect(
      onboardingRows(memberId),
      "the mentee onboarding row is untouched",
    ).toEqual(onboarding);
  });
});
