import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { act, renderHook, waitFor } from "@testing-library/react";
import useTrainingRuntime from "@/hooks/useTrainingRuntime";
import * as api from "@/api/trainingApi";
import { MESSAGE_TYPES } from "@/training/scormBridge";

vi.mock("@/api/trainingApi");
vi.mock("@/utils/request", () => ({
  default: { defaults: { baseURL: "https://api.test" } },
}));

const TRAINING_ID = 7;
const CONTENT_ORIGIN = "https://content.test";

const SESSION = {
  contentBaseUrl: `${CONTENT_ORIGIN}/packages/1/`,
  entryPath: "index.html",
  playerPath: "player.html",
  progress: {},
};

const cmiWith = (lessonStatus) => ({
  "cmi.core.lesson_status": lessonStatus,
  "cmi.core.total_time": "00:10:00",
});

const commit = (cmi) =>
  new MessageEvent("message", {
    data: { type: MESSAGE_TYPES.COMMIT, cmi },
    origin: CONTENT_ORIGIN,
  });

/** A promise the test decides when to settle. */
const deferred = () => {
  let resolve;
  let reject;
  const promise = new Promise((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
};

const renderRuntime = async () => {
  api.openSession.mockResolvedValue({ data: SESSION });
  const rendered = renderHook(() =>
    useTrainingRuntime(TRAINING_ID, { userId: 1, email: "learner@test" }),
  );
  await waitFor(() => expect(rendered.result.current.session).not.toBeNull());
  return rendered;
};

describe("useTrainingRuntime saves", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("keeps one save per assignment on the wire at a time", async () => {
    // The mentor course reports `incomplete` and then `completed` within the
    // same second. Overlapping, each request decides the assignment's next
    // status from a read the other has not written to yet.
    const inFlight = deferred();
    api.saveProgress
      .mockReturnValueOnce(inFlight.promise)
      .mockResolvedValue({});
    await renderRuntime();

    await act(async () => {
      window.dispatchEvent(commit(cmiWith("incomplete")));
      window.dispatchEvent(commit(cmiWith("completed")));
    });

    expect(api.saveProgress).toHaveBeenCalledTimes(1);
  });

  it("sends the save it held back once the one before it lands", async () => {
    const inFlight = deferred();
    api.saveProgress
      .mockReturnValueOnce(inFlight.promise)
      .mockResolvedValue({});
    await renderRuntime();
    await act(async () => {
      window.dispatchEvent(commit(cmiWith("incomplete")));
      window.dispatchEvent(commit(cmiWith("completed")));
    });

    await act(async () => {
      inFlight.resolve({});
    });

    await waitFor(() => expect(api.saveProgress).toHaveBeenCalledTimes(2));
    expect(api.saveProgress.mock.calls[1][1].cmi).toEqual(cmiWith("completed"));
  });

  it("goes on saving after a save fails", async () => {
    api.saveProgress
      .mockRejectedValueOnce(new Error("network"))
      .mockResolvedValue({});
    const { result } = await renderRuntime();

    await act(async () => {
      window.dispatchEvent(commit(cmiWith("incomplete")));
    });
    await waitFor(() => expect(result.current.saveFailed).toBe(true));
    await act(async () => {
      window.dispatchEvent(commit(cmiWith("completed")));
    });

    await waitFor(() => expect(result.current.saveFailed).toBe(false));
    expect(api.saveProgress).toHaveBeenCalledTimes(2);
  });
});

describe("useTrainingRuntime unload save", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.saveProgress.mockResolvedValue({});
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  const unload = () => {
    act(() => {
      window.dispatchEvent(new Event("beforeunload"));
    });
  };

  it("marks the parting save final so the server writes it", async () => {
    // It resends the cmi the last commit already stored, so the content
    // matches and the server would otherwise skip it -- and the elapsed time
    // it exists to bank is exactly what the content comparison ignores.
    const fetchMock = vi.fn(() => Promise.resolve({ ok: true }));
    vi.stubGlobal("fetch", fetchMock);
    await renderRuntime();
    await act(async () => {
      window.dispatchEvent(commit(cmiWith("incomplete")));
    });

    unload();

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("https://api.test/training/7/progress");
    expect(init.keepalive).toBe(true);
    expect(JSON.parse(init.body)).toEqual({
      cmi: cmiWith("incomplete"),
      final: true,
    });
  });

  it("sends nothing when no commit is owed", async () => {
    const fetchMock = vi.fn(() => Promise.resolve({ ok: true }));
    vi.stubGlobal("fetch", fetchMock);
    await renderRuntime();

    unload();

    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("says so when the parting save does not go out", async () => {
    const fetchMock = vi.fn(() => Promise.reject(new Error("offline")));
    vi.stubGlobal("fetch", fetchMock);
    const consoleError = vi
      .spyOn(console, "error")
      .mockImplementation(() => {});
    await renderRuntime();
    await act(async () => {
      window.dispatchEvent(commit(cmiWith("incomplete")));
    });

    unload();

    await waitFor(() => expect(consoleError).toHaveBeenCalled());
  });

  it("still owes the save after a failed one, so a cancelled close retries", async () => {
    const fetchMock = vi.fn(() => Promise.reject(new Error("offline")));
    vi.stubGlobal("fetch", fetchMock);
    const consoleError = vi
      .spyOn(console, "error")
      .mockImplementation(() => {});
    await renderRuntime();
    await act(async () => {
      window.dispatchEvent(commit(cmiWith("incomplete")));
    });
    unload();
    await waitFor(() => expect(consoleError).toHaveBeenCalled());

    unload();

    expect(fetchMock).toHaveBeenCalledTimes(2);
  });
});
