import { describe, it, expect } from "vitest";
import { userDisplayName } from "@/utils/userName";

describe("userDisplayName", () => {
  it("uses the preferred name when present", () => {
    expect(
      userDisplayName({
        preferredName: "Ali",
        firstName: "Alice",
        lastName: "Anderson",
      }),
    ).toBe("Ali");
  });

  it("falls back to the full name when preferred name is missing", () => {
    expect(
      userDisplayName({
        preferredName: "",
        firstName: "Alice",
        lastName: "Anderson",
      }),
    ).toBe("Alice Anderson");
  });

  it("falls back to the full name when preferred name is null", () => {
    expect(
      userDisplayName({
        preferredName: null,
        firstName: "Alice",
        lastName: "Anderson",
      }),
    ).toBe("Alice Anderson");
  });

  it("trims whitespace and tolerates a missing last name", () => {
    expect(userDisplayName({ firstName: "Alice", lastName: undefined })).toBe(
      "Alice",
    );
  });

  it("returns an empty string when given nothing", () => {
    expect(userDisplayName(undefined)).toBe("");
  });
});
