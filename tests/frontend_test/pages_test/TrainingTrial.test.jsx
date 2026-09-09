import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Routes, Route, useNavigate } from "react-router-dom";
import TrainingTrial from "@/pages/TrainingTrial";
import { MESSAGE_TYPES } from "@/training/scormBridge";

vi.mock("@/api/trainingApi", () => ({
  startTrial: vi.fn(),
  // `useTrainingRuntime` still imports `openSession` as its default `open`
  // -- unused here since the trial page always passes `openTrialSession`
  // explicitly, but the module import itself must resolve to something.
  openSession: vi.fn(),
  openTrialSession: vi.fn(),
  saveProgress: vi.fn(),
  readCompletionConfig: vi.fn(),
  listCourses: vi.fn(),
  publishPackage: vi.fn(),
}));
vi.mock("@/context/auth", () => ({
  useAuth: vi.fn(),
}));

import {
  startTrial,
  openTrialSession,
  saveProgress,
  readCompletionConfig,
  listCourses,
  publishPackage,
} from "@/api/trainingApi";
import { useAuth } from "@/context/auth";

// The row this page is reached from always carries a staged package (it is
// only linked from `StagedRow`'s "Trial run" button), so the default fixture
// does too -- individual tests override just the keys they care about.
const COURSE = {
  courseId: 5,
  name: "Mentee Onboarding",
  packageVersion: "aaaaaaaa",
  liveState: "live",
  staged: {
    packageId: 99,
    packageVersion: "bbbbbbbb",
    uploadedAt: "2026-09-01T00:00:00Z",
    uploadedByUserId: 1,
    verifiedCompletableAt: null,
    verifiedByUserId: null,
  },
  assignedCount: 10,
  unfinishedCount: 2,
  isActive: true,
};

/**
 * @param {{verified?: boolean, [key: string]: unknown}} [overrides]
 *   `verified` feeds `readCompletionConfig`'s response; everything else
 *   overrides the fetched course row (`listCourses`). Neither mock is
 *   touched when the corresponding overrides are absent, so a test that
 *   configures either mock itself before calling this keeps its own setup.
 */
const renderTrial = (overrides = {}) => {
  const { verified, ...courseOverrides } = overrides;
  if (Object.keys(courseOverrides).length > 0) {
    listCourses.mockResolvedValue({
      data: [{ ...COURSE, ...courseOverrides }],
    });
  }
  if (verified !== undefined) {
    readCompletionConfig.mockResolvedValue({
      data: {
        verified,
        completionPercentage: 100,
        completesViaStoryline: false,
        completionConfigReadable: true,
      },
    });
  }
  return render(
    <MemoryRouter initialEntries={["/admin/training/5/trial"]}>
      <Routes>
        <Route
          path="/admin/training/:courseId/trial"
          element={<TrainingTrial />}
        />
      </Routes>
    </MemoryRouter>,
  );
};

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
    sessionToken: "signed.token",
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
    openTrialSession.mockResolvedValue(SESSION);
    saveProgress.mockResolvedValue({ data: { status: "in_progress" } });
    readCompletionConfig.mockResolvedValue({
      data: {
        verified: false,
        completionPercentage: 100,
        completesViaStoryline: false,
        completionConfigReadable: true,
      },
    });
    listCourses.mockResolvedValue({ data: [COURSE] });
    publishPackage.mockResolvedValue({ data: {} });
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
    await waitFor(() => expect(openTrialSession).toHaveBeenCalledWith(42));

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
    saveProgress.mockResolvedValue({
      data: { status: "done", courseVerified: true },
    });
    renderTrial();
    await screen.findByTitle(/course/i);

    postFromContent({
      type: MESSAGE_TYPES.FINISH,
      cmi: { "cmi.core.lesson_status": "completed" },
    });

    await waitFor(() => expect(saveProgress).toHaveBeenCalled());
    expect(
      await screen.findByText(/completed — this package can now be published/i),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/now verified and can be published/i),
    ).toBeInTheDocument();
  });

  it("still reaches the verdict when the assignment was already done", async () => {
    // The normal re-export loop: the verifier finished the previous package,
    // so their very first commit of the new run comes back done and nothing
    // about the assignment ever moves again. The stamp arrives twenty minutes
    // later, on the commit that actually finishes the run.
    saveProgress
      .mockResolvedValueOnce({ data: { status: "done" } })
      .mockResolvedValue({ data: { status: "done", courseVerified: true } });
    renderTrial();
    await screen.findByTitle(/course/i);

    postFromContent({
      type: MESSAGE_TYPES.COMMIT,
      cmi: { "cmi.core.lesson_status": "incomplete" },
    });
    await waitFor(() => expect(saveProgress).toHaveBeenCalledTimes(1));
    expect(screen.getByText(/not complete yet/i)).toBeInTheDocument();

    postFromContent({
      type: MESSAGE_TYPES.COMMIT,
      cmi: { "cmi.core.lesson_status": "completed" },
    });

    expect(
      await screen.findByText(/completed — this package can now be published/i),
    ).toBeInTheDocument();
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
    expect(screen.queryByText(/can now be published/i)).not.toBeInTheDocument();
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
      await screen.findByText(/completed — this package can now be published/i),
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
    expect(
      screen.getByText(/unlocks for publishing the moment it reports/),
    ).toBeInTheDocument();
    expect(screen.queryByText(/can now be published/i)).not.toBeInTheDocument();
    expect(
      screen.queryByText(/unlocks for assignment/i),
    ).not.toBeInTheDocument();
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
    expect(screen.queryByText(/can now be published/i)).not.toBeInTheDocument();
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

  it("warns before the run that a trial cannot be picked up later", async () => {
    renderTrial();

    const notice = await screen.findByTestId("trial-no-resume");
    expect(notice).toHaveTextContent(/cannot be resumed/i);
    expect(notice).toHaveTextContent(/from the beginning/i);
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

  it("repeats the server's reason when the trial cannot be started", async () => {
    // The dead end this replaces: an admin who discarded the staged package
    // and reloaded got "Could not start a trial run of this course." and no
    // way to tell whether anything was wrong beyond there being nothing to
    // run. The server already answers the rule that was broken.
    startTrial.mockRejectedValueOnce(
      Object.assign(new Error("refused"), {
        response: {
          status: 409,
          data: {
            message:
              "There is no staged package on this course to run. Upload one first.",
          },
        },
      }),
    );
    renderTrial();

    expect(
      await screen.findByText(/no staged package on this course to run/i),
    ).toBeInTheDocument();
    expect(
      screen.queryByText(/could not start a trial run/i),
    ).not.toBeInTheDocument();
  });

  it("falls back to its own sentence when the failure carries no reason", async () => {
    startTrial.mockRejectedValueOnce(new Error("nope"));
    renderTrial();

    expect(
      await screen.findByText(/could not start a trial run/i),
    ).toBeInTheDocument();
  });

  it("does not promise a replacement when a refused save ends the run", async () => {
    // A trial's package can be gone for two reasons -- replaced by another
    // upload, or discarded -- and after a discard there is no new package to
    // reload onto. The learner page's "run the new one" is true there and
    // false here.
    saveProgress.mockRejectedValue(
      Object.assign(new Error("refused"), { response: { status: 409 } }),
    );
    renderTrial();
    await screen.findByTitle(/course/i);

    postFromContent({
      type: MESSAGE_TYPES.COMMIT,
      cmi: { "cmi.core.lesson_status": "incomplete" },
    });

    const banner = await screen.findByText(/replaced or discarded/i);
    expect(banner).toBeInTheDocument();
    expect(banner.textContent).not.toMatch(/run the new one/i);
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
    expect(await screen.findByTestId("trial-package-notes")).toHaveTextContent(
      /storyline/i,
    );

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

  it("says which package this run is against", async () => {
    renderTrial({
      packageVersion: "qPpo9zHD",
      staged: { packageVersion: "RaOvlxxJ" },
    });

    expect(
      await screen.findByText(/running staged package RaOvlxxJ/),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Learners still see qPpo9zHD."),
    ).toBeInTheDocument();
  });

  it("names the staged and current packages without a version when neither has one", async () => {
    renderTrial({ packageVersion: null, staged: { packageVersion: null } });

    expect(
      await screen.findByText(/running the staged package/),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Learners still see the current package."),
    ).toBeInTheDocument();
  });

  it("says nothing about the live package once the course has none", async () => {
    renderTrial({ liveState: "no_package", packageVersion: null });
    await screen.findByTitle(/course/i);

    expect(screen.queryByText(/Learners still see/)).not.toBeInTheDocument();
  });

  it("offers to publish from the completion banner", async () => {
    renderTrial({ verified: true });

    expect(
      await screen.findByRole("button", { name: "Publish package" }),
    ).toBeInTheDocument();
  });

  it("does not offer to publish while nothing is staged", async () => {
    renderTrial({ verified: true, staged: null });
    await screen.findByTitle(/course/i);

    expect(
      screen.queryByRole("button", { name: "Publish package" }),
    ).not.toBeInTheDocument();
  });

  it("drops the staged package line from the header once publishing succeeds", async () => {
    listCourses
      .mockResolvedValueOnce({
        data: [{ ...COURSE, staged: { packageVersion: "RaOvlxxJ" } }],
      })
      .mockResolvedValueOnce({ data: [{ ...COURSE, staged: null }] });
    renderTrial({ verified: true });

    const trigger = await screen.findByRole("button", {
      name: "Publish package",
    });
    await userEvent.click(trigger);
    const dialog = await screen.findByRole("dialog");
    await userEvent.click(
      within(dialog).getByRole("button", { name: "Publish package" }),
    );

    await waitFor(() => expect(publishPackage).toHaveBeenCalledWith("5"));
    await waitFor(() =>
      expect(
        screen.queryByText(/running staged package/i),
      ).not.toBeInTheDocument(),
    );
    // No navigation, and no new "published" copy invented -- the banner
    // still reads exactly as it did before the publish.
    expect(
      screen.getByText(/completed — this package can now be published/i),
    ).toBeInTheDocument();
  });

  it("reports a failed publish instead of leaving it unhandled", async () => {
    publishPackage.mockRejectedValue(new Error("boom"));
    renderTrial({ verified: true });

    const trigger = await screen.findByRole("button", {
      name: "Publish package",
    });
    await userEvent.click(trigger);
    const dialog = await screen.findByRole("dialog");
    await userEvent.click(
      within(dialog).getByRole("button", { name: "Publish package" }),
    );

    await waitFor(() => expect(publishPackage).toHaveBeenCalled());
    // PublishDialog's own onConfirm handler has no catch of its own; the
    // page must catch the rejection itself or this becomes an unhandled
    // promise rejection. The dialog staying on screen, unclosed, is the
    // visible proof the rejection landed here rather than escaping.
    expect(await screen.findByRole("dialog")).toBeInTheDocument();
  });
});
