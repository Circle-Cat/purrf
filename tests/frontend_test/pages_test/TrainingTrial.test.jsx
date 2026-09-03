import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Routes, Route, useNavigate } from "react-router-dom";
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

const renderTrialWithNav = () => {
  const GoToAnotherCourse = () => {
    const navigate = useNavigate();
    return (
      <button onClick={() => navigate("/admin/training/6/trial")}>next</button>
    );
  };
  return render(
    <MemoryRouter initialEntries={["/admin/training/5/trial"]}>
      <GoToAnotherCourse />
      <Routes>
        <Route
          path="/admin/training/:courseId/trial"
          element={<TrainingTrial />}
        />
      </Routes>
    </MemoryRouter>,
  );
};

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
        verified: false,
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

  it("shows the course as verified once the server says the course is", async () => {
    saveProgress.mockResolvedValue({ data: { status: "done" } });
    readCompletionConfig
      .mockResolvedValueOnce({
        data: {
          verified: false,
          completionPercentage: 100,
          completesViaStoryline: false,
          completionConfigReadable: true,
        },
      })
      .mockResolvedValue({
        data: {
          verified: true,
          completionPercentage: 100,
          completesViaStoryline: false,
          completionConfigReadable: true,
        },
      });
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

  it("does not claim the course is unlocked while the stamp is still missing", async () => {
    // The assignment can read DONE while the course carries no stamp: a
    // verifier re-running a replaced package was already DONE on their row.
    saveProgress.mockResolvedValue({ data: { status: "done" } });
    renderTrial();
    await screen.findByTitle(/course/i);

    postFromContent({
      type: MESSAGE_TYPES.FINISH,
      cmi: { "cmi.core.lesson_status": "completed" },
    });

    await waitFor(() => expect(saveProgress).toHaveBeenCalled());
    expect(screen.queryByText(/can now be assigned/i)).not.toBeInTheDocument();
  });

  it("shows an already verified course as verified without any commit", async () => {
    readCompletionConfig.mockResolvedValue({
      data: {
        verified: true,
        completionPercentage: 100,
        completesViaStoryline: false,
        completionConfigReadable: true,
      },
    });

    renderTrial();

    expect(
      await screen.findByText(/completed — this course can now be assigned/i),
    ).toBeInTheDocument();
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
      /could not be determined/i,
    );
  });

  it("renders the health check even for a package that completes the ordinary way", async () => {
    // The box used to stay silent here; silence is exactly what let the
    // 08-29 failure go undetected, so a healthy package now says so too,
    // through the same PackageHealthBox the upload dialog uses.
    renderTrial();
    await screen.findByTitle(/course/i);

    expect(
      await screen.findByText(/completes on its own reporting/i),
    ).toBeInTheDocument();
  });

  it("reads the package settings for the course being trialled", async () => {
    renderTrial();
    await screen.findByTitle(/course/i);

    expect(readCompletionConfig).toHaveBeenCalledWith("5");
  });

  it("survives a commit from the content origin that carries no cmi", async () => {
    // Course content is uploaded by third parties and runs on that origin,
    // so a malformed commit needs no bug of ours to arrive.
    renderTrial();
    await screen.findByTitle(/course/i);

    postFromContent({ type: MESSAGE_TYPES.COMMIT });

    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(screen.getByTestId("trial-writes")).toBeInTheDocument();
    expect(saveProgress).not.toHaveBeenCalled();
  });

  it("does not carry one course's failure over to the next", async () => {
    // Router keeps the page mounted when only the param changes.
    startTrial.mockRejectedValueOnce(new Error("nope"));
    renderTrialWithNav();
    await screen.findByText(/could not start a trial run/i);

    await userEvent.click(screen.getByRole("button", { name: /next/i }));

    expect(await screen.findByText(/course #6/i)).toBeInTheDocument();
    expect(
      screen.queryByText(/could not start a trial run/i),
    ).not.toBeInTheDocument();
  });

  it("does not carry one course's package notes over to the next", async () => {
    readCompletionConfig
      .mockResolvedValueOnce({
        data: {
          verified: false,
          completionPercentage: 100,
          completesViaStoryline: true,
          completionConfigReadable: true,
        },
      })
      .mockResolvedValue({
        data: {
          verified: false,
          completionPercentage: 100,
          completesViaStoryline: false,
          completionConfigReadable: true,
        },
      });
    renderTrialWithNav();
    expect(
      await screen.findByTestId("trial-package-notes"),
    ).toHaveTextContent(/storyline/i);

    await userEvent.click(screen.getByRole("button", { name: /next/i }));

    await screen.findByText(/course #6/i);
    await waitFor(() =>
      expect(screen.getByTestId("trial-package-notes")).not.toHaveTextContent(
        /storyline/i,
      ),
    );
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
