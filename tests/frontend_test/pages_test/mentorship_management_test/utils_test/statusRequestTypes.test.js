import { describe, it, expect, vi } from "vitest";
import {
  availableStatusRequestTypes,
  statusRequestType,
} from "@/pages/MentorshipManagement/utils/statusRequestTypes";
import { requestParticipantWithdrawal } from "@/api/mentorshipApi";

vi.mock("@/api/mentorshipApi", () => ({
  requestParticipantWithdrawal: vi.fn(),
}));

const context = (overrides = {}) => ({
  canWrite: true,
  round: { roundId: 7, inProgress: true },
  registration: { approvalStatus: "matched" },
  ...overrides,
});

describe("statusRequestTypes", () => {
  it("offers Withdraw from round to a writer while the person is still in a round in progress", () => {
    for (const approvalStatus of ["signed_up", "matched", "un_matched"]) {
      expect(
        availableStatusRequestTypes(
          context({ registration: { approvalStatus } }),
        ).map((t) => t.label),
      ).toEqual(["Withdraw from round"]);
    }
  });

  it("offers nothing once they have left, before they register, to a reader, or after the round", () => {
    for (const ctx of [
      context({ registration: { approvalStatus: "withdrawn" } }),
      context({ registration: { approvalStatus: "rejected" } }),
      context({ registration: null }),
      context({ canWrite: false }),
      context({ round: { roundId: 7, inProgress: false } }),
    ]) {
      expect(availableStatusRequestTypes(ctx)).toEqual([]);
    }
  });

  it("finds a type by its action and sends it to the person in the round", () => {
    const withdraw = statusRequestType("withdraw_participant");

    withdraw.raise(7, 3104, { reviewerId: 8, reason: "" });

    expect(requestParticipantWithdrawal).toHaveBeenCalledWith(7, 3104, {
      reviewerId: 8,
      reason: "",
    });
    expect(withdraw.consequences("Mia Ko")).toMatch(/cannot be undone/);
    expect(statusRequestType("exempt_matching")).toBeNull();
  });
});
