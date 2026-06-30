import { describe, it, expect } from "vitest";
import { partnerDisplayName } from "@/utils/partnerName";

describe("partnerDisplayName", () => {
  it("uses the preferred name when present", () => {
    expect(
      partnerDisplayName({
        preferredName: "Ali",
        firstName: "Alice",
        lastName: "Anderson",
      }),
    ).toBe("Ali");
  });

  it("falls back to the full name when preferred name is missing", () => {
    expect(
      partnerDisplayName({
        preferredName: "",
        firstName: "Alice",
        lastName: "Anderson",
      }),
    ).toBe("Alice Anderson");
  });

  it("falls back to the full name when preferred name is null", () => {
    expect(
      partnerDisplayName({
        preferredName: null,
        firstName: "Alice",
        lastName: "Anderson",
      }),
    ).toBe("Alice Anderson");
  });

  it("trims whitespace and tolerates a missing last name", () => {
    expect(
      partnerDisplayName({ firstName: "Alice", lastName: undefined }),
    ).toBe("Alice");
  });

  it("returns an empty string when given nothing", () => {
    expect(partnerDisplayName(undefined)).toBe("");
  });
});
