import { describe, it, expect } from "vitest";
import { toLDContext } from "@/context/flags";

describe("toLDContext", () => {
  it("maps the user onto a LaunchDarkly user context keyed by sub", () => {
    expect(
      toLDContext({
        sub: "google-oauth2|7",
        userId: 7,
        email: "seven@example.com",
        identityType: "external",
      }),
    ).toEqual({
      kind: "user",
      key: "google-oauth2|7",
      userId: 7,
      email: "seven@example.com",
      identity_type: "external",
    });
  });
});
