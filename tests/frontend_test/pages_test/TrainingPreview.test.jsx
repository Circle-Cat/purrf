import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import TrainingPreview from "@/pages/TrainingPreview";
import { MESSAGE_TYPES } from "@/training/scormBridge";

vi.mock("@/api/trainingApi", () => ({
  startTrial: vi.fn(),
  // `useTrainingRuntime` still imports `openSession` as its default `open`
  // -- unused here since the preview page always passes `openPreviewSession`
  // explicitly, but the module import itself must resolve to something.
  openSession: vi.fn(),
  openPreviewSession: vi.fn(),
  saveProgress: vi.fn(),
  listCourses: vi.fn(),
}));
vi.mock("@/context/auth", () => ({
  useAuth: vi.fn(),
}));

import {
  startTrial,
  openSession,
  openPreviewSession,
  saveProgress,
  listCourses,
} from "@/api/trainingApi";
import { useAuth } from "@/context/auth";

// The row this page is reached from always carries a live package (it is
// only linked from a course that has one), so the default fixture does too.
const COURSE = {
  courseId: 9,
  name: "Mentee Onboarding",
  packageVersion: "qPpo9zHD",
  liveState: "live",
  staged: null,
  assignedCount: 10,
  unfinishedCount: 2,
  isActive: true,
};

const SESSION = {
  data: {
    contentBaseUrl: "https://test-training-content.purrf.io/p/tok/",
    sessionToken: "signed.token",
    entryPath: "scormdriver/indexAPI.html",
    playerPath: "__player.html",
    expiresAt: 1788400000,
  },
};

const postFromContent = (data) =>
  window.dispatchEvent(
    new MessageEvent("message", {
      origin: "https://test-training-content.purrf.io",
      data,
    }),
  );

/**
 * @param {{[key: string]: unknown}} [overrides]
 *   Overrides the fetched course row (`listCourses`). The mock is untouched
 *   when no overrides are given, so a test that configures `listCourses`
 *   itself before calling this keeps its own setup.
 */
const renderPreview = (overrides = {}) => {
  if (Object.keys(overrides).length > 0) {
    listCourses.mockResolvedValue({ data: [{ ...COURSE, ...overrides }] });
  }
  return render(
    <MemoryRouter initialEntries={["/admin/training/9/preview"]}>
      <Routes>
        <Route
          path="/admin/training/:courseId/preview"
          element={<TrainingPreview />}
        />
      </Routes>
    </MemoryRouter>,
  );
};

describe("TrainingPreview", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    openPreviewSession.mockResolvedValue(SESSION);
    saveProgress.mockResolvedValue({ data: { status: "in_progress" } });
    listCourses.mockResolvedValue({ data: [COURSE] });
    useAuth.mockReturnValue({
      user: { userId: 7, email: "admin@example.com" },
    });
  });

  it("says nothing is recorded", async () => {
    renderPreview();
    expect(
      await screen.findByText(/Nothing here is recorded/i),
    ).toBeInTheDocument();
  });

  it("names the live package it is showing", async () => {
    listCourses.mockResolvedValue({ data: [COURSE] }); // packageVersion: "qPpo9zHD"
    renderPreview();
    expect(await screen.findByText(/live package qPpo9zHD/)).toBeInTheDocument();
  });

  it("opens a preview session, not a trial and not a learner session", async () => {
    renderPreview();
    await waitFor(() => expect(openPreviewSession).toHaveBeenCalledWith("9"));
    expect(startTrial).not.toHaveBeenCalled();
    expect(openSession).not.toHaveBeenCalled();
  });

  it("renders no verdict bar and no CMI panel", async () => {
    renderPreview();
    await screen.findByTitle("Course");
    expect(screen.queryByTestId("trial-verdict")).toBeNull();
    expect(screen.queryByTestId("trial-writes")).toBeNull();
  });

  it("says so when the course has nothing live", async () => {
    openPreviewSession.mockRejectedValue(new Error("nope"));
    renderPreview();
    expect(
      await screen.findByText(/This course is not available/i),
    ).toBeInTheDocument();
  });

  it("records nothing the course reports", async () => {
    renderPreview();
    await screen.findByTitle("Course");

    postFromContent({
      type: MESSAGE_TYPES.COMMIT,
      cmi: { "cmi.core.lesson_status": "incomplete" },
    });

    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(saveProgress).not.toHaveBeenCalled();
  });
});
