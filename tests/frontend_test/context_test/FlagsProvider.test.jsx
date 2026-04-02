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
function FlagTracker({ flagsRef }) {
  const { flags } = useContext(FlagsContext);
  flagsRef.current = flags;
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
      user: { sub: "u1", email: "a@b.com" },
      roles: [],
    });
  });

  /**
   * Wraps LDIdentifier with LDReactContext.Provider so useLDClient(ldReactContext)
   * returns ldClientValue without needing to mock the SDK.
   */
  function renderLDIdentifier(ldClientValue) {
    const flagsRef = { current: {} };
    const utils = render(
      <LDReactContext.Provider
        value={{ ldClient: ldClientValue, flags: {}, flagKeyMap: {} }}
      >
        <FlagsProvider>
          <FlagTracker flagsRef={flagsRef} />
          <LDIdentifier />
        </FlagsProvider>
      </LDReactContext.Provider>,
    );
    return { ...utils, flagsRef };
  }

  it("does nothing when ldClient is undefined", () => {
    renderLDIdentifier(undefined);

    expect(mockLDClient.identify).not.toHaveBeenCalled();
  });

  it("does nothing when user is null", () => {
    useAuth.mockReturnValue({ user: null, roles: [] });

    renderLDIdentifier(mockLDClient);

    expect(mockLDClient.identify).not.toHaveBeenCalled();
  });

  it("calls identify with the user's sub, email, and roles", async () => {
    useAuth.mockReturnValue({
      user: { sub: "azure|123", email: "user@example.com" },
      roles: ["cc_internal"],
    });

    await act(async () => {
      renderLDIdentifier(mockLDClient);
    });

    expect(mockLDClient.identify).toHaveBeenCalledWith({
      kind: "user",
      key: "azure|123",
      email: "user@example.com",
      roles: ["cc_internal"],
    });
  });

  it("defaults roles to [] when roles is undefined", async () => {
    useAuth.mockReturnValue({
      user: { sub: "u1", email: "a@b.com" },
      roles: undefined,
    });

    await act(async () => {
      renderLDIdentifier(mockLDClient);
    });

    expect(mockLDClient.identify).toHaveBeenCalledWith(
      expect.objectContaining({ roles: [] }),
    );
  });

  it("writes allFlags into FlagsContext after identify resolves", async () => {
    let flagsRef;
    await act(async () => {
      ({ flagsRef } = renderLDIdentifier(mockLDClient));
    });

    expect(flagsRef.current).toEqual({ "manual-submit-meeting": true });
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
