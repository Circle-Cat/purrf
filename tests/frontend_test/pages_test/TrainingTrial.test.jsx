import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import TrainingTrial from "@/pages/TrainingTrial";
import { MESSAGE_TYPES } from "@/training/scormBridge";

vi.mock("@/api/trainingApi", () => ({
  startTrial: vi.fn(),
  openSession: vi.fn(),
  saveProgress: vi.fn(),
  readCompletionConfig: vi.fn(),
}));
vi.mock("@/context/auth", () => ({
  useAuth: vi.fn(),
}));

import {
  startTrial,
  openSession,
  saveProgress,
  readCompletionConfig,
} from "@/api/trainingApi";
import { useAuth } from "@/context/auth";

const renderTrial = () =>
  render(
    <MemoryRouter initialEntries={["/admin/training/5/trial"]}>
      <Routes>
        <Route
          path="/admin/training/:courseId/trial"
          element={<TrainingTrial />}
        />
      </Routes>
    </MemoryRouter>,
  );

const TRIAL = {
  data: { trainingId: 42, userId: 7, courseId: 5, created: true },
};

const SESSION = {
  data: {
    contentBaseUrl: "https://test-training-content.purrf.io/p/tok/",
    entryPath: "scormdriver/indexAPI.html",
    playerPath: "__player.html",
    expiresAt: 1788400000,
    progress: null,
  },
};

const postFromContent = (data) =>
  window.dispatchEvent(
    new MessageEvent("message", {
      origin: "https://test-training-content.purrf.io",
      data,
    }),
  );

describe("TrainingTrial", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    startTrial.mockResolvedValue(TRIAL);
    openSession.mockResolvedValue(SESSION);
    saveProgress.mockResolvedValue({ data: { status: "in_progress" } });
    readCompletionConfig.mockResolvedValue({
      data: {
        completionPercentage: 100,
        completesViaStoryline: false,
        completionConfigReadable: true,
      },
    });
    useAuth.mockReturnValue({
      user: { userId: 7, email: "admin@example.com" },
    });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("starts a trial on the course, then opens the session it returns", async () => {
    renderTrial();

    await waitFor(() => expect(startTrial).toHaveBeenCalledWith("5"));
    await waitFor(() => expect(openSession).toHaveBeenCalledWith(42));

    const frame = await screen.findByTitle(/course/i);
    expect(frame.src).toContain(
      "https://test-training-content.purrf.io/p/tok/__player.html",
    );
  });

  it("lists a received CMI write with its field, value, and time", async () => {
    renderTrial();
    await screen.findByTitle(/course/i);

    postFromContent({
      type: MESSAGE_TYPES.COMMIT,
      cmi: { "cmi.core.lesson_status": "incomplete" },
    });

    await waitFor(() => expect(saveProgress).toHaveBeenCalled());
    const writesLog = within(await screen.findByTestId("trial-writes"));
    expect(writesLog.getByText("cmi.core.lesson_status")).toBeInTheDocument();
    expect(writesLog.getByText("incomplete")).toBeInTheDocument();
  });

  it("shows the course as verified once the server says the assignment is done", async () => {
    saveProgress.mockResolvedValue({ data: { status: "done" } });
    renderTrial();
    await screen.findByTitle(/course/i);

    postFromContent({
      type: MESSAGE_TYPES.FINISH,
      cmi: { "cmi.core.lesson_status": "completed" },
    });

    await waitFor(() => expect(saveProgress).toHaveBeenCalled());
    expect(
      await screen.findByText(/completed — this course can now be assigned/i),
    ).toBeInTheDocument();
    expect(screen.getByText(/now verified and unlocked/i)).toBeInTheDocument();
  });

  it("does not claim completion while the server still says in progress", async () => {
    renderTrial();
    await screen.findByTitle(/course/i);

    postFromContent({
      type: MESSAGE_TYPES.COMMIT,
      cmi: { "cmi.core.lesson_status": "incomplete" },
    });

    await waitFor(() => expect(saveProgress).toHaveBeenCalled());
    expect(screen.getByText(/not complete yet/i)).toBeInTheDocument();
    expect(screen.queryByText(/can now be assigned/i)).not.toBeInTheDocument();
  });

  it("does not claim completion on a finishing status the server did not accept", async () => {
    // The page has no second opinion. The server folds in rules it cannot
    // see: DONE is absorbing, and the stamp needs a grant.
    renderTrial();
    await screen.findByTitle(/course/i);

    postFromContent({
      type: MESSAGE_TYPES.COMMIT,
      cmi: { "cmi.core.lesson_status": "passed" },
    });

    await waitFor(() => expect(saveProgress).toHaveBeenCalled());
    expect(screen.queryByText(/can now be assigned/i)).not.toBeInTheDocument();
    expect(screen.getByText(/not complete yet/i)).toBeInTheDocument();
  });

  it("keeps a message from an untrusted origin out of both the panel and the save", async () => {
    renderTrial();
    await screen.findByTitle(/course/i);

    window.dispatchEvent(
      new MessageEvent("message", {
        origin: "https://evil.example",
        data: {
          type: MESSAGE_TYPES.COMMIT,
          cmi: { "cmi.core.lesson_status": "completed" },
        },
      }),
    );

    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(saveProgress).not.toHaveBeenCalled();
    const writesLog = within(screen.getByTestId("trial-writes"));
    expect(
      writesLog.queryByText("cmi.core.lesson_status"),
    ).not.toBeInTheDocument();
    expect(writesLog.getByText(/no cmi traffic received/i)).toBeInTheDocument();
  });

  it("warns before the run that this course only finishes via Storyline", async () => {
    readCompletionConfig.mockResolvedValue({
      data: {
        completionPercentage: 100,
        completesViaStoryline: true,
        completionConfigReadable: true,
      },
    });

    renderTrial();

    expect(await screen.findByTestId("trial-package-notes")).toHaveTextContent(
      /storyline/i,
    );
  });

  it("says so when the package's completion settings cannot be read", async () => {
    readCompletionConfig.mockResolvedValue({
      data: {
        completionPercentage: null,
        completesViaStoryline: false,
        completionConfigReadable: false,
      },
    });

    renderTrial();

    expect(await screen.findByTestId("trial-package-notes")).toHaveTextContent(
      /could not read/i,
    );
  });

  it("stays quiet for a package that completes the ordinary way", async () => {
    renderTrial();
    await screen.findByTitle(/course/i);

    expect(screen.queryByTestId("trial-package-notes")).not.toBeInTheDocument();
  });

  it("reads the package settings for the course being trialled", async () => {
    renderTrial();
    await screen.findByTitle(/course/i);

    expect(readCompletionConfig).toHaveBeenCalledWith("5");
  });

  it("shows suspend_data as a size only, never a limit", async () => {
    renderTrial();
    await screen.findByTitle(/course/i);

    postFromContent({
      type: MESSAGE_TYPES.COMMIT,
      cmi: { "cmi.suspend_data": "x".repeat(1264) },
    });

    await waitFor(() => expect(saveProgress).toHaveBeenCalled());
    const writesLog = within(await screen.findByTestId("trial-writes"));
    const size = writesLog.getByText("1264 chars");
    expect(size).toBeInTheDocument();
    expect(screen.queryByText(/4096/)).not.toBeInTheDocument();
    expect(size.textContent).not.toMatch(/\//);
  });
});
