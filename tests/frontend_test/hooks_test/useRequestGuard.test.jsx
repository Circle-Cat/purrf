import { describe, it, expect } from "vitest";
import { renderHook } from "@testing-library/react";
import { useRequestGuard } from "@/hooks/useRequestGuard";

describe("useRequestGuard", () => {
  it("issues monotonically increasing request ids", () => {
    const { result } = renderHook(() => useRequestGuard());
    const a = result.current.begin();
    const b = result.current.begin();
    expect(b).toBeGreaterThan(a);
  });

  it("treats only the latest issued id as current", () => {
    const { result } = renderHook(() => useRequestGuard());
    const first = result.current.begin();
    const second = result.current.begin();
    expect(result.current.isCurrent(second)).toBe(true);
    expect(result.current.isCurrent(first)).toBe(false);
  });

  it("treats nothing as current after unmount", () => {
    const { result, unmount } = renderHook(() => useRequestGuard());
    const seq = result.current.begin();
    expect(result.current.isCurrent(seq)).toBe(true);
    unmount();
    expect(result.current.isCurrent(seq)).toBe(false);
  });

  it("keeps begin/isCurrent identities stable across rerenders", () => {
    const { result, rerender } = renderHook(() => useRequestGuard());
    const first = result.current;
    rerender();
    expect(result.current.begin).toBe(first.begin);
    expect(result.current.isCurrent).toBe(first.isCurrent);
  });
});
