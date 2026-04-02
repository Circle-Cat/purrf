import { describe, it, expect } from "vitest";
import { renderHook } from "@testing-library/react";
import { useFeatureFlags } from "@/hooks/useFeatureFlags";
import { FlagsContext } from "@/context/flags";

describe("useFeatureFlags", () => {
  it("returns empty object when no flags are in context", () => {
    const { result } = renderHook(() => useFeatureFlags());
    expect(result.current).toEqual({});
  });

  it("returns flags provided by FlagsContext", () => {
    const flags = { "manual-submit-meeting": true };
    const wrapper = ({ children }) => (
      <FlagsContext.Provider value={{ flags, setFlags: () => {} }}>
        {children}
      </FlagsContext.Provider>
    );

    const { result } = renderHook(() => useFeatureFlags(), { wrapper });

    expect(result.current).toEqual(flags);
  });

  it("returns updated flags when context value changes", () => {
    const initial = { "manual-submit-meeting": false };
    let flags = initial;
    const wrapper = ({ children }) => (
      <FlagsContext.Provider value={{ flags, setFlags: () => {} }}>
        {children}
      </FlagsContext.Provider>
    );

    const { result, rerender } = renderHook(() => useFeatureFlags(), {
      wrapper,
    });
    expect(result.current).toEqual({ "manual-submit-meeting": false });

    flags = { "manual-submit-meeting": true };
    rerender();
    expect(result.current).toEqual({ "manual-submit-meeting": true });
  });
});
