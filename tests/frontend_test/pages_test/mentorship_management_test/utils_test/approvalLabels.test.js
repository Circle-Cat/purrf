import { describe, it, expect } from "vitest";
import {
  approvalActionLabel,
  approvalPairLabel,
  approvalPersonLabel,
  approvalReviewLink,
  exemptionWhyLines,
} from "@/pages/MentorshipManagement/utils/approvalLabels";

describe("approvalLabels", () => {
  it("labels each action, and anything else plainly", () => {
    expect(approvalActionLabel("publish_matching")).toBe(
      "Publish matching result",
    );
    expect(approvalActionLabel("exempt_matching")).toBe("Matching exemption");
    expect(approvalActionLabel("withdraw_participant")).toBe(
      "Withdrawal from round",
    );
    expect(approvalActionLabel("mark_no_show")).toBe("No show mark");
    expect(approvalActionLabel("mark_red_flag")).toBe("Red flag");
    expect(approvalActionLabel("end_pair")).toBe("End pair");
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

  it("reviews a withdrawal on the person's page for the round", () => {
    const link = approvalReviewLink({
      action: "withdraw_participant",
      round: { roundId: 7 },
      person: { userId: 3104 },
    });

    expect(link).toEqual({
      pathname: "/mentorship-management/participants/3104",
      search: "?round=7",
    });
  });

  it("names both people in a pair, mentor first", () => {
    expect(
      approvalPairLabel({
        pairId: 80,
        mentor: { userId: 11, name: "Mia Ko" },
        mentee: { userId: 21, name: null },
      }),
    ).toBe("mentor Mia Ko and mentee ID 21");
    expect(approvalPairLabel(null)).toBe("");
  });

  it("reviews ending a pair on the mentee's page for the round", () => {
    expect(
      approvalReviewLink({
        action: "end_pair",
        round: { roundId: 7 },
        person: null,
        pair: {
          pairId: 80,
          mentor: { userId: 11, name: "Mia Ko" },
          mentee: { userId: 21, name: "Ann Lee" },
        },
      }),
    ).toEqual({
      pathname: "/mentorship-management/participants/21",
      search: "?round=7",
    });
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

  it("reviews a mark on the person's page for the round", () => {
    for (const action of ["mark_no_show", "mark_red_flag"]) {
      expect(
        approvalReviewLink({
          action,
          round: { roundId: 7 },
          person: { userId: 3104 },
        }),
      ).toEqual({
        pathname: "/mentorship-management/participants/3104",
        search: "?round=7",
      });
    }
  });

  it("says where a mark was given, this round by name of its own", () => {
    expect(
      exemptionWhyLines(
        [
          { reason: "no_show", roundId: 3, roundName: "Spring 2026" },
          { reason: "red_flag", roundId: 7, roundName: "Fall 2026" },
          { reason: "red_flag", roundId: 2, roundName: null },
        ],
        "7",
      ),
    ).toEqual([
      "No show in Spring 2026",
      "Red flag in this round",
      "Red flag in an earlier round",
    ]);
  });

  it("says why someone needs an exemption, one line per problem", () => {
    expect(
      exemptionWhyLines([
        { reason: "quit_after_match", roundName: "Fall 2025" },
        {
          reason: "meetings_short",
          roundName: "Fall 2025",
          completed: 2,
          required: 5,
        },
        {
          reason: "meetings_short",
          roundName: null,
          completed: null,
          required: 6,
        },
      ]),
    ).toEqual([
      "Quit after being matched in Fall 2025",
      "Meetings short in Fall 2025: 2 of 5",
      "Meetings short in an earlier round: 0 of 6",
    ]);
    expect(exemptionWhyLines(undefined)).toEqual([]);
  });
});
