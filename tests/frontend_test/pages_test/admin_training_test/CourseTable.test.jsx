import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, it, expect, vi, beforeEach } from "vitest";
import "@testing-library/jest-dom";

import CourseTable from "@/pages/AdminTraining/components/CourseTable";
import * as api from "@/api/trainingApi";

vi.mock("@/api/trainingApi");

// One fixture per `TrainingCourseState`, shaped like the wire DTO
// (backend/dto/training_course_dto.py -> TrainingCourseDto), from the state
// table in docs/superpowers/specs/2026-09-01-scorm-training-ui-design.md §4.1.
const verified = {
  courseId: 1,
  name: "Mentor Onboarding",
  description: "What a mentor needs before their first pairing.",
  category: "mentorship_mentor_onboarding",
  isActive: true,
  state: "verified",
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
  state: "needs_trial_run",
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
  state: "no_package",
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
  state: "external_link",
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
  it("shows a verified course as assignable", () => {
    renderTable([verified]);

    expect(screen.getByText("Verified")).toBeInTheDocument();
    const assign = screen.getByRole("button", { name: /assign/i });
    expect(assign).not.toBeDisabled();
  });

  it("shows the total assigned count", () => {
    renderTable([verified]);

    expect(screen.getByText("124")).toBeInTheDocument();
  });

  it("offers a trial run for a course that has never been finished", () => {
    renderTable([needsTrialRun]);

    expect(screen.getByText("Needs trial run")).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: /trial run/i }),
    ).toHaveAttribute("href", "/admin/training/2/trial");
  });

  it("keeps Assign visible but disabled until the course is verified", () => {
    render(<CourseTable courses={[needsTrialRun]} />, { wrapper: MemoryRouter });

    const assign = screen.getByRole("button", { name: /assign/i });
    expect(assign).toBeDisabled();
    expect(assign).toHaveAccessibleDescription(
      /run this course to completion first/i,
    );
  });

  it("offers to upload a package for a course that has never had one", () => {
    renderTable([noPackage]);

    expect(screen.getByText("No package")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /upload package/i }),
    ).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /assign/i })).not.toBeInTheDocument();
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

    await userEvent.click(
      screen.getByRole("button", { name: /deactivate/i }),
    );

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

    await userEvent.click(
      screen.getByRole("button", { name: /deactivate/i }),
    );
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
    expect(
      screen.queryByText(/nothing is deleted/i),
    ).not.toBeInTheDocument();
  });

  it("activates a course directly with no dialog, and only reflects it once fresh courses arrive", async () => {
    const inactive = { ...verified, courseId: 9, isActive: false };
    const reactivated = { ...inactive, isActive: true };
    api.updateCourse.mockResolvedValue({ data: {} });
    const onCoursesChanged = vi.fn();

    const { rerender } = renderTable([inactive], onCoursesChanged);

    await userEvent.click(
      screen.getByRole("button", { name: /^activate$/i }),
    );

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
      <CourseTable courses={[reactivated]} onCoursesChanged={onCoursesChanged} />,
    );

    expect(
      screen.getByRole("button", { name: /deactivate/i }),
    ).toBeInTheDocument();
  });
});
