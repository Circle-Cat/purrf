import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { useMyApplications } from "@/hooks/useMyApplications";
import * as api from "@/api/recruitingApi";

vi.mock("@/api/recruitingApi");

/** One row of the response's `applications` list. */
const row = (overrides = {}) => ({
  applicationId: 1,
  jobId: 1,
  jobTitle: "CircleCat Mentor",
  jobKind: "activity",
  mentorshipRole: "mentor",
  stage: "hired",
  ...overrides,
});

describe("useMyApplications", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("is null while loading (no fail-open)", () => {
    api.listMyApplications.mockReturnValue(new Promise(() => {})); // never resolves
    const { result } = renderHook(() => useMyApplications());

    expect(result.current.isLoading).toBe(true);
    expect(result.current.hiredMentorshipRole).toBeNull();
  });

  it("is null on load failure (no fail-open)", async () => {
    api.listMyApplications.mockRejectedValue(new Error("network error"));
    const { result } = renderHook(() => useMyApplications());

    await waitFor(() => expect(result.current.loadError).toBe(true));
    expect(result.current.hiredMentorshipRole).toBeNull();
  });

  it("is 'mentor' when the response says so", async () => {
    api.listMyApplications.mockResolvedValue({
      data: { applications: [row()], lastMentorshipRole: "mentor" },
    });
    const { result } = renderHook(() => useMyApplications());

    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.hiredMentorshipRole).toBe("mentor");
  });

  it("is 'mentee' when the response says so", async () => {
    api.listMyApplications.mockResolvedValue({
      data: {
        applications: [row({ mentorshipRole: "mentee" })],
        lastMentorshipRole: "mentee",
      },
    });
    const { result } = renderHook(() => useMyApplications());

    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.hiredMentorshipRole).toBe("mentee");
  });

  // Which of several hired admissions governs is settled server-side. The
  // hook must not second-guess it from the rows: doing so is what let the
  // form a user filled in disagree with the registration it saved.
  it("takes the role from the response, not from the rows", async () => {
    api.listMyApplications.mockResolvedValue({
      data: {
        applications: [
          row({ applicationId: 1, mentorshipRole: "mentee" }),
          row({ applicationId: 2, mentorshipRole: "mentor" }),
        ],
        lastMentorshipRole: "mentor",
      },
    });
    const { result } = renderHook(() => useMyApplications());

    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.hiredMentorshipRole).toBe("mentor");
  });

  it("is null when the response carries no role, whatever the rows say", async () => {
    api.listMyApplications.mockResolvedValue({
      data: {
        applications: [row()],
        lastMentorshipRole: null,
      },
    });
    const { result } = renderHook(() => useMyApplications());

    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.hiredMentorshipRole).toBeNull();
  });

  it("exposes the applications list", async () => {
    const rows = [row({ applicationId: 7 })];
    api.listMyApplications.mockResolvedValue({
      data: { applications: rows, lastMentorshipRole: "mentor" },
    });
    const { result } = renderHook(() => useMyApplications());

    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.applications).toEqual(rows);
  });

  it("is null for an empty application list", async () => {
    api.listMyApplications.mockResolvedValue({
      data: { applications: [], lastMentorshipRole: null },
    });
    const { result } = renderHook(() => useMyApplications());

    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.hiredMentorshipRole).toBeNull();
    expect(result.current.applications).toEqual([]);
  });

  // A reload that fails leaves nothing standing: the mentorship section is
  // gated on this role, and a stale one would keep it rendered against an
  // answer no response confirms.
  it("drops a previously loaded role when a reload fails", async () => {
    api.listMyApplications.mockResolvedValue({
      data: { applications: [row()], lastMentorshipRole: "mentor" },
    });
    const { result } = renderHook(() => useMyApplications());
    await waitFor(() =>
      expect(result.current.hiredMentorshipRole).toBe("mentor"),
    );

    api.listMyApplications.mockRejectedValue(new Error("network error"));
    result.current.load();

    await waitFor(() => expect(result.current.loadError).toBe(true));
    expect(result.current.hiredMentorshipRole).toBeNull();
  });
});
