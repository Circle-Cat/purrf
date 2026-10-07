import { describe, it, expect } from "vitest";
import {
  approvalActionLabel,
  approvalPersonLabel,
  approvalReviewLink,
} from "@/pages/MentorshipManagement/utils/approvalLabels";

describe("approvalLabels", () => {
  it("labels each action, and anything else plainly", () => {
    expect(approvalActionLabel("publish_matching")).toBe(
      "Publish matching result",
    );
    expect(approvalActionLabel("exempt_matching")).toBe("Matching exemption");
    expect(approvalActionLabel("job_review")).toBe("Approval");
  });

  it("names a person, or gives their id when the name did not resolve", () => {
    expect(approvalPersonLabel({ userId: 8, name: "Rae Kim" })).toBe("Rae Kim");
    expect(approvalPersonLabel({ userId: 8, name: null })).toBe("ID 8");
    expect(approvalPersonLabel(null)).toBe("");
  });

  it("reviews a publish request on the round's matching results", () => {
    expect(
      approvalReviewLink({ action: "publish_matching", round: { roundId: 7 } }),
    ).toEqual({ pathname: "/mentorship-management/matching/7", search: "" });
  });

  it("reviews an exemption on the Needs exemption list, narrowed to the person", () => {
    const link = approvalReviewLink({
      action: "exempt_matching",
      round: { roundId: 7 },
      person: { userId: 21 },
    });

    expect(link.pathname).toBe("/mentorship-management");
    expect(Object.fromEntries(new URLSearchParams(link.search))).toEqual({
      round: "7",
      needsExemption: "1",
      id: "21",
    });
  });
});
