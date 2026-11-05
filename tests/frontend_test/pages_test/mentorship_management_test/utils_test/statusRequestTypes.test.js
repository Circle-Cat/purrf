import { describe, it, expect, vi } from "vitest";
import {
  PAIR_RULE,
  availableStatusRequestTypes,
  statusRequestType,
} from "@/pages/MentorshipManagement/utils/statusRequestTypes";
import {
  requestParticipantEndPair,
  requestParticipantMark,
  requestParticipantWithdrawal,
} from "@/api/mentorshipApi";

vi.mock("@/api/mentorshipApi", () => ({
  requestParticipantEndPair: vi.fn(),
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
  it("offers all four to a writer while someone paired is still in a round in progress", () => {
    expect(labels(context())).toEqual([
      "Withdraw from round",
      "Mark as no show",
      "Raise a red flag",
      "End this pair",
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
    ).toEqual(["Raise a red flag", "End this pair"]);
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

  const active = (pairId, id) => ({
    pairId,
    partner: { id, firstName: "P", lastName: String(id), isActive: true },
  });
  const ended = (pairId, id) => ({
    pairId,
    partner: { id, firstName: "P", lastName: String(id), isActive: false },
  });

  it("offers ending a pair only while someone still in the round has an active one", () => {
    expect(
      labels(
        context({
          registration: { approvalStatus: "matched", pairs: [ended(80, 23)] },
        }),
      ),
    ).not.toContain("End this pair");
    expect(
      labels(
        context({
          registration: {
            approvalStatus: "withdrawn",
            pairs: [active(80, 23)],
          },
        }),
      ),
    ).not.toContain("End this pair");
  });

  it("lists only active pairs not already waiting to end, so another pair stays open", () => {
    const type = statusRequestType("end_pair");
    const pairs = [active(80, 23), active(81, 24), ended(82, 25)];
    const pendingRequests = [{ requestId: 61, action: "end_pair", pairId: 80 }];

    expect(
      type.pairChoices(pairs, pendingRequests).map((p) => p.pairId),
    ).toEqual([81]);
    expect(
      labels(
        context({
          registration: { approvalStatus: "matched", pairs },
          pendingRequests,
        }),
      ),
    ).toContain("End this pair");
    expect(
      labels(
        context({
          registration: { approvalStatus: "matched", pairs: [active(80, 23)] },
          pendingRequests,
        }),
      ),
    ).not.toContain("End this pair");
  });

  it("names the partner in what ending the pair does", () => {
    const type = statusRequestType("end_pair");
    expect(type.pair).toBe(PAIR_RULE.REQUIRED);
    expect(type.partnerMayNotReview).toBe(true);
    expect(type.consequences("Mia Ko", { partnerName: "Ann Lee" })).toBe(
      "The pair with Ann Lee ends and its meetings that have not started are cancelled. Whoever has no other pair left becomes unmatched; both can be paired with someone else; these two cannot be paired again this round. This cannot be undone. Neither of them is told.",
    );
    expect(type.consequences("Mia Ko")).toMatch(/^The pair you pick ends/);
  });

  it("sends ending a pair with its pair", async () => {
    await statusRequestType("end_pair").raise(7, 3104, {
      reviewerId: 8,
      reason: "",
      pairId: 80,
    });
    expect(requestParticipantEndPair).toHaveBeenCalledWith(7, 3104, {
      pairId: 80,
      reviewerId: 8,
      reason: "",
    });
  });

  it("says a withdrawn person's partner left with no pair becomes unmatched", () => {
    expect(
      statusRequestType("withdraw_participant").consequences("Mia Ko"),
    ).toBe(
      "Mia Ko leaves this round: every pair they have in it ends, and their meetings that have not started are cancelled. A partner left with no other pair becomes unmatched. This cannot be undone.",
    );
  });
});
