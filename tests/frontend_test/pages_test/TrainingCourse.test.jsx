import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import TrainingCourse from "@/pages/TrainingCourse";
import { MESSAGE_TYPES } from "@/training/scormBridge";

vi.mock("@/api/trainingApi", () => ({
  openSession: vi.fn(),
  saveProgress: vi.fn(),
}));
vi.mock("@/context/auth", () => ({
  useAuth: vi.fn(),
}));

import { openSession, saveProgress } from "@/api/trainingApi";
import { useAuth } from "@/context/auth";

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

const postCommit = (cmi) =>
  window.dispatchEvent(
    new MessageEvent("message", {
      origin: "https://test-training-content.purrf.io",
      data: { type: MESSAGE_TYPES.COMMIT, cmi },
    }),
  );

const SESSION = {
  data: {
    contentBaseUrl: "https://test-training-content.purrf.io/p/tok/",
    entryPath: "scormdriver/indexAPI.html",
    playerPath: "__player.html",
    expiresAt: 1788400000,
    progress: null,
  },
};

describe("TrainingCourse", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    openSession.mockResolvedValue(SESSION);
    saveProgress.mockResolvedValue({});
    useAuth.mockReturnValue({
      user: { userId: 7, email: "alice@example.com" },
    });
    // The unload save goes around axios on purpose (see TrainingCourse.jsx),
    // so it is observed here at the fetch seam instead of through the
    // trainingApi mock.
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true }));
  });

  afterEach(() => {
    vi.unstubAllGlobals();
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

    // Waited in two stages rather than one. The banner is three awaits away
    // from the dispatch -- the rejected save, the state update, the render --
    // and under the full suite's parallel load that overran a single default
    // budget. Each stage also says which of the three did not happen.
    await waitFor(() => expect(saveProgress).toHaveBeenCalled());
    expect(await screen.findByText(/could not be saved/i)).toBeInTheDocument();
  });

  it("logs a scorm:error from the player instead of dropping it", async () => {
    const consoleError = vi
      .spyOn(console, "error")
      .mockImplementation(() => {});
    renderCourse();
    await screen.findByTitle(/course/i);

    window.dispatchEvent(
      new MessageEvent("message", {
        origin: "https://test-training-content.purrf.io",
        data: { type: "scorm:error", code: 101, message: "General exception" },
      }),
    );

    await waitFor(() =>
      expect(consoleError).toHaveBeenCalledWith(
        expect.stringContaining("42"),
        expect.objectContaining({ code: 101, message: "General exception" }),
      ),
    );
    consoleError.mockRestore();
  });

  it("ignores a scorm:error forged by any other page", async () => {
    const consoleError = vi
      .spyOn(console, "error")
      .mockImplementation(() => {});
    renderCourse();
    await screen.findByTitle(/course/i);

    window.dispatchEvent(
      new MessageEvent("message", {
        origin: "https://evil.example",
        data: { type: "scorm:error", code: 101, message: "forged" },
      }),
    );

    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(consoleError).not.toHaveBeenCalled();
    consoleError.mockRestore();
  });

  it("says so when the course has no package to open", async () => {
    openSession.mockRejectedValue({ response: { status: 404 } });

    renderCourse();

    expect(await screen.findByText(/not available/i)).toBeInTheDocument();
  });

  it("replies to a trusted READY with the stored progress, the learner, and the entry path", async () => {
    const progress = {
      lessonStatus: "incomplete",
      lessonLocation: "3",
      suspendData: "blob",
      sessionTimeSeconds: 42,
    };
    openSession.mockResolvedValue({ data: { ...SESSION.data, progress } });
    renderCourse();
    const frame = await screen.findByTitle(/course/i);
    const postMessage = vi.spyOn(frame.contentWindow, "postMessage");

    window.dispatchEvent(
      new MessageEvent("message", {
        origin: "https://test-training-content.purrf.io",
        data: { type: MESSAGE_TYPES.READY },
      }),
    );

    await waitFor(() => expect(postMessage).toHaveBeenCalled());
    const [message, targetOrigin] = postMessage.mock.calls.at(-1);
    expect(message).toEqual({
      type: MESSAGE_TYPES.INIT,
      progress,
      learner: { userId: 7, displayName: "alice@example.com" },
      entryPath: SESSION.data.entryPath,
    });
    // Must go to the content origin specifically -- never a wildcard, and
    // never back to our own origin.
    expect(targetOrigin).toBe("https://test-training-content.purrf.io");
    expect(targetOrigin).not.toBe("*");
    expect(targetOrigin).not.toBe(window.location.origin);
  });

  it("ignores a READY forged by any other page", async () => {
    renderCourse();
    const frame = await screen.findByTitle(/course/i);
    const postMessage = vi.spyOn(frame.contentWindow, "postMessage");

    window.dispatchEvent(
      new MessageEvent("message", {
        origin: "https://evil.example",
        data: { type: MESSAGE_TYPES.READY },
      }),
    );

    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(postMessage).not.toHaveBeenCalled();
  });

  it("still replies to READY with an empty progress object, not undefined, when nobody has opened the course yet", async () => {
    // SESSION carries `progress: null` -- what the API sends for an
    // assignment nobody has opened.
    renderCourse();
    const frame = await screen.findByTitle(/course/i);
    const postMessage = vi.spyOn(frame.contentWindow, "postMessage");

    window.dispatchEvent(
      new MessageEvent("message", {
        origin: "https://test-training-content.purrf.io",
        data: { type: MESSAGE_TYPES.READY },
      }),
    );

    await waitFor(() => expect(postMessage).toHaveBeenCalled());
    const [message] = postMessage.mock.calls.at(-1);
    expect(message.progress).toEqual({});
  });

  it("saves what it last received when the tab goes away, over a keepalive fetch rather than axios", async () => {
    renderCourse();
    await screen.findByTitle(/course/i);
    postCommit({ "cmi.suspend_data": "blob" });
    // A generous timeout on this first stage, not the assertion, is what
    // needs raising: under the full suite's parallel load the default 1000ms
    // budget can elapse before the mocked save even resolves once.
    await waitFor(() => expect(saveProgress).toHaveBeenCalledTimes(1), {
      timeout: 3000,
    });
    // The ordinary commit save never touches fetch -- only unload does.
    expect(fetch).not.toHaveBeenCalled();

    window.dispatchEvent(new Event("beforeunload"));

    await waitFor(() => expect(fetch).toHaveBeenCalledTimes(1));
    const [url, options] = fetch.mock.calls[0];
    expect(url).toBe("/api/training/42/progress");
    expect(options).toMatchObject({
      method: "POST",
      credentials: "include",
      keepalive: true,
    });
    // final: the server skips a save whose content matches what it stored,
    // and this one always does -- the elapsed time it banks is the one thing
    // that comparison leaves out.
    expect(JSON.parse(options.body)).toEqual({
      cmi: { "cmi.suspend_data": "blob" },
      final: true,
    });
    // Unload does not also re-trigger the axios save.
    expect(saveProgress).toHaveBeenCalledTimes(1);
  });

  it("does not save on unload when nothing new arrived", async () => {
    renderCourse();
    await screen.findByTitle(/course/i);

    window.dispatchEvent(new Event("beforeunload"));

    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(fetch).not.toHaveBeenCalled();
  });

  it("stops listening for unload when it goes away", async () => {
    const { unmount } = renderCourse();
    await screen.findByTitle(/course/i);
    postCommit({ "cmi.suspend_data": "blob" });
    await waitFor(() => expect(saveProgress).toHaveBeenCalledTimes(1), {
      timeout: 3000,
    });
    unmount();

    window.dispatchEvent(new Event("beforeunload"));

    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(fetch).not.toHaveBeenCalled();
  });
});
