import { test, expect, settle } from "../../fixtures.js";
import {
  callApi,
  courseFrame,
  courseRow,
  createCourse,
  expectCourseLoaded,
  needTraining,
  openAdmin,
  packageFile,
  stagedRow,
  trainingRow,
  progressRow,
} from "./helpers.js";
import { rowsOf } from "../../lib/seed.js";

// A course's whole life in the Training Administration console, on one
// course the spec creates ("E2E admin course …"): rejected uploads, package A
// staged, tried, published and previewed, package B staged and discarded,
// then staged again, tried and published over A, and the course turned off.

const UPLOAD = {
  method: "POST",
  path: /^\/api\/training\/courses\/\d+\/package$/,
  status: 400,
};

async function openUpload(page, name, title) {
  await courseRow(page, name).getByRole("button", { name: title }).click();
  const dialog = page.getByRole("dialog");
  await expect(dialog.getByRole("heading", { name: title })).toBeVisible();
  return dialog;
}

async function upload(page, name, title, file) {
  const dialog = await openUpload(page, name, title);
  await dialog
    .getByLabel("SCORM package (.zip)")
    .setInputFiles(packageFile(file));
  const done = page.waitForResponse(
    (r) =>
      r.request().method() === "POST" &&
      /\/package$/.test(new URL(r.url()).pathname),
    { timeout: 60_000 },
  );
  await dialog.getByRole("button", { name: title }).click();
  return { dialog, response: await done };
}

/** Run the staged package on the trial page to the finish. */
async function trialRun(page, name, version, finish) {
  await stagedRow(page, name).getByRole("link", { name: "Trial run" }).click();
  await expect(page).toHaveURL(/\/admin\/training\/\d+\/trial$/);
  await expect(page.getByRole("heading", { name: "Trial run" })).toBeVisible();
  await expect(page.getByText(`running staged package ${version}`)).toBeVisible(
    { timeout: 20_000 },
  );
  await expect(page.getByTestId("trial-package-notes")).toContainText(
    "Completes on its own reporting",
  );
  const frame = await expectCourseLoaded(page, version);
  await expect(frame.locator("#entry")).toHaveText("ab-initio");
  await expect(page.getByTestId("trial-verdict")).toContainText(
    "Not complete yet",
  );
  await frame.locator("#finish").click();
  await expect(page.getByTestId("trial-verdict")).toContainText(
    "✓ Completed — this package can now be published",
    { timeout: 30_000 },
  );
  await expect(page.getByTestId("trial-writes")).toContainText(finish);
}

test.describe.serial(
  "training course administration",
  { tag: "@training" },
  () => {
    let course;

    test("an E2E course starts with no package, and broken uploads are refused", async ({
      as,
    }) => {
      const page = await as("admin");
      needTraining(page);
      await openAdmin(page);
      await expect(
        page.getByRole("button", { name: /new course/i }),
      ).toHaveCount(0);
      course = await createCourse(page, "admin course");
      await openAdmin(page);
      const row = courseRow(page, course.name);
      await expect(row.getByText("No package", { exact: true })).toBeVisible();

      page.expectApiError(UPLOAD);
      let { dialog, response } = await upload(
        page,
        course.name,
        "Upload package",
        "notZip",
      );
      expect(response.status()).toBe(400);
      await expect(dialog).toContainText(
        "Rejected: the file is not a readable zip archive.",
      );
      await expect(dialog).toContainText(
        "Nothing was uploaded. The current package is unchanged.",
      );
      await dialog.getByRole("button", { name: "Cancel" }).click();

      ({ dialog, response } = await upload(
        page,
        course.name,
        "Upload package",
        "damaged",
      ));
      expect(response.status()).toBe(400);
      await expect(dialog).toContainText(
        "'imsmanifest.xml' inside the archive is damaged and could not be read",
      );
      await dialog.getByRole("button", { name: "Cancel" }).click();
      await expect(
        stagedRow(page, course.name).getByText(/staged/),
      ).toHaveCount(0);
    });

    test("package A is staged, tried to completion and published", async ({
      as,
    }) => {
      const page = await as("admin");
      needTraining(page);
      test.skip(!course, "needs the course from the first test");
      test.setTimeout(150_000);
      await openAdmin(page);

      const { dialog, response } = await upload(
        page,
        course.name,
        "Upload package",
        "a",
      );
      expect(response.status()).toBe(201);
      const uploaded = (await response.json()).data;
      expect(uploaded).toMatchObject({
        packageVersion: "AAAAaaaa",
        reportingMode: "completed-incomplete",
        scormVersion: "1.2",
        entryPath: "scormdriver/indexAPI.html",
        completionConfigReadable: true,
        completesViaStoryline: false,
        missingDeclaredFiles: [],
      });
      await expect(dialog.getByText("Package uploaded.")).toBeVisible();
      await expect(dialog).toContainText("Completes on its own reporting");
      await expect(dialog).toContainText("threshold 100%");
      await dialog.getByRole("button", { name: "Done" }).click();

      const staged = stagedRow(page, course.name);
      await expect(staged).toContainText("⬆ AAAAaaaa staged — not run yet");
      await expect(staged).toContainText("Nothing is live yet");
      const publishButton = staged.getByRole("button", { name: "Publish" });
      await expect(publishButton).toBeDisabled();
      // The reason is a tooltip on the wrapper; the disabled button gets no hover.
      await publishButton.locator("..").hover();
      await expect(page.getByRole("tooltip")).toHaveText(
        "Run this package to completion first",
      );
      await page.mouse.move(0, 0);

      await trialRun(page, course.name, "AAAAaaaa", "completed");

      await openAdmin(page);
      await expect(stagedRow(page, course.name)).toContainText(
        "✓ AAAAaaaa staged — verified",
      );
      await stagedRow(page, course.name)
        .getByRole("button", { name: "Publish" })
        .click();
      const publish = page.getByRole("dialog");
      await expect(publish).toContainText(
        "AAAAaaaa becomes the package this course serves.",
      );
      await publish.getByRole("button", { name: "Publish package" }).click();
      await expect(publish).toBeHidden({ timeout: 20_000 });
      const row = courseRow(page, course.name);
      await expect(
        row.getByRole("link", { name: "Preview package AAAAaaaa" }),
      ).toBeVisible();
      await expect(row.getByText("Live", { exact: true })).toBeVisible();
      await expect(page.getByText("AAAAaaaa staged")).toHaveCount(0);
    });

    test("the preview runs the live package and records nothing", async ({
      as,
    }) => {
      const page = await as("admin");
      needTraining(page);
      test.skip(!course, "needs the course from the first test");
      const trial = trainingRow(page.account.userId, course.id);
      expect(
        trial,
        "the trial run left e2e-admin's own assignment",
      ).not.toBeNull();
      await openAdmin(page);

      const saves = [];
      page.on("request", (r) => {
        if (/\/api\/training\/\d+\/progress$/.test(new URL(r.url()).pathname))
          saves.push(r.url());
      });
      const preview = courseRow(page, course.name).getByRole("link", {
        name: "Preview package AAAAaaaa",
      });
      // The link starts with a 1px sr-only span, which Playwright's default
      // click point lands on; click the middle of the visible version.
      const box = await preview.boundingBox();
      await preview.click({
        position: { x: box.width / 2, y: box.height / 2 },
      });
      await expect(page).toHaveURL(
        new RegExp(`/admin/training/${course.id}/preview$`),
      );
      await expect(page.getByText("Nothing here is recorded.")).toBeVisible();
      await expect(
        page.getByText(`${course.name} · live package AAAAaaaa`),
      ).toBeVisible({
        timeout: 20_000,
      });
      const frame = await expectCourseLoaded(page, "AAAAaaaa");
      await expect(frame.locator("#entry")).toHaveText("ab-initio");
      await frame.locator("#next").click();
      await expect(frame.locator("#location")).toHaveText("page-2");
      await frame.locator("#finish").click();
      await expect(frame.locator("#status")).toHaveText("completed");
      await settle(page);

      expect(saves, "a preview sends no progress").toEqual([]);
      expect(trainingRow(page.account.userId, course.id)).toEqual(trial);
      expect(progressRow(trial.id)).toBeNull();
    });

    test("package B is staged over the live A, then discarded", async ({
      as,
    }) => {
      const page = await as("admin");
      needTraining(page);
      test.skip(!course, "needs the course from the first test");
      await openAdmin(page);

      const dialog = await openUpload(page, course.name, "Replace package");
      await expect(dialog).toContainText(
        "Learners keep seeing AAAAaaaa until you publish it.",
      );
      await dialog.getByRole("button", { name: "Cancel" }).click();

      const { dialog: done, response } = await upload(
        page,
        course.name,
        "Replace package",
        "b",
      );
      expect(response.status()).toBe(201);
      expect((await response.json()).data).toMatchObject({
        packageVersion: "BBBBbbbb",
        reportingMode: "passed-incomplete",
      });
      await done.getByRole("button", { name: "Done" }).click();

      const staged = stagedRow(page, course.name);
      await expect(staged).toContainText("⬆ BBBBbbbb staged — not run yet");
      await expect(staged).toContainText("Learners still see AAAAaaaa.");
      const discarded = page.waitForResponse(
        (r) =>
          r.request().method() === "DELETE" &&
          /\/package$/.test(new URL(r.url()).pathname),
      );
      await staged.getByRole("button", { name: "Discard" }).click();
      expect((await discarded).status()).toBe(200);
      await expect(page.getByText("BBBBbbbb staged")).toHaveCount(0);
      await expect(
        courseRow(page, course.name).getByRole("link", {
          name: "Preview package AAAAaaaa",
        }),
      ).toBeVisible();
    });

    test("package B is staged again, tried and published over A from the trial page", async ({
      as,
    }) => {
      const page = await as("admin");
      needTraining(page);
      test.skip(!course, "needs the course from the first test");
      test.setTimeout(150_000);
      await openAdmin(page);

      const { dialog, response } = await upload(
        page,
        course.name,
        "Replace package",
        "b",
      );
      expect(response.status()).toBe(201);
      await dialog.getByRole("button", { name: "Done" }).click();
      await trialRun(page, course.name, "BBBBbbbb", "passed");
      await expect(
        page.getByText("Learners still see AAAAaaaa."),
      ).toBeVisible();

      await page
        .getByTestId("trial-verdict")
        .getByRole("button", { name: "Publish package" })
        .click();
      const publish = page.getByRole("dialog");
      await expect(publish).toContainText(
        "BBBBbbbb replaces AAAAaaaa for everyone on this course.",
      );
      await expect(publish).toContainText(
        "AAAAaaaa is deleted and cannot be brought back.",
      );
      await publish.getByRole("button", { name: "Publish package" }).click();
      await expect(publish).toBeHidden({ timeout: 20_000 });

      await openAdmin(page);
      const row = courseRow(page, course.name);
      await expect(
        row.getByRole("link", { name: "Preview package BBBBbbbb" }),
      ).toBeVisible();
      await expect(page.getByText("BBBBbbbb staged")).toHaveCount(0);
    });

    test("turning the course off closes it to assignment", async ({ as }) => {
      const page = await as("admin");
      const { trainees } = needTraining(page);
      test.skip(!course, "needs the course from the first test");
      await openAdmin(page);

      await courseRow(page, course.name)
        .getByRole("button", { name: "Deactivate" })
        .click();
      const dialog = page.getByRole("dialog");
      await expect(
        dialog.getByRole("heading", { name: `Turn off ${course.name}` }),
      ).toBeVisible();
      await dialog.getByRole("button", { name: "Turn off course" }).click();
      await expect(dialog).toBeHidden({ timeout: 20_000 });

      const row = courseRow(page, course.name);
      await expect(row.getByText("Off", { exact: true })).toBeVisible();
      await expect(row.getByRole("button", { name: "Activate" })).toBeVisible();

      await page
        .getByLabel("Target course")
        .selectOption({ label: course.name });
      await expect(
        page.getByText(
          "This course is deactivated. Turn it back on to assign it.",
        ),
      ).toBeVisible();

      expect(
        rowsOf(
          `SELECT is_active FROM training_course WHERE course_id = ${Number(course.id)}`,
        ),
      ).toEqual([["f"]]);

      // The backend refuses the assignment too, not only the card.
      page.expectApiError({
        method: "POST",
        path: /^\/api\/training\/assignments\/bulk$/,
        status: 409,
      });
      const refused = await callApi(
        page,
        "POST",
        "/api/training/assignments/bulk",
        { courseId: course.id, userIds: [trainees[0]] },
      );
      expect(refused.status, JSON.stringify(refused.json)).toBe(409);
      expect(refused.json.message).toBe(
        "This course is deactivated and cannot be assigned to anybody new.",
      );
      expect(trainingRow(trainees[0], course.id)).toBeNull();
    });
  },
);
