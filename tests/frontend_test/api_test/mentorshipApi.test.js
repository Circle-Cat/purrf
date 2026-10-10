import { vi, describe, it, expect, beforeEach } from "vitest";
import request from "@/utils/request";
import {
  getAllMentorshipRounds,
  upsertMentorshipRound,
  getMyMentorshipPartners,
  getMyMentorshipRegistration,
  postMyMentorshipRegistration,
  getMyMentorshipMeetingLog,
  postMyMentorshipMeetingLog,
  searchParticipants,
  searchUnregistered,
  getMeetingLog,
  updateMeetingLog,
  startMatchingRun,
  getMatchingRun,
  getMatchingResults,
  getMatchingUnmatched,
  takeMatchingEditLock,
  releaseMatchingEditLock,
  releaseMatchingEditLockOnLeave,
  saveMatchingDraft,
  requestMatchingPublish,
  getMentorshipApprovers,
  getMyMentorshipApprovals,
  reassignMentorshipApproval,
  decideMentorshipApproval,
  withdrawMentorshipApproval,
  requestMatchingExemption,
  requestParticipantEndPair,
  requestParticipantMark,
  requestParticipantWithdrawal,
} from "@/api/mentorshipApi";
import { API_ENDPOINTS } from "@/constants/ApiEndpoints";

vi.mock("@/utils/request", () => {
  return {
    default: {
      get: vi.fn(),
      post: vi.fn(),
      patch: vi.fn(),
      delete: vi.fn(),
      defaults: { baseURL: "/api" },
    },
  };
});
describe("Mentorship Service API", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("upsertMentorshipRound should send a POST request with the payload", async () => {
    const payload = { name: "Mentorship 2026 Spring", required_meetings: 5 };
    await upsertMentorshipRound(payload);
    expect(request.post).toHaveBeenCalledWith(
      API_ENDPOINTS.MENTORSHIP_ROUNDS,
      payload,
    );
  });

  it("getAllMentorshipRounds should call the correct GET endpoint with need_details=false by default", async () => {
    const mockData = [{ id: 1, name: "Round 1" }];
    request.get.mockResolvedValue(mockData);

    const result = await getAllMentorshipRounds();

    expect(request.get).toHaveBeenCalledWith(API_ENDPOINTS.MENTORSHIP_ROUNDS, {
      params: { need_details: false },
    });
    expect(result).toEqual(mockData);
  });

  it("getAllMentorshipRounds should call the correct GET endpoint with need_details=true", async () => {
    const mockData = [
      {
        id: 1,
        name: "Round 1",
        matchedParticipants: 10,
        activePairs: 5,
        totalCompletedMeetings: 18,
      },
    ];
    request.get.mockResolvedValue(mockData);

    const result = await getAllMentorshipRounds(true);

    expect(request.get).toHaveBeenCalledWith(API_ENDPOINTS.MENTORSHIP_ROUNDS, {
      params: { need_details: true },
    });
    expect(result).toEqual(mockData);
  });

  it("getMyMentorshipPartners without the roundId parameter", async () => {
    await getMyMentorshipPartners();

    expect(request.get).toHaveBeenCalledWith(
      API_ENDPOINTS.MENTORSHIP_PARTNERS,
      {
        params: { roundId: undefined },
      },
    );
  });

  it("getMyMentorshipRegistration should correctly replace the path parameter", async () => {
    const roundId = "999";
    const expectedUrl = API_ENDPOINTS.MENTORSHIP_REGISTRATION(roundId);

    await getMyMentorshipRegistration(roundId);

    expect(request.get).toHaveBeenCalledWith(expectedUrl, {
      params: undefined,
    });
  });

  it("getMyMentorshipRegistration sends the role when one is named", async () => {
    const roundId = "999";
    const expectedUrl = API_ENDPOINTS.MENTORSHIP_REGISTRATION(roundId);

    await getMyMentorshipRegistration(roundId, "mentor");

    expect(request.get).toHaveBeenCalledWith(expectedUrl, {
      params: { role: "mentor" },
    });
  });

  it("postMyMentorshipRegistration should send a POST request with the payload", async () => {
    const roundId = "888";
    const payload = { mentor_id: 1, reason: "Learn Vitest" };
    const expectedUrl = API_ENDPOINTS.MENTORSHIP_REGISTRATION(roundId);

    await postMyMentorshipRegistration(roundId, payload);

    expect(request.post).toHaveBeenCalledWith(expectedUrl, payload);
  });

  it("should throw an error when the request fails (verify error propagation from the interceptor)", async () => {
    const mockError = new Error("Network Error");
    request.get.mockRejectedValue(mockError);

    await expect(getAllMentorshipRounds()).rejects.toThrow("Network Error");
  });

  it("getMyMentorshipMeetingLog should call the correct GET endpoint", async () => {
    const roundId = "777";
    const mockData = { meeting_info: [] };
    request.get.mockResolvedValue(mockData);

    const result = await getMyMentorshipMeetingLog(roundId);

    expect(request.get).toHaveBeenCalledWith(
      API_ENDPOINTS.MENTORSHIP_MEETINGS_ENDPOINT,
      {
        params: { round_id: roundId },
      },
    );
    expect(result).toEqual(mockData);
  });

  it("postMyMentorshipMeetingLog should call the correct POST endpoint with the payload", async () => {
    const payload = {
      roundId: 1,
      chosenTimezone: "Asia/Shanghai",
      startDatetime: "2026-03-13T10:00:00+08:00",
      endDatetime: "2026-03-13T11:00:00+08:00",
      is_completed: true,
    };
    const mockResponse = { success: true };
    request.post.mockResolvedValue(mockResponse);

    const result = await postMyMentorshipMeetingLog(payload);

    expect(request.post).toHaveBeenCalledWith(
      API_ENDPOINTS.MENTORSHIP_MEETINGS_ENDPOINT,
      payload,
    );
    expect(result).toEqual(mockResponse);
  });

  it("searchParticipants sends filters as camelCase params", async () => {
    const mockData = { participant_rows: [], total: 0 };
    request.get.mockResolvedValue(mockData);

    const result = await searchParticipants({
      userId: 5,
      q: "alice",
      accountStatus: "blocked",
      internal: "external",
      roundId: 3,
      participantRole: "mentor",
      approvalStatus: "matched",
      onboardingStatus: "completed",
      limit: 20,
      offset: 0,
    });

    expect(request.get).toHaveBeenCalledWith(
      API_ENDPOINTS.MENTORSHIP_ADMIN_PARTICIPANTS,
      {
        params: {
          userId: 5,
          q: "alice",
          accountStatus: "blocked",
          internal: "external",
          roundId: 3,
          participantRole: "mentor",
          approvalStatus: "matched",
          onboardingStatus: "completed",
          limit: 20,
          offset: 0,
        },
      },
    );
    expect(result).toEqual(mockData);
  });

  it("searchParticipants sends sortBy as the sort_by query param", async () => {
    request.get.mockResolvedValue({ participant_rows: [], total: 0 });

    await searchParticipants({
      limit: 20,
      offset: 0,
      sortBy: "user_id",
      order: "desc",
    });

    expect(request.get).toHaveBeenCalledWith(
      API_ENDPOINTS.MENTORSHIP_ADMIN_PARTICIPANTS,
      expect.objectContaining({
        params: expect.objectContaining({
          sort_by: "user_id",
          order: "desc",
        }),
      }),
    );
  });

  it("searchUnregistered asks the round's not-registered list with its filters", async () => {
    const mockData = { rows: [], total: 0 };
    request.get.mockResolvedValue(mockData);

    const result = await searchUnregistered(7, {
      userId: 5,
      q: "alice",
      accountStatus: "blocked",
      internal: "external",
      admittedRole: "mentee",
      limit: 20,
      offset: 40,
      order: "desc",
    });

    expect(request.get).toHaveBeenCalledWith(
      "/mentorship/admin/rounds/7/unregistered",
      {
        params: {
          userId: 5,
          q: "alice",
          accountStatus: "blocked",
          internal: "external",
          admittedRole: "mentee",
          limit: 20,
          offset: 40,
          order: "desc",
        },
      },
    );
    expect(result).toEqual(mockData);
  });

  it("searchParticipants omits filters that are not provided", async () => {
    request.get.mockResolvedValue({ participant_rows: [], total: 0 });

    await searchParticipants({
      limit: 20,
      offset: 0,
    });

    expect(request.get).toHaveBeenCalledWith(
      API_ENDPOINTS.MENTORSHIP_ADMIN_PARTICIPANTS,
      {
        params: {
          userId: undefined,
          q: undefined,
          accountStatus: undefined,
          internal: undefined,
          roundId: undefined,
          participantRole: undefined,
          approvalStatus: undefined,
          onboardingStatus: undefined,
          limit: 20,
          offset: 0,
          sort_by: undefined,
          order: undefined,
        },
      },
    );
  });

  it("getMeetingLog should call the correct GET endpoint for the given pair", async () => {
    const pairId = 80;
    const mockData = { roundVersion: "v2", meetings: [] };
    request.get.mockResolvedValue(mockData);

    const result = await getMeetingLog(pairId);

    expect(request.get).toHaveBeenCalledWith(
      API_ENDPOINTS.MENTORSHIP_ADMIN_PAIR_MEETINGS(pairId),
    );
    expect(result).toEqual(mockData);
  });

  it("updateMeetingLog should PATCH the correct endpoint with the batch body", async () => {
    const pairId = 80;
    const body = {
      updates: [{ meetingId: "gm-1", isCompleted: true }],
      deletes: ["gm-2"],
    };
    const mockData = { roundVersion: "v2", meetings: [] };
    request.patch.mockResolvedValue(mockData);

    const result = await updateMeetingLog(pairId, body);

    expect(request.patch).toHaveBeenCalledWith(
      API_ENDPOINTS.MENTORSHIP_ADMIN_PAIR_MEETINGS(pairId),
      body,
    );
    expect(result).toEqual(mockData);
  });

  it("startMatchingRun posts the round and the picked people", async () => {
    const mockData = { data: { runId: 12 } };
    request.post.mockResolvedValue(mockData);

    const result = await startMatchingRun({
      roundId: 7,
      participantIds: [11, 12],
    });

    expect(request.post).toHaveBeenCalledWith("/mentorship/admin/match-runs", {
      roundId: 7,
      participantIds: [11, 12],
    });
    expect(result).toEqual(mockData);
  });

  it("getMatchingRun asks for the round's run", async () => {
    const mockData = { data: { status: "never_run" } };
    request.get.mockResolvedValue(mockData);

    const result = await getMatchingRun(7);

    expect(request.get).toHaveBeenCalledWith("/mentorship/admin/match-runs/7");
    expect(result).toEqual(mockData);
  });

  it("getMatchingResults asks for a page of the round's results", async () => {
    const mockData = { data: { items: [], total: 0 } };
    request.get.mockResolvedValue(mockData);

    const result = await getMatchingResults(7, {
      limit: 20,
      offset: 40,
      matched: false,
    });

    expect(request.get).toHaveBeenCalledWith(
      "/mentorship/admin/match-runs/7/results",
      { params: { limit: 20, offset: 40, matched: false } },
    );
    expect(result).toEqual(mockData);
  });

  it("getMatchingResults leaves matched out for every mentee", async () => {
    request.get.mockResolvedValue({ data: {} });

    await getMatchingResults(7, { limit: 20, offset: 0 });

    expect(request.get).toHaveBeenCalledWith(
      "/mentorship/admin/match-runs/7/results",
      { params: { limit: 20, offset: 0, matched: undefined } },
    );
  });

  it("getMatchingUnmatched asks for a page of the people left unmatched", async () => {
    const mockData = { data: { items: [], total: 0 } };
    request.get.mockResolvedValue(mockData);

    const result = await getMatchingUnmatched(7, { limit: 20, offset: 20 });

    expect(request.get).toHaveBeenCalledWith(
      "/mentorship/admin/match-runs/7/unmatched",
      { params: { limit: 20, offset: 20 } },
    );
    expect(result).toEqual(mockData);
  });

  it("takeMatchingEditLock posts to the round's edit lock", async () => {
    const mockData = { data: { userId: 5845, name: "Dev Admin" } };
    request.post.mockResolvedValue(mockData);

    const result = await takeMatchingEditLock(7);

    expect(request.post).toHaveBeenCalledWith(
      "/mentorship/admin/match-runs/7/edit-lock",
    );
    expect(result).toEqual(mockData);
  });

  it("releaseMatchingEditLock deletes the round's edit lock", async () => {
    request.delete.mockResolvedValue({ data: null });

    await releaseMatchingEditLock(7);

    expect(request.delete).toHaveBeenCalledWith(
      "/mentorship/admin/match-runs/7/edit-lock",
    );
  });

  it("releaseMatchingEditLockOnLeave sends a keepalive DELETE around axios", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true });
    vi.stubGlobal("fetch", fetchMock);
    try {
      await releaseMatchingEditLockOnLeave(7);

      expect(fetchMock).toHaveBeenCalledWith(
        "/api/mentorship/admin/match-runs/7/edit-lock",
        { method: "DELETE", keepalive: true, credentials: "include" },
      );
      expect(request.delete).not.toHaveBeenCalled();
    } finally {
      vi.unstubAllGlobals();
    }
  });

  it("releaseMatchingEditLockOnLeave only logs a failure", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")));
    const consoleError = vi
      .spyOn(console, "error")
      .mockImplementation(() => {});
    try {
      await expect(releaseMatchingEditLockOnLeave(7)).resolves.toBeUndefined();
      expect(consoleError).toHaveBeenCalled();
    } finally {
      vi.unstubAllGlobals();
      consoleError.mockRestore();
    }
  });

  it("saveMatchingDraft patches the draft with the changes", async () => {
    const mockData = { data: { draftCount: 3 } };
    request.patch.mockResolvedValue(mockData);
    const changes = [
      { menteeId: "201", mentorId: null, recommendationReason: "" },
    ];

    const result = await saveMatchingDraft(7, changes);

    expect(request.patch).toHaveBeenCalledWith(
      "/mentorship/admin/match-runs/7/draft",
      { changes },
    );
    expect(result).toEqual(mockData);
  });

  it("requestMatchingPublish posts the reviewer and reason for the round", async () => {
    const mockData = { data: { requestId: 31 } };
    request.post.mockResolvedValue(mockData);

    const result = await requestMatchingPublish(7, {
      reviewerId: 8,
      reason: "Reviewed every pair",
    });

    expect(request.post).toHaveBeenCalledWith(
      "/mentorship/admin/match-runs/7/publish-request",
      { reviewerId: 8, reason: "Reviewed every pair" },
    );
    expect(result).toEqual(mockData);
  });

  it("getMentorshipApprovers and getMyMentorshipApprovals read their lists", async () => {
    request.get.mockResolvedValue({ data: [] });

    await getMentorshipApprovers();
    await getMyMentorshipApprovals();

    expect(request.get).toHaveBeenNthCalledWith(
      1,
      "/mentorship/admin/approvals/approvers",
    );
    expect(request.get).toHaveBeenNthCalledWith(
      2,
      "/mentorship/admin/approvals/mine",
    );
  });

  it("reassign, decide and withdraw post to the request", async () => {
    request.post.mockResolvedValue({ data: {} });

    await reassignMentorshipApproval(31, 12);
    await decideMentorshipApproval(31, { decision: "reject", comment: "No" });
    await withdrawMentorshipApproval(31);

    expect(request.post).toHaveBeenNthCalledWith(
      1,
      "/mentorship/admin/approvals/31/reassign",
      { reviewerId: 12 },
    );
    expect(request.post).toHaveBeenNthCalledWith(
      2,
      "/mentorship/admin/approvals/31/decide",
      { decision: "reject", comment: "No" },
    );
    expect(request.post).toHaveBeenNthCalledWith(
      3,
      "/mentorship/admin/approvals/31/withdraw",
    );
  });

  it("requestMatchingExemption posts to the person in the round", async () => {
    request.post.mockResolvedValue({ data: {} });

    await requestMatchingExemption(7, 21, { reviewerId: 8, reason: "Left" });

    expect(request.post).toHaveBeenCalledWith(
      "/mentorship/admin/rounds/7/participants/21/exemption-request",
      { reviewerId: 8, reason: "Left" },
    );
  });

  it("requestParticipantWithdrawal posts to the person in the round", async () => {
    request.post.mockResolvedValue({ data: {} });

    await requestParticipantWithdrawal(7, 3104, { reviewerId: 8, reason: "" });

    expect(request.post).toHaveBeenCalledWith(
      "/mentorship/admin/rounds/7/participants/3104/withdraw-request",
      { reviewerId: 8, reason: "" },
    );
  });

  it("requestParticipantMark posts the mark and its pair for the person in the round", async () => {
    request.post.mockResolvedValue({ data: {} });

    await requestParticipantMark(7, 3104, {
      tag: "no_show",
      pairId: 80,
      reviewerId: 8,
      reason: "",
    });
    await requestParticipantMark(7, 3104, {
      tag: "red_flag",
      reviewerId: 8,
      reason: "Rude",
    });

    expect(request.post).toHaveBeenNthCalledWith(
      1,
      "/mentorship/admin/rounds/7/participants/3104/mark-request",
      { tag: "no_show", pairId: 80, reviewerId: 8, reason: "" },
    );
    expect(request.post).toHaveBeenNthCalledWith(
      2,
      "/mentorship/admin/rounds/7/participants/3104/mark-request",
      { tag: "red_flag", pairId: null, reviewerId: 8, reason: "Rude" },
    );
  });

  it("requestParticipantEndPair posts the pair for the person in the round", async () => {
    request.post.mockResolvedValue({ data: {} });

    await requestParticipantEndPair(7, 3104, {
      pairId: 80,
      reviewerId: 8,
      reason: "",
    });

    expect(request.post).toHaveBeenCalledWith(
      "/mentorship/admin/rounds/7/participants/3104/end-pair-request",
      { pairId: 80, reviewerId: 8, reason: "" },
    );
  });

  it("searchParticipants passes needsExemption through", async () => {
    request.get.mockResolvedValue({ data: {} });

    await searchParticipants({ roundId: 7, needsExemption: true });

    expect(request.get.mock.calls.at(-1)[1].params.needsExemption).toBe(true);
  });
});
