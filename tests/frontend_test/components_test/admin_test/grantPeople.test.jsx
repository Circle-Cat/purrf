import { describe, it, expect } from "vitest";
import { actorLabel } from "@/pages/AdminPermissions/utils/grantPeople";
import { legalName } from "@/utils/userName";

describe("legalName", () => {
  it("is the legal name, and never the preferred one", () => {
    expect(
      legalName({ firstName: "Zhao", lastName: "Min", preferredName: "Min" }),
    ).toBe("Zhao Min");
  });

  it("is empty for a missing person", () => {
    expect(legalName(undefined)).toBe("");
    expect(legalName(null)).toBe("");
  });
});

describe("actorLabel", () => {
  it("names the actor when resolved", () => {
    expect(actorLabel({ firstName: "Wang", lastName: "Yanpei" }, 9)).toBe(
      "Wang Yanpei",
    );
  });

  it("keeps the id when the account is gone, rather than hiding it", () => {
    expect(actorLabel(null, 9)).toBe("User 9");
  });

  it("shows an em dash only when there was no actor at all", () => {
    expect(actorLabel(null, null)).toBe("—");
  });
});
