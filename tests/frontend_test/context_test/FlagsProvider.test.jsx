import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, act } from "@testing-library/react";
import { useContext } from "react";
import {
  FlagsProvider,
  LDIdentifier,
  FlagsContext,
  ldReactContext as LDReactContext,
} from "@/context/flags";
import { useAuth } from "@/context/auth";

vi.mock("@/context/auth", () => ({
  useAuth: vi.fn(),
}));

/** Reads flags out of FlagsContext on each render and stores into a ref. */
function FlagTracker({ flagsRef, readyRef }) {
  const { flags, ready } = useContext(FlagsContext);
  flagsRef.current = flags;
  if (readyRef) readyRef.current = ready;
  return null;
}

describe("FlagsProvider", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders children", () => {
    const { getByText } = render(
      <FlagsProvider>
        <span>hello</span>
      </FlagsProvider>,
    );
    expect(getByText("hello")).toBeInTheDocument();
  });

  it("provides empty flags initially", () => {
    const flagsRef = { current: null };
    render(
      <FlagsProvider>
        <FlagTracker flagsRef={flagsRef} />
      </FlagsProvider>,
    );
    expect(flagsRef.current).toEqual({});
  });

  it("is not ready before LaunchDarkly has answered", () => {
    const flagsRef = { current: null };
    const readyRef = { current: null };
    render(
      <FlagsProvider>
        <FlagTracker flagsRef={flagsRef} readyRef={readyRef} />
      </FlagsProvider>,
    );
    expect(readyRef.current).toBe(false);
  });
});

describe("LDIdentifier", () => {
  let mockLDClient;

  beforeEach(() => {
    vi.clearAllMocks();
    mockLDClient = {
      identify: vi.fn().mockResolvedValue(undefined),
      allFlags: vi.fn().mockReturnValue({ "manual-submit-meeting": true }),
      on: vi.fn(),
      off: vi.fn(),
    };
    useAuth.mockReturnValue({
      user: {
        sub: "u1",
        email: "a@b.com",
        userId: 1,
        identityType: "external",
      },
    });
  });

  /**
   * Wraps LDIdentifier with LDReactContext.Provider so useLDClient(ldReactContext)
   * returns ldClientValue without needing to mock the SDK.
   */
  function renderLDIdentifier(ldClientValue) {
    const flagsRef = { current: {} };
    const readyRef = { current: null };
    const utils = render(
      <LDReactContext.Provider
        value={{ ldClient: ldClientValue, flags: {}, flagKeyMap: {} }}
      >
        <FlagsProvider>
          <FlagTracker flagsRef={flagsRef} readyRef={readyRef} />
          <LDIdentifier />
        </FlagsProvider>
      </LDReactContext.Provider>,
    );
    return { ...utils, flagsRef, readyRef };
  }

  it("does nothing when ldClient is undefined", () => {
    renderLDIdentifier(undefined);

    expect(mockLDClient.identify).not.toHaveBeenCalled();
  });

  it("does nothing when user is null", () => {
    useAuth.mockReturnValue({ user: null });

    renderLDIdentifier(mockLDClient);

    expect(mockLDClient.identify).not.toHaveBeenCalled();
  });

  it("calls identify with the user's sub, userId, email, and identity_type", async () => {
    useAuth.mockReturnValue({
      user: {
        sub: "azure|123",
        email: "user@example.com",
        userId: 42,
        identityType: "internal",
      },
    });

    await act(async () => {
      renderLDIdentifier(mockLDClient);
    });

    expect(mockLDClient.identify).toHaveBeenCalledWith({
      kind: "user",
      key: "azure|123",
      userId: 42,
      email: "user@example.com",
      identity_type: "internal",
    });
  });

  it("writes allFlags into FlagsContext after identify resolves", async () => {
    let flagsRef;
    await act(async () => {
      ({ flagsRef } = renderLDIdentifier(mockLDClient));
    });

    expect(flagsRef.current).toEqual({ "manual-submit-meeting": true });
  });

  it("is ready once identify resolves", async () => {
    let resolveIdentify;
    mockLDClient.identify.mockReturnValue(
      new Promise((resolve) => {
        resolveIdentify = resolve;
      }),
    );
    let readyRef;
    await act(async () => {
      ({ readyRef } = renderLDIdentifier(mockLDClient));
    });
    expect(readyRef.current).toBe(false);

    await act(async () => resolveIdentify());

    expect(readyRef.current).toBe(true);
  });

  it("is ready with no flags when identify fails, and logs the failure", async () => {
    // Without settling on failure every flag-gated page would wait forever.
    const consoleError = vi
      .spyOn(console, "error")
      .mockImplementation(() => {});
    const failure = new Error("LaunchDarkly unreachable");
    mockLDClient.identify.mockRejectedValue(failure);

    let flagsRef, readyRef;
    await act(async () => {
      ({ flagsRef, readyRef } = renderLDIdentifier(mockLDClient));
    });

    expect(readyRef.current).toBe(true);
    expect(flagsRef.current).toEqual({});
    expect(consoleError).toHaveBeenCalledWith(expect.any(String), failure);
    consoleError.mockRestore();
  });

  it("subscribes to LD change events after identify", async () => {
    await act(async () => {
      renderLDIdentifier(mockLDClient);
    });

    expect(mockLDClient.on).toHaveBeenCalledWith(
      "change",
      expect.any(Function),
    );
  });

  it("updates FlagsContext when a change event fires", async () => {
    let flagsRef;
    await act(async () => {
      ({ flagsRef } = renderLDIdentifier(mockLDClient));
    });

    mockLDClient.allFlags.mockReturnValue({ "manual-submit-meeting": false });
    const changeHandler = mockLDClient.on.mock.calls[0][1];
    act(() => changeHandler());

    expect(flagsRef.current).toEqual({ "manual-submit-meeting": false });
  });

  it("removes the change listener on unmount", async () => {
    let unmount;
    await act(async () => {
      ({ unmount } = renderLDIdentifier(mockLDClient));
    });

    const registeredHandler = mockLDClient.on.mock.calls[0][1];
    unmount();

    expect(mockLDClient.off).toHaveBeenCalledWith("change", registeredHandler);
  });
});
