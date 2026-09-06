import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, it, expect, vi, beforeEach } from "vitest";
import "@testing-library/jest-dom";

import CourseTable from "@/pages/AdminTraining/components/CourseTable";
import * as api from "@/api/trainingApi";
import { formatDateTimeWithZone } from "@/utils/dateTime";

vi.mock("@/api/trainingApi");

// Pins the viewer's zone so the upload timestamp is asserted end to end
// (the real formatter, a fixed zone) rather than trusting the wiring blind.
vi.mock("@/utils/dateTime", async (importOriginal) => {
  const actual = await importOriginal();
  return { ...actual, resolveViewerTimezone: () => "America/New_York" };
});

// One fixture per `TrainingCourseLiveState`, shaped like the wire DTO
// (backend/dto/training_course_dto.py -> TrainingCourseDto). `verified` and
// `needsTrialRun` are both live packages now -- a staged package's own
// verification (task 9's sub-row) is what used to separate them, and no
// longer gates assigning a package that is already live.
const verified = {
  courseId: 1,
  name: "Mentor Onboarding",
  description: "What a mentor needs before their first pairing.",
  category: "mentorship_mentor_onboarding",
  isActive: true,
  liveState: "live",
  link: null,
  scormVersion: "1.2",
  packageVersion: "qPpo9zHD",
  reportingMode: "completed",
  packageUploadedAt: "2026-08-20T00:00:00Z",
  verifiedCompletableAt: "2026-08-21T00:00:00Z",
  verifiedByUserId: 42,
  assignedCount: 124,
  unfinishedCount: 3,
};

const needsTrialRun = {
  courseId: 2,
  name: "Mentee Onboarding",
  description: null,
  category: "mentorship_mentee_onboarding",
  isActive: true,
  liveState: "live",
  link: null,
  scormVersion: "1.2",
  packageVersion: "cm171zxgx006v",
  reportingMode: "passed-incomplete",
  packageUploadedAt: "2026-09-01T00:00:00Z",
  verifiedCompletableAt: null,
  verifiedByUserId: null,
  assignedCount: 0,
  unfinishedCount: 0,
};

const noPackage = {
  courseId: 3,
  name: "Corporate Culture",
  description: null,
  category: "corporate_culture_course",
  isActive: true,
  liveState: "no_package",
  link: null,
  scormVersion: null,
  packageVersion: null,
  reportingMode: null,
  packageUploadedAt: null,
  verifiedCompletableAt: null,
  verifiedByUserId: null,
  assignedCount: 0,
  unfinishedCount: 0,
};

const externalLink = {
  courseId: 4,
  name: "Residency Program Onboarding",
  description: null,
  category: "residency_program_onboarding",
  isActive: true,
  liveState: "external_link",
  link: "https://example.com/mentor",
  scormVersion: null,
  packageVersion: null,
  reportingMode: null,
  packageUploadedAt: null,
  verifiedCompletableAt: null,
  verifiedByUserId: null,
  assignedCount: 61,
  unfinishedCount: 23,
};

const renderTable = (courses, onCoursesChanged) =>
  render(
    <CourseTable courses={courses} onCoursesChanged={onCoursesChanged} />,
    { wrapper: MemoryRouter },
  );

beforeEach(() => {
  vi.clearAllMocks();
});

describe("CourseTable", () => {
  it("shows a live course as assignable", () => {
    renderTable([verified]);

    expect(screen.getByText("Live")).toBeInTheDocument();
    const assign = screen.getByRole("button", { name: /assign/i });
    expect(assign).not.toBeDisabled();
  });

  it("shows the total assigned count", () => {
    renderTable([verified]);

    expect(screen.getByText("124")).toBeInTheDocument();
  });

  it("keeps Assign enabled on a live course even without its own verification stamp", () => {
    // The verification stamp only gates publishing a staged package now --
    // once a package is live, assigning it no longer re-checks that stamp.
    renderTable([needsTrialRun]);

    const assign = screen.getByRole("button", { name: /^assign$/i });
    expect(assign).not.toBeDisabled();
  });

  it("keeps Assign disabled on a deactivated course, which the API answers 409 for", () => {
    // The backend gate is verified AND active. A still-clickable Assign sends
    // the admin through the whole form to reach a rejection.
    renderTable([{ ...verified, isActive: false }]);

    expect(screen.getByRole("button", { name: /^assign$/i })).toBeDisabled();
  });

  it("names deactivation as the reason, not the publish rule", () => {
    // Two rules, two sentences: one is answered by publishing a package, the
    // other by turning the course back on.
    renderTable([{ ...verified, isActive: false }]);

    const assign = screen.getByRole("button", { name: /^assign$/i });
    expect(assign).toHaveAccessibleDescription(
      /deactivated\. turn it back on to assign it/i,
    );
    expect(assign).not.toHaveAccessibleDescription(/publish a package/i);
  });

  it("offers to upload a package for a course that has never had one", () => {
    renderTable([noPackage]);

    expect(screen.getByText("No package")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /upload package/i }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /assign/i }),
    ).not.toBeInTheDocument();
  });

  it("shows an external-link course as such, with the link", () => {
    render(<CourseTable courses={[externalLink]} />, { wrapper: MemoryRouter });

    expect(screen.getByText("External link")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /view/i })).toHaveAttribute(
      "href",
      "https://example.com/mentor",
    );
    expect(
      screen.getByRole("button", { name: /upload package/i }),
    ).toBeInTheDocument();
  });

  it("opens the deactivate dialog naming this row's headcounts", async () => {
    renderTable([externalLink]);

    await userEvent.click(screen.getByRole("button", { name: /deactivate/i }));

    expect(
      screen.getByText(/61 people already assigned keep their access/i),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/23 of them have not finished yet/i),
    ).toBeInTheDocument();
  });

  it("turns a course off through the dialog, then asks the caller to refetch and closes", async () => {
    api.updateCourse.mockResolvedValue({ data: {} });
    const onCoursesChanged = vi.fn();
    renderTable([verified], onCoursesChanged);

    await userEvent.click(screen.getByRole("button", { name: /deactivate/i }));
    await userEvent.click(
      screen.getByRole("button", { name: /turn off course/i }),
    );

    await waitFor(() =>
      expect(api.updateCourse).toHaveBeenCalledWith(verified.courseId, {
        isActive: false,
      }),
    );
    expect(onCoursesChanged).toHaveBeenCalledTimes(1);
    // CourseTable never patches `courses` itself -- the dialog is gone, but
    // the row still reads whatever `courses` says until a fresh prop arrives.
    expect(screen.queryByText(/nothing is deleted/i)).not.toBeInTheDocument();
  });

  it("activates a course directly with no dialog, and only reflects it once fresh courses arrive", async () => {
    const inactive = { ...verified, courseId: 9, isActive: false };
    const reactivated = { ...inactive, isActive: true };
    api.updateCourse.mockResolvedValue({ data: {} });
    const onCoursesChanged = vi.fn();

    const { rerender } = renderTable([inactive], onCoursesChanged);

    await userEvent.click(screen.getByRole("button", { name: /^activate$/i }));

    await waitFor(() =>
      expect(api.updateCourse).toHaveBeenCalledWith(inactive.courseId, {
        isActive: true,
      }),
    );
    expect(onCoursesChanged).toHaveBeenCalledTimes(1);
    // No local patch: the row still says Activate until the parent re-renders
    // with what the refetch actually returned.
    expect(
      screen.getByRole("button", { name: /^activate$/i }),
    ).toBeInTheDocument();

    rerender(
      <CourseTable
        courses={[reactivated]}
        onCoursesChanged={onCoursesChanged}
      />,
    );

    expect(
      screen.getByRole("button", { name: /deactivate/i }),
    ).toBeInTheDocument();
  });

  it("opens the upload dialog for a course with no package, uploads, and refetches on success", async () => {
    const file = new File(["zip-bytes"], "course.zip", {
      type: "application/zip",
    });
    api.uploadPackage.mockResolvedValue({
      data: {
        completionConfigReadable: true,
        completesViaStoryline: false,
        completionPercentage: 100,
      },
    });
    const onCoursesChanged = vi.fn();
    renderTable([noPackage], onCoursesChanged);

    await userEvent.click(
      screen.getByRole("button", { name: /upload package/i }),
    );
    await userEvent.upload(screen.getByLabelText(/scorm package/i), file);
    await userEvent.click(screen.getByRole("button", { name: /^upload/i }));

    // The third argument is the dialog's own progress callback, handed
    // straight through so the bar it draws is fed by the real transfer.
    await waitFor(() =>
      expect(api.uploadPackage).toHaveBeenCalledWith(
        noPackage.courseId,
        file,
        expect.any(Function),
      ),
    );
    expect(onCoursesChanged).toHaveBeenCalledTimes(1);
  });

  it("opens the assign dialog for a verified course, assigns, and refetches on success", async () => {
    api.assignCourse.mockResolvedValue({
      data: {
        trainingId: 9,
        userId: 11,
        courseId: verified.courseId,
        created: true,
      },
    });
    const onCoursesChanged = vi.fn();
    renderTable([verified], onCoursesChanged);

    await userEvent.click(screen.getByRole("button", { name: /^assign$/i }));
    await userEvent.type(screen.getByLabelText(/person/i), "11");
    await userEvent.click(screen.getByRole("button", { name: /^assign$/i }));

    await waitFor(() =>
      expect(api.assignCourse).toHaveBeenCalledWith({
        userId: 11,
        courseId: verified.courseId,
      }),
    );
    expect(onCoursesChanged).toHaveBeenCalledTimes(1);
  });

  it("labels the action Replace package for a course that already has one, and says the upload only stages it", async () => {
    renderTable([verified]);

    await userEvent.click(
      screen.getByRole("button", { name: /replace package/i }),
    );

    expect(
      screen.getByText(/Learners keep seeing qPpo9zHD until you publish it/),
    ).toBeInTheDocument();
  });

  it("makes the live version a link into the preview", () => {
    renderTable([{ ...verified, courseId: 9, packageVersion: "qPpo9zHD" }]);

    expect(screen.getByRole("link", { name: "qPpo9zHD" })).toHaveAttribute(
      "href",
      "/admin/training/9/preview",
    );
  });

  it("leaves a course with no package with nothing to click", () => {
    renderTable([{ ...verified, packageVersion: null, link: null }]);

    expect(screen.queryByRole("link", { name: /preview/i })).toBeNull();
  });

  it("leaves an external-link course pointing outward", () => {
    renderTable([
      { ...verified, link: "https://example.com/c", packageVersion: null },
    ]);

    expect(screen.getByRole("link", { name: /View/ })).toHaveAttribute(
      "href",
      "https://example.com/c",
    );
  });
});

// One staged sub-row per course whose `staged` is non-null (spec §8). Kept
// separate from the `describe` above because these fixtures shape `staged`
// directly rather than reusing `verified`/`needsTrialRun`/etc.
describe("CourseTable staged sub-row", () => {
  const staged = (over) => ({
    courseId: 9,
    name: "Mentee Onboarding",
    isActive: true,
    liveState: "live",
    packageVersion: "qPpo9zHD",
    staged: {
      packageId: 2,
      packageVersion: "RaOvlxxJ",
      uploadedAt: "2026-09-05T03:41:00Z",
      verifiedCompletableAt: null,
    },
    ...over,
  });

  it("shows no sub-row for a course with nothing staged", () => {
    renderTable([staged({ staged: null })]);

    expect(screen.queryByText(/staged/i)).not.toBeInTheDocument();
  });

  it("says what learners still see while a package is staged", () => {
    renderTable([staged()]);

    expect(
      screen.getByText("Learners still see qPpo9zHD."),
    ).toBeInTheDocument();
  });

  it("says nothing is live when the course has never published", () => {
    renderTable([staged({ liveState: "no_package", packageVersion: null })]);

    expect(
      screen.getByText(
        "Nothing is live yet; publishing makes this course assignable.",
      ),
    ).toBeInTheDocument();
  });

  it("keeps Publish on screen but disabled until the package is verified", () => {
    renderTable([staged()]);

    const publish = screen.getByRole("button", { name: "Publish" });
    expect(publish).toBeDisabled();
    expect(publish).toHaveAttribute(
      "title",
      "Run this package to completion first",
    );
  });

  it("enables Publish once the staged package is verified", () => {
    renderTable([
      staged({
        staged: {
          packageId: 2,
          packageVersion: "RaOvlxxJ",
          uploadedAt: "2026-09-05T03:41:00Z",
          verifiedCompletableAt: "2026-09-05T04:10:00Z",
        },
      }),
    ]);

    expect(screen.getByRole("button", { name: "Publish" })).toBeEnabled();
  });

  it("shows the staged package's upload time and version marker", () => {
    renderTable([staged()]);

    expect(
      screen.getByText(/⬆ RaOvlxxJ staged — not run yet/),
    ).toBeInTheDocument();
  });

  it("marks a verified staged package with a check instead of the upload arrow", () => {
    renderTable([
      staged({
        staged: {
          packageId: 2,
          packageVersion: "RaOvlxxJ",
          uploadedAt: "2026-09-05T03:41:00Z",
          verifiedCompletableAt: "2026-09-05T04:10:00Z",
        },
      }),
    ]);

    expect(
      screen.getByText(/✓ RaOvlxxJ staged — verified/),
    ).toBeInTheDocument();
  });

  it("discards the staged package and refetches, without touching the live package", async () => {
    api.discardPackage.mockResolvedValue({ data: {} });
    const onCoursesChanged = vi.fn();
    renderTable([staged()], onCoursesChanged);

    await userEvent.click(screen.getByRole("button", { name: /^discard$/i }));

    await waitFor(() => expect(api.discardPackage).toHaveBeenCalledWith(9));
    expect(onCoursesChanged).toHaveBeenCalledTimes(1);
    expect(api.publishPackage).not.toHaveBeenCalled();
  });

  it("sends one DELETE however fast Discard is double-clicked", async () => {
    // Nothing stands between the click and the request -- spec 6.2 shows a
    // bare Discard, and re-uploading the zip is the way back -- so the button
    // itself has to latch. The second DELETE finds nothing staged and reaches
    // the admin as a red toast on an action that worked.
    let land;
    api.discardPackage.mockReturnValue(
      new Promise((resolve) => {
        land = resolve;
      }),
    );
    const onCoursesChanged = vi.fn();
    renderTable([staged()], onCoursesChanged);

    const discard = screen.getByRole("button", { name: /^discard$/i });
    await userEvent.click(discard);
    await userEvent.click(discard);

    expect(api.discardPackage).toHaveBeenCalledTimes(1);
    land({ data: {} });
    await waitFor(() => expect(onCoursesChanged).toHaveBeenCalledTimes(1));
  });

  it("opens the publish dialog from a verified staged package, then publishes and refetches", async () => {
    api.publishPackage.mockResolvedValue({ data: {} });
    const onCoursesChanged = vi.fn();
    renderTable(
      [
        staged({
          assignedCount: 48,
          unfinishedCount: 3,
          staged: {
            packageId: 2,
            packageVersion: "RaOvlxxJ",
            uploadedAt: "2026-09-05T03:41:00Z",
            verifiedCompletableAt: "2026-09-05T04:10:00Z",
          },
        }),
      ],
      onCoursesChanged,
    );

    await userEvent.click(screen.getByRole("button", { name: "Publish" }));

    expect(
      screen.getByText(
        "RaOvlxxJ replaces qPpo9zHD for everyone on this course.",
      ),
    ).toBeInTheDocument();

    await userEvent.click(
      screen.getByRole("button", { name: /publish package/i }),
    );

    await waitFor(() => expect(api.publishPackage).toHaveBeenCalledWith(9));
    expect(onCoursesChanged).toHaveBeenCalledTimes(1);
  });

  it("names the staged package without a version when it has none, instead of leaving a gap", () => {
    renderTable([
      staged({
        staged: {
          packageId: 2,
          packageVersion: null,
          uploadedAt: "2026-09-05T03:41:00Z",
          verifiedCompletableAt: null,
        },
      }),
    ]);

    expect(
      screen.getByText("⬆ the staged package — not run yet"),
    ).toBeInTheDocument();
    expect(screen.queryByText(/⬆ +staged/)).not.toBeInTheDocument();
  });

  it("says learners still see the current package when the live package has no version", () => {
    renderTable([staged({ packageVersion: null })]);

    expect(
      screen.getByText("Learners still see the current package."),
    ).toBeInTheDocument();
    expect(screen.queryByText(/still see \./)).not.toBeInTheDocument();
  });

  it("shows the staged package's upload time in the viewer's timezone", () => {
    renderTable([staged()]);

    const expected = formatDateTimeWithZone(
      "2026-09-05T03:41:00Z",
      "America/New_York",
    );
    expect(screen.getByText(expected)).toBeInTheDocument();
  });

  it("offers a Trial run link into the course's own trial route", () => {
    renderTable([staged()]);

    expect(screen.getByRole("link", { name: /trial run/i })).toHaveAttribute(
      "href",
      "/admin/training/9/trial",
    );
  });
});
