import { vi, describe, it, expect, beforeEach } from "vitest";
import request from "@/utils/request";
import {
  getAllMentorshipRounds,
  getMyMentorshipPartners,
  getMyMentorshipRegistration,
  postMyMentorshipRegistration,
} from "@/api/mentorshipApi";
import { API_ENDPOINTS } from "@/constants/ApiEndpoints";

vi.mock("@/utils/request", () => {
  return {
    default: {
      get: vi.fn(),
      post: vi.fn(),
    },
  };
});

describe("Mentorship Service API", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("getAllMentorshipRounds should call the correct GET endpoint", async () => {
    const mockData = [{ id: 1, name: "Round 1" }];
    request.get.mockResolvedValue(mockData);

    const result = await getAllMentorshipRounds();

    expect(request.get).toHaveBeenCalledWith(API_ENDPOINTS.MENTORSHIP_ROUNDS);
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
});
