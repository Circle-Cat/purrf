import { describe, test, expect } from "vitest";
import { isBannerEnv } from "@/utils/deployEnv";

describe("isBannerEnv", () => {
  test.each([
    ["staging", true],
    ["test", true],
    ["prod", false],
    ["", false],
    [undefined, false],
    ["STAGING", false],
  ])("isBannerEnv(%p) === %p", (env, expected) => {
    expect(isBannerEnv(env)).toBe(expected);
  });
});
