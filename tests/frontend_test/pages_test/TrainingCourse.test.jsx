import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import TrainingCourse from "@/pages/TrainingCourse";

vi.mock("@/api/trainingApi", () => ({
  openSession: vi.fn(),
  saveProgress: vi.fn(),
}));

import { openSession, saveProgress } from "@/api/trainingApi";

// react-router-dom re-exports live hooks from react-router; in the Bazel
// sandbox vi.mock("react-router-dom") does not intercept useParams for the
// component. Route through a real MemoryRouter instead, per the established
// codebase pattern (see PostingEditor.test.jsx).
const renderCourse = () =>
  render(
    <MemoryRouter initialEntries={["/training/42"]}>
      <Routes>
        <Route path="/training/:trainingId" element={<TrainingCourse />} />
      </Routes>
    </MemoryRouter>,
  );

const SESSION = {
  data: {
    contentBaseUrl: "https://test-training-content.purrf.io/p/tok/",
    entryPath: "scormdriver/indexAPI.html",
    playerPath: "__player.html",
    expiresAt: 1788400000,
  },
};

describe("TrainingCourse", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    openSession.mockResolvedValue(SESSION);
    saveProgress.mockResolvedValue({});
  });

  it("points the player frame at the content origin, not at our own", async () => {
    renderCourse();

    const frame = await screen.findByTitle(/course/i);
    expect(frame.src).toContain(
      "https://test-training-content.purrf.io/p/tok/__player.html",
    );
  });

  it("saves a commit that came from the content origin", async () => {
    renderCourse();
    await screen.findByTitle(/course/i);

    window.dispatchEvent(
      new MessageEvent("message", {
        origin: "https://test-training-content.purrf.io",
        data: { type: "scorm:commit", cmi: { "cmi.suspend_data": "blob" } },
      }),
    );

    await waitFor(() =>
      expect(saveProgress).toHaveBeenCalledWith("42", {
        cmi: { "cmi.suspend_data": "blob" },
      }),
    );
  });

  it("ignores a commit forged by any other page", async () => {
    renderCourse();
    await screen.findByTitle(/course/i);

    window.dispatchEvent(
      new MessageEvent("message", {
        origin: "https://evil.example",
        data: {
          type: "scorm:commit",
          cmi: { "cmi.core.lesson_status": "passed" },
        },
      }),
    );

    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(saveProgress).not.toHaveBeenCalled();
  });

  it("tells the learner when a save failed, because the course cannot", async () => {
    // LMSCommit already answered "true" to the course the moment it posted;
    // only this page knows.
    saveProgress.mockRejectedValue(new Error("boom"));
    renderCourse();
    await screen.findByTitle(/course/i);

    window.dispatchEvent(
      new MessageEvent("message", {
        origin: "https://test-training-content.purrf.io",
        data: { type: "scorm:commit", cmi: {} },
      }),
    );

    expect(await screen.findByText(/could not be saved/i)).toBeInTheDocument();
  });

  it("says so when the course has no package to open", async () => {
    openSession.mockRejectedValue({ response: { status: 404 } });

    renderCourse();

    expect(await screen.findByText(/not available/i)).toBeInTheDocument();
  });
});
