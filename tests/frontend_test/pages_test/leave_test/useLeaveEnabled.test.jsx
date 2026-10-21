import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook } from "@testing-library/react";

import { useLeaveEnabled } from "@/pages/Leave/hooks/useLeaveEnabled";
import { useFeatureFlags } from "@/hooks/useFeatureFlags";
import { FlagsContext } from "@/context/flags";
import { FEATURE_FLAGS } from "@/constants/FeatureFlags";

vi.mock("@/hooks/useFeatureFlags", () => ({ useFeatureFlags: vi.fn() }));

const withReady =
  (ready) =>
  ({ children }) => (
    <FlagsContext.Provider value={{ flags: {}, setFlags: () => {}, ready }}>
      {children}
    </FlagsContext.Provider>
  );

describe("useLeaveEnabled", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("is off and not ready until LaunchDarkly has answered", () => {
    // Flag values start as an empty map. Off is the safe direction for
    // something unreleased: the cost is a card appearing a moment late,
    // against it appearing to everybody if the SDK never answers.
    useFeatureFlags.mockReturnValue({});

    const { result } = renderHook(() => useLeaveEnabled(), {
      wrapper: withReady(false),
    });

    expect(result.current).toEqual({ isEnabled: false, isReady: false });
  });

  it("is off when the flag says so", () => {
    useFeatureFlags.mockReturnValue({
      [FEATURE_FLAGS.LEAVE_MANAGEMENT]: false,
    });

    const { result } = renderHook(() => useLeaveEnabled(), {
      wrapper: withReady(true),
    });

    expect(result.current).toEqual({ isEnabled: false, isReady: true });
  });

  it("is on when the flag says so", () => {
    useFeatureFlags.mockReturnValue({ [FEATURE_FLAGS.LEAVE_MANAGEMENT]: true });

    const { result } = renderHook(() => useLeaveEnabled(), {
      wrapper: withReady(true),
    });

    expect(result.current).toEqual({ isEnabled: true, isReady: true });
  });
});
