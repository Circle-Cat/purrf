import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { toast } from "sonner";

import AdminTraining from "@/pages/AdminTraining";
import * as api from "@/api/trainingApi";

vi.mock("@/api/trainingApi");
vi.spyOn(toast, "error").mockImplementation(() => {});

const course = {
  courseId: 1,
  name: "Mentor Onboarding",
  description: null,
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

const renderPage = () => render(<AdminTraining />, { wrapper: MemoryRouter });

beforeEach(() => {
  vi.clearAllMocks();
});

describe("AdminTraining page", () => {
  it("shows a loading state before the courses arrive", () => {
    api.listCourses.mockReturnValue(new Promise(() => {}));

    renderPage();

    expect(screen.getByText("Loading...")).toBeInTheDocument();
  });

  it("loads and lists courses on mount", async () => {
    api.listCourses.mockResolvedValue({ data: [course] });

    renderPage();

    expect(await screen.findByText("Mentor Onboarding")).toBeInTheDocument();
    expect(api.listCourses).toHaveBeenCalled();
  });

  it("shows the empty state when there are no courses", async () => {
    api.listCourses.mockResolvedValue({ data: [] });

    renderPage();

    expect(
      await screen.findByText("No training courses yet."),
    ).toBeInTheDocument();
  });

  it("shows an error toast when the fetch fails", async () => {
    api.listCourses.mockRejectedValue(new Error("network error"));

    renderPage();

    await waitFor(() =>
      expect(toast.error).toHaveBeenCalledWith("network error"),
    );
  });
});
