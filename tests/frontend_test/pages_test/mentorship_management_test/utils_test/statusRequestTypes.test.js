import { describe, it, expect, vi } from "vitest";
import {
  PAIR_RULE,
  availableStatusRequestTypes,
  statusRequestType,
} from "@/pages/MentorshipManagement/utils/statusRequestTypes";
import {
  requestParticipantMark,
  requestParticipantWithdrawal,
} from "@/api/mentorshipApi";

vi.mock("@/api/mentorshipApi", () => ({
  requestParticipantMark: vi.fn(),
  requestParticipantWithdrawal: vi.fn(),
}));

const PAIR = { pairId: 80 };

const context = (overrides = {}) => ({
  canWrite: true,
  round: { roundId: 7, inProgress: true },
  registration: { approvalStatus: "matched", pairs: [PAIR] },
  ...overrides,
});

const labels = (ctx) => availableStatusRequestTypes(ctx).map((t) => t.label);

describe("statusRequestTypes", () => {
  it("offers all three to a writer while someone paired is still in a round in progress", () => {
    expect(labels(context())).toEqual([
      "Withdraw from round",
      "Mark as no show",
      "Raise a red flag",
    ]);
  });

  it("offers no show only to someone who had a pair this round", () => {
    expect(
      labels(
        context({ registration: { approvalStatus: "signed_up", pairs: [] } }),
      ),
    ).toEqual(["Withdraw from round", "Raise a red flag"]);
  });

  it("still offers the marks once they have left, whatever their status", () => {
    for (const approvalStatus of ["withdrawn", "rejected"]) {
      expect(
        labels(context({ registration: { approvalStatus, pairs: [PAIR] } })),
      ).toEqual(["Mark as no show", "Raise a red flag"]);
    }
  });

  it("offers nothing before they register, to a reader, or after the round", () => {
    for (const ctx of [
      context({ registration: null }),
      context({ canWrite: false }),
      context({ round: { roundId: 7, inProgress: false } }),
    ]) {
      expect(availableStatusRequestTypes(ctx)).toEqual([]);
    }
  });

  it("does not offer a type already waiting, but offers the others beside it", () => {
    expect(
      labels(
        context({
          pendingRequests: [
            { requestId: 41, action: "withdraw_participant" },
            { requestId: 43, action: "mark_no_show" },
          ],
        }),
      ),
    ).toEqual(["Raise a red flag"]);
  });

  it("says which types are about a pair", () => {
    expect(statusRequestType("withdraw_participant").pair).toBe(PAIR_RULE.NONE);
    expect(statusRequestType("mark_no_show").pair).toBe(PAIR_RULE.REQUIRED);
    expect(statusRequestType("mark_red_flag").pair).toBe(PAIR_RULE.OPTIONAL);
  });

  it("sends each type to the person in the round", () => {
    statusRequestType("withdraw_participant").raise(7, 3104, {
      reviewerId: 8,
      reason: "",
    });
    statusRequestType("mark_no_show").raise(7, 3104, {
      reviewerId: 8,
      reason: "",
      pairId: 80,
    });
    statusRequestType("mark_red_flag").raise(7, 3104, {
      reviewerId: 8,
      reason: "Rude",
      pairId: null,
    });

    expect(requestParticipantWithdrawal).toHaveBeenCalledWith(7, 3104, {
      reviewerId: 8,
      reason: "",
    });
    expect(requestParticipantMark).toHaveBeenCalledWith(7, 3104, {
      tag: "no_show",
      pairId: 80,
      reviewerId: 8,
      reason: "",
    });
    expect(requestParticipantMark).toHaveBeenCalledWith(7, 3104, {
      tag: "red_flag",
      pairId: null,
      reviewerId: 8,
      reason: "Rude",
    });
    expect(statusRequestType("exempt_matching")).toBeNull();
  });

  it("tells the asker what a mark does", () => {
    for (const action of ["mark_no_show", "mark_red_flag"]) {
      expect(statusRequestType(action).consequences("Mia Ko")).toBe(
        "Recorded on their history. It keeps them out of matching until an exemption, including later in this round. It cannot be undone. They are not told.",
      );
    }
  });
});
