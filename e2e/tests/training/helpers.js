import fs from "node:fs";
import { test, expect, settle } from "../../fixtures.js";
import { callApi } from "../mentorship/helpers.js";
import { ENV } from "../../lib/env.js";
import { rowsOf } from "../../lib/seed.js";
import {
  FIXTURE_DIR,
  PACKAGES,
  writeFixtures,
} from "../../lib/scorm-fixtures.js";

export { callApi };
export { PACKAGES };

/**
 * Shared steps for the training specs. Every course they touch is one they
 * create, named "E2E …"; locators come from the English copy in
 * frontend/src/pages/AdminTraining, TrainingTrial, TrainingCourse and the
 * profile's TrainingSection.
 */

/** Skip a write test when global setup did not seed the trainees. */
export function needTraining(page) {
  test.skip(
    !page.seed?.training,
    "not seeded (needs E2E_DATABASE_URL and the admin and member tokens, on test)",
  );
  return page.seed.training;
}

/** Paths of the fixture zips: a, b, damaged, notZip. */
export function packageFile(name) {
  const files = {
    a: "package-a.zip",
    b: "package-b.zip",
    damaged: "package-damaged.zip",
    notZip: "not-a-package.zip",
  };
  const file = `${FIXTURE_DIR}/${files[name]}`;
  if (!fs.existsSync(file)) writeFixtures();
  return file;
}

const stamp = () => new Date().toISOString().slice(5, 19).replace(/\D/g, "");

/** Create an "E2E …" course through the API (there is no UI for it). */
export async function createCourse(page, label) {
  const name = `E2E ${label} ${stamp()}`;
  const res = await callApi(page, "POST", "/api/training/courses", {
    name,
    description: "Created by the e2e suite",
  });
  expect(res.status, JSON.stringify(res.json)).toBe(201);
  return { id: res.json.data.courseId, name };
}

/** Upload a fixture zip to a course from inside the page, as the dialog does. */
export async function uploadPackage(page, courseId, name) {
  const base64 = fs.readFileSync(packageFile(name)).toString("base64");
  return page.evaluate(
    async ({ url, base64 }) => {
      const bytes = Uint8Array.from(atob(base64), (c) => c.charCodeAt(0));
      const form = new FormData();
      form.append(
        "file",
        new Blob([bytes], { type: "application/zip" }),
        "package.zip",
      );
      const res = await fetch(url, {
        method: "POST",
        credentials: "include",
        body: form,
      });
      return { status: res.status, json: await res.json().catch(() => null) };
    },
    { url: `${ENV.api}/api/training/courses/${courseId}/package`, base64 },
  );
}

/**
 * Verify the staged package the way a trial run does: open the caller's
 * trial assignment, open a trial session on it, and report completion with
 * that session's token.
 */
export async function verifyStaged(page, courseId, finish = "completed") {
  const trial = await callApi(
    page,
    "POST",
    `/api/training/courses/${courseId}/trial`,
  );
  expect([200, 201], JSON.stringify(trial.json)).toContain(trial.status);
  const trainingId = trial.json.data.trainingId;
  const session = await callApi(
    page,
    "POST",
    `/api/training/${trainingId}/trial-session`,
  );
  expect(session.status, JSON.stringify(session.json)).toBe(200);
  const saved = await callApi(
    page,
    "POST",
    `/api/training/${trainingId}/progress`,
    {
      cmi: { "cmi.core.lesson_status": finish },
      sessionToken: session.json.data.sessionToken,
    },
  );
  expect(saved.status, JSON.stringify(saved.json)).toBe(200);
  expect(saved.json.data.courseVerified).toBe(true);
}

export async function publish(page, courseId) {
  const res = await callApi(
    page,
    "POST",
    `/api/training/courses/${courseId}/package/publish`,
  );
  expect(res.status, JSON.stringify(res.json)).toBe(200);
  return res.json.data;
}

/** Upload, verify and publish a fixture package, all through the API. */
export async function publishPackage(page, courseId, name) {
  const up = await uploadPackage(page, courseId, name);
  expect(up.status, JSON.stringify(up.json)).toBe(201);
  await verifyStaged(page, courseId, PACKAGES[name].finish);
  return publish(page, courseId);
}

/** A new suite course with a fixture package live on it. */
export async function liveCourse(page, label, name = "a") {
  await page.goto("/admin/training");
  const course = await createCourse(page, label);
  await publishPackage(page, course.id, name);
  return course;
}

export async function assign(page, courseId, userIds) {
  const res = await callApi(page, "POST", "/api/training/assignments/bulk", {
    courseId,
    userIds,
  });
  expect(res.status, JSON.stringify(res.json)).toBe(200);
  return res.json.data;
}

/** One assignment row from the database, or null. */
export function trainingRow(userId, courseId) {
  const [row] = rowsOf(`
    SELECT training_id, status, COALESCE(category::text, ''), COALESCE(link, ''),
           completed_timestamp IS NOT NULL
    FROM training WHERE user_id = ${Number(userId)} AND course_id = ${Number(courseId)}`);
  if (!row) return null;
  const [id, status, category, link, completed] = row;
  return {
    id: Number(id),
    status,
    category,
    link,
    completed: completed === "t",
  };
}

/** The stored progress row of an assignment, or null. */
export function progressRow(trainingId) {
  const [row] = rowsOf(`
    SELECT training_id, COALESCE(lesson_status, ''), COALESCE(lesson_location, ''),
           length(COALESCE(suspend_data, ''))
    FROM training_progress WHERE training_id = ${Number(trainingId)}`);
  if (!row) return null;
  return {
    lessonStatus: row[1],
    lessonLocation: row[2],
    suspendLength: Number(row[3]),
  };
}

/** Open the Training Administration page and wait for the course table. */
export async function openAdmin(page) {
  await page.goto("/admin/training");
  await expect(
    page.getByRole("heading", { name: "Training courses" }),
  ).toBeVisible({
    timeout: 20_000,
  });
  await expect(
    page.getByRole("cell", { name: "Course", exact: true }),
  ).toBeVisible({
    timeout: 20_000,
  });
  await settle(page);
}

/** A course's row in the catalogue, by its exact name. */
export const courseRow = (page, name) =>
  page.getByRole("row").filter({ has: page.getByText(name, { exact: true }) });

/** The staged sub-row directly under a course's row. */
export const stagedRow = (page, name) =>
  courseRow(page, name).locator("xpath=following-sibling::tr[1]");

/** The course itself: two frames down, on the content origin. */
export const courseFrame = (page) =>
  page.frameLocator('iframe[title="Course"]').frameLocator("iframe");

/** Wait for the course page to print what the player handed it. */
export async function expectCourseLoaded(page, version) {
  const frame = courseFrame(page);
  await expect(frame.locator("#version")).toHaveText(version, {
    timeout: 45_000,
  });
  await expect(frame.locator("#api")).toHaveText("true", { timeout: 15_000 });
  return frame;
}

/** Resolves with the next progress save's response. */
export const nextSave = (page, trainingId) =>
  page.waitForResponse(
    (r) =>
      r.request().method() === "POST" &&
      new URL(r.url()).pathname === `/api/training/${trainingId}/progress`,
    { timeout: 30_000 },
  );

/** The learner's row for a course in the profile's Training table. */
export async function profileRow(page, courseName) {
  await page.goto("/profile");
  const row = page.locator("tr").filter({ hasText: courseName });
  await expect(row).toBeVisible({ timeout: 30_000 });
  return row;
}
