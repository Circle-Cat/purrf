import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, act, waitFor } from "@testing-library/react";
import { useParticipantDetail } from "@/pages/MentorshipManagement/hooks/useParticipantDetail";
import * as api from "@/api/mentorshipApi";
import { detailOf } from "../participantDetail.helper";

vi.mock("@/api/mentorshipApi");

describe("useParticipantDetail", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.getParticipantDetail.mockResolvedValue({ data: detailOf() });
  });

  it("asks for the person in the round, in that order", async () => {
    const { result } = renderHook(() => useParticipantDetail("7", "3104"));
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(api.getParticipantDetail).toHaveBeenCalledWith("7", "3104");
    expect(result.current.detail.person.userId).toBe(3104);
  });

  it("does not fetch without a round", () => {
    renderHook(() => useParticipantDetail(null, "3104"));
    expect(api.getParticipantDetail).not.toHaveBeenCalled();
  });

  it("sets error on failure", async () => {
    api.getParticipantDetail.mockRejectedValue(new Error("boom"));
    const { result } = renderHook(() => useParticipantDetail("7", "3104"));
    await waitFor(() => expect(result.current.error).toBe(true));
    expect(result.current.loading).toBe(false);
  });

  it("refetch replaces the detail without going back to loading", async () => {
    const { result } = renderHook(() => useParticipantDetail("7", "3104"));
    await waitFor(() => expect(result.current.loading).toBe(false));

    api.getParticipantDetail.mockResolvedValue({
      data: detailOf({ exempted: true }),
    });
    let sawLoading = false;
    await act(async () => {
      const pending = result.current.refetch();
      sawLoading = result.current.loading;
      await pending;
    });
    expect(sawLoading).toBe(false);
    expect(result.current.detail.exempted).toBe(true);
  });
});
