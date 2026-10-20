import { test, expect } from "../../fixtures.js";
import {
  assign,
  callApi,
  createCourse,
  liveCourse,
  needTraining,
  trainingRow,
  uploadPackage,
} from "./helpers.js";

// Accounts without training.admin.* (e2e-readonly, e2e-member) see no
// training administration and are refused every admin write on a suite
// course; a learner cannot open or save someone else's assignment.

async function refused(page, method, path, body) {
  const re = new RegExp(`^${path.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}$`);
  page.expectApiError({ method, path: re, status: 403 });
  const res = await callApi(page, method, path, body);
  expect(
    res.status,
    `${method} ${path} -> ${res.status} ${JSON.stringify(res.json)}`,
  ).toBe(403);
}

test.describe("training permissions", { tag: "@training" }, () => {
  let course;
  let traineeTraining;

  for (const role of ["readonly", "member"]) {
    test(`${role} sees no training administration and cannot write it`, async ({
      as,
    }) => {
      test.setTimeout(120_000);
      const admin = await as("admin");
      const { trainees } = needTraining(admin);
      if (!course) {
        course = await liveCourse(admin, "permission course");
        await assign(admin, course.id, [trainees[3]]);
        traineeTraining = trainingRow(trainees[3], course.id).id;
      }
      const page = await as(role);
      await page.goto("/dashboard/me");
      await expect(
        page.getByRole("link", { name: "Personal Dashboard" }),
      ).toBeVisible({
        timeout: 20_000,
      });
      await expect(
        page.getByRole("link", { name: "Training Administration" }),
      ).toHaveCount(0);
      for (const path of [
        "/admin/training",
        `/admin/training/${course.id}/trial`,
        `/admin/training/${course.id}/preview`,
      ]) {
        await page.goto(path);
        await expect(page).toHaveURL(/\/access-denied$/, { timeout: 20_000 });
      }

      await refused(page, "GET", "/api/training/courses");
      await refused(page, "POST", "/api/training/courses", {
        name: "E2E permission probe",
      });
      await refused(page, "PATCH", `/api/training/courses/${course.id}`, {
        isActive: false,
      });
      await refused(page, "POST", `/api/training/courses/${course.id}/trial`);
      await refused(
        page,
        "POST",
        `/api/training/courses/${course.id}/package/publish`,
      );
      await refused(
        page,
        "DELETE",
        `/api/training/courses/${course.id}/package`,
      );
      await refused(
        page,
        "POST",
        `/api/training/courses/${course.id}/preview-session`,
      );
      await refused(page, "POST", "/api/training/assignments/bulk", {
        courseId: course.id,
        userIds: [page.account.userId],
      });
      page.expectApiError({
        method: "POST",
        path: new RegExp(`^/api/training/courses/${course.id}/package$`),
        status: 403,
      });
      expect((await uploadPackage(page, course.id, "b")).status).toBe(403);

      await refused(page, "POST", `/api/training/${traineeTraining}/session`);
      await refused(page, "POST", `/api/training/${traineeTraining}/progress`, {
        cmi: { "cmi.core.lesson_status": "completed" },
      });
      expect(trainingRow(trainees[3], course.id)).toMatchObject({
        status: "to_do",
      });
      expect(trainingRow(page.account.userId, course.id)).toBeNull();
    });
  }

  test("the course page of someone else's assignment does not open", async ({
    as,
  }) => {
    const member = await as("member");
    needTraining(member);
    test.skip(!traineeTraining, "needs the course from the tests above");
    member.expectApiError({
      method: "POST",
      path: new RegExp(`^/api/training/${traineeTraining}/session$`),
      status: 403,
    });
    await member.goto(`/training/${traineeTraining}`);
    await expect(member.getByText("This course is not available.")).toBeVisible(
      {
        timeout: 20_000,
      },
    );
    await expect(member.locator('iframe[title="Course"]')).toHaveCount(0);
  });

  test("an admin cannot start a trial of a course with nothing staged", async ({
    as,
  }) => {
    const admin = await as("admin");
    needTraining(admin);
    await admin.goto("/dashboard/me");
    const empty = await createCourse(admin, "empty course");
    admin.expectApiError({
      method: "POST",
      path: new RegExp(
        `^/api/training/courses/${empty.id}/(trial|package/publish)$`,
      ),
      status: 409,
    });
    const trial = await callApi(
      admin,
      "POST",
      `/api/training/courses/${empty.id}/trial`,
    );
    expect(trial.status).toBe(409);
    const pub = await callApi(
      admin,
      "POST",
      `/api/training/courses/${empty.id}/package/publish`,
    );
    expect(pub.status).toBe(409);
  });
});
