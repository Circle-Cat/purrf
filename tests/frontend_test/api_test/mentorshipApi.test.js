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
  getMeetingLog,
  updateMeetingLog,
  getParticipantExportUrl,
} from "@/api/mentorshipApi";
import { API_ENDPOINTS } from "@/constants/ApiEndpoints";

vi.mock("@/utils/request", () => {
  return {
    default: {
      get: vi.fn(),
      post: vi.fn(),
      patch: vi.fn(),
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

    expect(request.get).toHaveBeenCalledWith(expectedUrl);
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
      name: "Alice",
      email: "alice@x.com",
      matchedUser: "Bob Smith",
      roundId: 3,
      participantRole: "mentor",
      approvalStatus: "matched",
      onboardingStatus: "completed",
      participationStatus: "participant",
      limit: 20,
      offset: 0,
    });

    expect(request.get).toHaveBeenCalledWith(
      API_ENDPOINTS.MENTORSHIP_ADMIN_PARTICIPANTS,
      {
        params: {
          userId: 5,
          name: "Alice",
          email: "alice@x.com",
          matchedUser: "Bob Smith",
          roundId: 3,
          participantRole: "mentor",
          approvalStatus: "matched",
          onboardingStatus: "completed",
          participationStatus: "participant",
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
      participationStatus: "participant",
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

  it("searchParticipants omits filters that are not provided", async () => {
    request.get.mockResolvedValue({ participant_rows: [], total: 0 });

    await searchParticipants({
      participationStatus: "non_participant",
      limit: 20,
      offset: 0,
    });

    expect(request.get).toHaveBeenCalledWith(
      API_ENDPOINTS.MENTORSHIP_ADMIN_PARTICIPANTS,
      {
        params: {
          userId: undefined,
          name: undefined,
          email: undefined,
          matchedUser: undefined,
          roundId: undefined,
          participantRole: undefined,
          approvalStatus: undefined,
          onboardingStatus: undefined,
          participationStatus: "non_participant",
          limit: 20,
          offset: 0,
          sort_by: undefined,
          order: undefined,
        },
      },
    );
  });

  it("getParticipantExportUrl sends export filters with correct param names", () => {
    const url = getParticipantExportUrl({
      userId: 5,
      name: "Alice",
      participationStatus: "participant",
      expandMeetings: true,
    });

    const [base, query] = url.split("?");
    expect(base).toBe(
      `${request.defaults.baseURL}${API_ENDPOINTS.MENTORSHIP_ADMIN_PARTICIPANTS_EXPORT}`,
    );
    const params = new URLSearchParams(query);
    expect(params.get("userId")).toBe("5");
    expect(params.get("name")).toBe("Alice");
    expect(params.get("participationStatus")).toBe("participant");
    expect(params.get("expand_meetings")).toBe("true");
  });

  it("getParticipantExportUrl includes expand_meetings=false when expandMeetings is false", () => {
    const url = getParticipantExportUrl({
      participationStatus: "participant",
      expandMeetings: false,
    });

    const params = new URLSearchParams(url.split("?")[1]);
    expect(params.get("expand_meetings")).toBe("false");
  });

  it("getParticipantExportUrl omits filters that are not provided", () => {
    const url = getParticipantExportUrl({
      participationStatus: "non_participant",
    });

    const params = new URLSearchParams(url.split("?")[1]);
    expect(params.has("userId")).toBe(false);
    expect(params.has("name")).toBe(false);
    expect(params.has("expand_meetings")).toBe(false);
    expect(params.get("participationStatus")).toBe("non_participant");
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
});
