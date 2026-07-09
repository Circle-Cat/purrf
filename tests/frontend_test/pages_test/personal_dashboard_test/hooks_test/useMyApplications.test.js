import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { useMyApplications } from "@/pages/PersonalDashboard/hooks/useMyApplications";
import * as api from "@/api/recruitingApi";

vi.mock("@/api/recruitingApi");

describe("useMyApplications", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("defaults hasHiredMentorshipApplication to true while loading", () => {
    api.listMyApplications.mockReturnValue(new Promise(() => {})); // never resolves
    const { result } = renderHook(() => useMyApplications());

    expect(result.current.isLoading).toBe(true);
    expect(result.current.hasHiredMentorshipApplication).toBe(true);
  });

  it("defaults hasHiredMentorshipApplication to true on load failure (fail open)", async () => {
    api.listMyApplications.mockRejectedValue(new Error("network error"));
    const { result } = renderHook(() => useMyApplications());

    await waitFor(() => expect(result.current.loadError).toBe(true));
    expect(result.current.hasHiredMentorshipApplication).toBe(true);
  });

  it("is true when a hired activity application has a mentor role", async () => {
    api.listMyApplications.mockResolvedValue({
      data: [
        {
          applicationId: 1,
          jobId: 1,
          jobTitle: "CircleCat Mentor",
          jobKind: "activity",
          mentorshipRole: "mentor",
          stage: "hired",
        },
      ],
    });
    const { result } = renderHook(() => useMyApplications());

    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.hasHiredMentorshipApplication).toBe(true);
  });

  it("is true when a hired activity application has a mentee role", async () => {
    api.listMyApplications.mockResolvedValue({
      data: [
        {
          applicationId: 1,
          jobId: 1,
          jobTitle: "CircleCat Mentee",
          jobKind: "activity",
          mentorshipRole: "mentee",
          stage: "hired",
        },
      ],
    });
    const { result } = renderHook(() => useMyApplications());

    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.hasHiredMentorshipApplication).toBe(true);
  });

  it("is false when the only hired application is EMPLOYMENT-kind", async () => {
    api.listMyApplications.mockResolvedValue({
      data: [
        {
          applicationId: 1,
          jobId: 1,
          jobTitle: "Backend Engineer",
          jobKind: "employment",
          mentorshipRole: null,
          stage: "hired",
        },
      ],
    });
    const { result } = renderHook(() => useMyApplications());

    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.hasHiredMentorshipApplication).toBe(false);
  });

  it("is false when an activity application has no mentorshipRole even if hired", async () => {
    api.listMyApplications.mockResolvedValue({
      data: [
        {
          applicationId: 1,
          jobId: 1,
          jobTitle: "Some Future Activity",
          jobKind: "activity",
          mentorshipRole: null,
          stage: "hired",
        },
      ],
    });
    const { result } = renderHook(() => useMyApplications());

    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.hasHiredMentorshipApplication).toBe(false);
  });

  it("is false when an activity+mentor application exists but isn't hired yet", async () => {
    api.listMyApplications.mockResolvedValue({
      data: [
        {
          applicationId: 1,
          jobId: 1,
          jobTitle: "CircleCat Mentor",
          jobKind: "activity",
          mentorshipRole: "mentor",
          stage: "recruiter_screening",
        },
      ],
    });
    const { result } = renderHook(() => useMyApplications());

    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.hasHiredMentorshipApplication).toBe(false);
  });

  it("is false for an empty application list", async () => {
    api.listMyApplications.mockResolvedValue({ data: [] });
    const { result } = renderHook(() => useMyApplications());

    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.hasHiredMentorshipApplication).toBe(false);
    expect(result.current.applications).toEqual([]);
  });
});
