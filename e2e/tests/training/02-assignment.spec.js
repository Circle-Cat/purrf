import { test, expect, settle } from "../../fixtures.js";
import { ENV } from "../../lib/env.js";
import { rowsOf } from "../../lib/seed.js";
import { successToast } from "../mentorship/helpers.js";
import {
  callApi,
  liveCourse,
  needTraining,
  openAdmin,
  trainingRow,
} from "./helpers.js";

// Assigning a published "E2E assign course …" from the Assign training card:
// one seed trainee by user id, then two more from a name search. The guard
// refuses assigning anyone else, and touching a real course at all.

/** Search the card, scoped to the course, and wait for the result. */
async function search(page, courseName, fill) {
  await page.getByLabel("Target course").selectOption({ label: courseName });
  await expect(page.getByLabel("On this course")).toHaveValue("not_assigned");
  await fill();
  const done = page.waitForResponse(
    (r) => new URL(r.url()).pathname === "/api/training/assignments/audience",
    { timeout: 30_000 },
  );
  await page.getByRole("button", { name: "Search", exact: true }).click();
  await done;
  await settle(page);
}

async function assignTicked(page, message) {
  const done = page.waitForResponse(
    (r) => new URL(r.url()).pathname === "/api/training/assignments/bulk",
  );
  await page.getByRole("button", { name: "Assign", exact: true }).click();
  const res = await done;
  expect(res.status()).toBe(200);
  await expect(successToast(page, message)).toBeVisible({ timeout: 15_000 });
  return (await res.json()).data;
}

test.describe.serial("training assignment", { tag: "@training" }, () => {
  let course;

  test("one seed trainee, found by user id", async ({ as }) => {
    test.setTimeout(120_000);
    const page = await as("admin");
    const { trainees } = needTraining(page);
    course = await liveCourse(page, "assign course");
    await openAdmin(page);

    await search(page, course.name, () =>
      page.getByLabel("User ID").fill(String(trainees[0])),
    );
    const row = page.getByTestId(`audience-row-${trainees[0]}`);
    await expect(row).toContainText("E2E Trainee 1");
    await expect(row).toContainText("Not assigned");
    await expect(page.locator('[data-testid^="audience-row-"]')).toHaveCount(1);
    await row.getByRole("checkbox", { name: "Select E2E Trainee 1" }).check();
    await expect(page.getByText("1 selected")).toBeVisible();
    const result = await assignTicked(page, "Assigned to 1 people.");
    expect(result).toMatchObject({
      createdCount: 1,
      alreadyAssignedCount: 0,
      attachedCount: 0,
    });

    expect(trainingRow(trainees[0], course.id)).toMatchObject({
      status: "to_do",
      category: "",
      link: "",
      completed: false,
    });
  });

  test("two more trainees from a name search; nobody else is touched", async ({
    as,
  }) => {
    const page = await as("admin");
    const { trainees } = needTraining(page);
    test.skip(!course, "needs the course from the first test");
    await openAdmin(page);

    await search(page, course.name, () =>
      page.getByLabel("Name or email").fill("e2e-trainee"),
    );
    const rows = page.locator('[data-testid^="audience-row-"]');
    await expect(rows).toHaveCount(3);
    await expect(page.getByTestId(`audience-row-${trainees[0]}`)).toHaveCount(
      0,
    );
    await page.getByRole("checkbox", { name: "Select E2E Trainee 2" }).check();
    await page.getByRole("checkbox", { name: "Select E2E Trainee 3" }).check();
    await expect(page.getByText("2 selected")).toBeVisible();
    const result = await assignTicked(
      page,
      "Assigned to 2 people. 0 already had this course.",
    );
    expect(result).toMatchObject({ createdCount: 2, alreadyAssignedCount: 0 });

    const holders = rowsOf(
      `SELECT user_id FROM training WHERE course_id = ${course.id} ORDER BY user_id`,
    ).map(([id]) => Number(id));
    expect(holders).toEqual(
      [page.account.userId, trainees[0], trainees[1], trainees[2]].sort(
        (a, b) => a - b,
      ),
    );
  });

  test("the guard refuses assigning a real person and writing to a real course", async ({
    as,
  }) => {
    const page = await as("admin");
    needTraining(page);
    test.skip(!course, "needs the course from the first test");
    await openAdmin(page);
    const [[stranger]] = rowsOf(`
      SELECT min(user_id) FROM users
      WHERE user_id < 990000 AND user_id NOT IN (${page.seed.testAccounts.join(",")})`);
    const [[realCourse]] = rowsOf(
      "SELECT min(course_id) FROM training_course WHERE category IS NOT NULL",
    );
    const before = rowsOf(
      `SELECT count(*) FROM training WHERE user_id = ${stranger}`,
    );

    page.expectBlocked(
      /POST \/api\/training\/assignments\/bulk: assigns users/,
    );
    page.expectBlocked(
      new RegExp(`/api/training/courses/${realCourse}/package: course`),
    );
    page.expectBlocked(
      new RegExp(`/api/training/courses/${realCourse}: course`),
    );
    const aborted = async (fn) =>
      expect(
        await fn().then(
          () => "sent",
          () => "aborted",
        ),
      ).toBe("aborted");
    await aborted(() =>
      callApi(page, "POST", "/api/training/assignments/bulk", {
        courseId: course.id,
        userIds: [Number(stranger)],
      }),
    );
    await aborted(() =>
      page.evaluate(async (url) => {
        const form = new FormData();
        form.append("file", new Blob(["x"]), "x.zip");
        await fetch(url, {
          method: "POST",
          credentials: "include",
          body: form,
        });
      }, `${ENV.api}/api/training/courses/${realCourse}/package`),
    );
    await aborted(() =>
      callApi(page, "PATCH", `/api/training/courses/${realCourse}`, {
        isActive: false,
      }),
    );
    expect(
      rowsOf(`SELECT count(*) FROM training WHERE user_id = ${stranger}`),
    ).toEqual(before);
  });
});
