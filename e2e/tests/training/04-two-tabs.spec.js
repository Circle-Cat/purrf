import { test, expect } from "../../fixtures.js";
import {
  assign,
  expectCourseLoaded,
  liveCourse,
  needTraining,
  nextSave,
  progressRow,
  trainingRow,
} from "./helpers.js";

// The newest tab owns an assignment's progress: e2e-member opens the same
// course twice, and the first tab's next save is refused with
// training_run_superseded while the second one keeps saving.

test.describe("training in two tabs", { tag: "@training" }, () => {
  test("the tab opened first is told the course is open in another tab", async ({
    as,
  }) => {
    test.setTimeout(150_000);
    const admin = await as("admin");
    needTraining(admin);
    const first = await as("member");
    const memberId = first.account.userId;
    const course = await liveCourse(admin, "two tabs course");
    await assign(admin, course.id, [memberId]);
    const { id } = trainingRow(memberId, course.id);

    await first.goto(`/training/${id}`);
    const firstFrame = await expectCourseLoaded(first, "AAAAaaaa");
    const second = await first.context().newPage();
    await second.goto(`/training/${id}`);
    const secondFrame = await expectCourseLoaded(second, "AAAAaaaa");

    first.expectApiError({
      method: "POST",
      path: new RegExp(`^/api/training/${id}/progress$`),
      status: 409,
    });
    const refused = nextSave(first, id);
    await first.bringToFront();
    await firstFrame.locator("#next").click();
    const res = await refused;
    expect(res.status()).toBe(409);
    expect((await res.json()).data).toMatchObject({
      code: "training_run_superseded",
    });
    await expect(
      first.getByText(
        "This course is open in another tab. Close this tab and continue there.",
      ),
    ).toBeVisible();
    expect(progressRow(id), "the superseded tab stored nothing").toBeNull();

    await second.bringToFront();
    const saved = nextSave(second, id);
    await secondFrame.locator("#next").click();
    expect((await saved).status()).toBe(200);
    expect(progressRow(id)).toMatchObject({ lessonLocation: "page-2" });
  });
});
