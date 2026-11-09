import { describe, test, expect, afterEach } from "vitest";
import { renderHook, cleanup } from "@testing-library/react";

import { GuideContext, useGuides } from "@/guides/GuideContext";

describe("useGuides", () => {
  afterEach(() => {
    cleanup();
  });

  test("is inactive with a no-op start outside a provider", () => {
    const { result } = renderHook(() => useGuides());

    expect(result.current.active).toBe(false);
    expect(() => result.current.start("welcome")).not.toThrow();
  });

  test("returns the provider's value", () => {
    const value = { active: true, start: () => {} };
    const { result } = renderHook(() => useGuides(), {
      wrapper: ({ children }) => (
        <GuideContext.Provider value={value}>{children}</GuideContext.Provider>
      ),
    });

    expect(result.current).toBe(value);
  });
});
