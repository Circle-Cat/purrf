import { describe, it, expect } from "vitest";
import { registrationWindowLabel } from "@/pages/MentorshipManagement/utils/registrationWindow";

describe("registrationWindowLabel", () => {
  it("gives the window in Los Angeles dates", () => {
    // 07:00 UTC on the 21st is still the 21st in Los Angeles; 03:00 UTC on
    // the 1st would be the 31st there.
    expect(
      registrationWindowLabel({
        timeline: {
          promotionStartAt: "2026-09-01T03:00:00Z",
          onboardingDeadlineAt: "2026-09-21T07:00:00Z",
        },
      }),
    ).toBe("Registration: 2026-08-31 to 2026-09-21");
  });

  it("says when the round has no window", () => {
    expect(registrationWindowLabel({ timeline: {} })).toBe(
      "This round has no registration period set.",
    );
  });
});
