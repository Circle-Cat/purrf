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

// The envelope the session endpoint sends for an assignment nobody has
// opened yet: progress is null, not an empty object.
const SESSION = {
  contentBaseUrl: `${CONTENT_ORIGIN}/packages/1/`,
  sessionToken: "signed.token",
  entryPath: "index.html",
  playerPath: "player.html",
  expiresAt: 1788400000,
  progress: null,
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

describe("useTrainingRuntime parting save", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.saveProgress.mockResolvedValue({});
    setVisibility("visible");
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  /** jsdom leaves visibilityState read-only, so it is redefined per test. */
  const setVisibility = (state) => {
    Object.defineProperty(document, "visibilityState", {
      configurable: true,
      get: () => state,
    });
  };

  const unload = () => {
    act(() => {
      window.dispatchEvent(new Event("pagehide"));
    });
  };

  const hide = () => {
    setVisibility("hidden");
    act(() => {
      document.dispatchEvent(new Event("visibilitychange"));
    });
  };

  const show = () => {
    setVisibility("visible");
    act(() => {
      document.dispatchEvent(new Event("visibilitychange"));
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
      sessionToken: "signed.token",
    });
  });

  it("names the content session on every save it posts", async () => {
    // A finishing status can only vouch for a package when the server can
    // tell which run reported it, and the run the token names is signed.
    api.saveProgress.mockResolvedValue({});
    await renderRuntime();

    await act(async () => {
      window.dispatchEvent(commit(cmiWith("incomplete")));
    });

    expect(api.saveProgress.mock.calls[0][1].sessionToken).toBe("signed.token");
  });

  it("reports the course verified when the save that finished it says so", async () => {
    // The assignment's own status cannot stand in for this: a verifier
    // re-running a replaced package is already DONE, so nothing moves.
    api.saveProgress.mockResolvedValue({
      data: { status: "done", courseVerified: true },
    });
    const { result } = await renderRuntime();

    await act(async () => {
      window.dispatchEvent(commit(cmiWith("completed")));
    });

    await waitFor(() => expect(result.current.courseVerified).toBe(true));
  });

  it("leaves the course unverified when a save says nothing about it", async () => {
    api.saveProgress.mockResolvedValue({ data: { status: "done" } });
    const { result } = await renderRuntime();

    await act(async () => {
      window.dispatchEvent(commit(cmiWith("completed")));
    });

    await waitFor(() => expect(api.saveProgress).toHaveBeenCalled());
    expect(result.current.courseVerified).toBe(false);
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

  it("banks the session when the page is hidden, which is all iOS gives us", async () => {
    // Mobile Safari never fires beforeunload; hiding the tab is the last
    // event the page is guaranteed to see.
    const fetchMock = vi.fn(() => Promise.resolve({ ok: true }));
    vi.stubGlobal("fetch", fetchMock);
    await renderRuntime();
    await act(async () => {
      window.dispatchEvent(commit(cmiWith("incomplete")));
    });

    hide();

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({
      cmi: cmiWith("incomplete"),
      final: true,
      sessionToken: "signed.token",
    });
  });

  it("ignores the page coming back into view", async () => {
    const fetchMock = vi.fn(() => Promise.resolve({ ok: true }));
    vi.stubGlobal("fetch", fetchMock);
    await renderRuntime();
    await act(async () => {
      window.dispatchEvent(commit(cmiWith("incomplete")));
    });
    hide();

    show();

    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("sends one save however often a learner switches apps", async () => {
    // Nothing new has been committed between the switches, so there is
    // nothing left to bank.
    const fetchMock = vi.fn(() => Promise.resolve({ ok: true }));
    vi.stubGlobal("fetch", fetchMock);
    await renderRuntime();
    await act(async () => {
      window.dispatchEvent(commit(cmiWith("incomplete")));
    });

    hide();
    show();
    hide();
    show();
    hide();

    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("saves again once the course has committed something new", async () => {
    const fetchMock = vi.fn(() => Promise.resolve({ ok: true }));
    vi.stubGlobal("fetch", fetchMock);
    await renderRuntime();
    await act(async () => {
      window.dispatchEvent(commit(cmiWith("incomplete")));
    });
    hide();
    show();

    await act(async () => {
      window.dispatchEvent(commit(cmiWith("completed")));
    });
    hide();

    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(JSON.parse(fetchMock.mock.calls[1][1].body).cmi).toEqual(
      cmiWith("completed"),
    );
  });

  it("no longer leans on beforeunload, which iOS never fires", async () => {
    const fetchMock = vi.fn(() => Promise.resolve({ ok: true }));
    vi.stubGlobal("fetch", fetchMock);
    await renderRuntime();
    await act(async () => {
      window.dispatchEvent(commit(cmiWith("incomplete")));
    });

    act(() => {
      window.dispatchEvent(new Event("beforeunload"));
    });

    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("drops suspend_data from the parting save rather than exceeding keepalive", async () => {
    // fetch refuses a keepalive body over 64 KiB, and the server's own cap on
    // suspend_data is exactly 65536 -- so the save that exists to bank elapsed
    // time would throw every time for a learner near that cap.
    const huge = {
      ...cmiWith("incomplete"),
      "cmi.suspend_data": "x".repeat(65536),
      "cmi.core.total_time": "01:00:00",
    };
    const fetchMock = vi.fn(() => Promise.resolve({ ok: true }));
    vi.stubGlobal("fetch", fetchMock);
    await renderRuntime();
    await act(async () => {
      window.dispatchEvent(commit(huge));
    });

    unload();

    const [, init] = fetchMock.mock.calls[0];
    expect(new Blob([init.body]).size).toBeLessThan(60 * 1024);
    const body = JSON.parse(init.body);
    expect(body.final).toBe(true);
    expect(body.cmi["cmi.core.total_time"]).toBe("01:00:00");
    expect(body.cmi).not.toHaveProperty("cmi.suspend_data");
  });
});

describe("useTrainingRuntime and a run the server no longer serves", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  const refusal = (status) =>
    Object.assign(new Error("refused"), { response: { status } });

  it("marks the session stale when a save is refused as a replaced package", async () => {
    // 409 is what the server answers a commit whose run names a package it
    // has stopped serving. Telling this learner to keep the tab open would
    // leave them on a page that can never save again.
    api.saveProgress.mockRejectedValue(refusal(409));
    const { result } = await renderRuntime();

    await act(async () => {
      window.dispatchEvent(commit(cmiWith("incomplete")));
    });

    await waitFor(() => expect(result.current.sessionStale).toBe(true));
  });

  it("leaves an ordinary save failure retryable", async () => {
    api.saveProgress.mockRejectedValue(refusal(500));
    const { result } = await renderRuntime();

    await act(async () => {
      window.dispatchEvent(commit(cmiWith("incomplete")));
    });

    await waitFor(() => expect(result.current.saveFailed).toBe(true));
    expect(result.current.sessionStale).toBe(false);
  });
});
