import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import TrainingTrial from "@/pages/TrainingTrial";
import { MESSAGE_TYPES } from "@/training/scormBridge";

vi.mock("@/api/trainingApi", () => ({
  startTrial: vi.fn(),
  openSession: vi.fn(),
  saveProgress: vi.fn(),
}));
vi.mock("@/context/auth", () => ({
  useAuth: vi.fn(),
}));

import { startTrial, openSession, saveProgress } from "@/api/trainingApi";
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
    saveProgress.mockResolvedValue({});
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

  it("shows the course as verified and unlocked once it reports a finishing status", async () => {
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

  it("does not claim completion for a non-finishing status", async () => {
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
