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

  it("is empty while loading (no fail-open)", () => {
    api.listMyApplications.mockReturnValue(new Promise(() => {})); // never resolves
    const { result } = renderHook(() => useMyApplications());

    expect(result.current.isLoading).toBe(true);
    expect(result.current.hiredMentorshipRoles).toEqual([]);
  });

  it("is empty on load failure (no fail-open)", async () => {
    api.listMyApplications.mockRejectedValue(new Error("network error"));
    const { result } = renderHook(() => useMyApplications());

    await waitFor(() => expect(result.current.loadError).toBe(true));
    expect(result.current.hiredMentorshipRoles).toEqual([]);
  });

  it("returns every role the response carries", async () => {
    api.listMyApplications.mockResolvedValue({
      data: { applications: [], mentorshipRoles: ["mentor", "mentee"] },
    });
    const { result } = renderHook(() => useMyApplications());

    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.hiredMentorshipRoles).toEqual(["mentor", "mentee"]);
  });

  it("returns the single role of a one-admission participant", async () => {
    api.listMyApplications.mockResolvedValue({
      data: {
        applications: [row({ mentorshipRole: "mentee" })],
        mentorshipRoles: ["mentee"],
      },
    });
    const { result } = renderHook(() => useMyApplications());

    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.hiredMentorshipRoles).toEqual(["mentee"]);
  });

  // Which admissions qualify a user is settled server-side. The hook must
  // not second-guess it from the rows: doing so is what let the form a user
  // filled in disagree with the registration it saved.
  it("takes the roles from the response, not from the rows", async () => {
    api.listMyApplications.mockResolvedValue({
      data: {
        applications: [
          row({ applicationId: 1, mentorshipRole: "mentee" }),
          row({ applicationId: 2, mentorshipRole: "mentor" }),
        ],
        mentorshipRoles: ["mentor"],
      },
    });
    const { result } = renderHook(() => useMyApplications());

    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.hiredMentorshipRoles).toEqual(["mentor"]);
  });

  it("returns no roles when the response carries none, whatever the rows say", async () => {
    api.listMyApplications.mockResolvedValue({
      data: { applications: [row()], mentorshipRoles: [] },
    });
    const { result } = renderHook(() => useMyApplications());

    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.hiredMentorshipRoles).toEqual([]);
  });

  it("returns no roles when the response carries no role field at all", async () => {
    api.listMyApplications.mockResolvedValue({ data: { applications: [] } });
    const { result } = renderHook(() => useMyApplications());

    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.hiredMentorshipRoles).toEqual([]);
  });

  it("exposes the applications list", async () => {
    const rows = [row({ applicationId: 7 })];
    api.listMyApplications.mockResolvedValue({
      data: { applications: rows, mentorshipRoles: ["mentor"] },
    });
    const { result } = renderHook(() => useMyApplications());

    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.applications).toEqual(rows);
  });

  it("is empty for an empty application list", async () => {
    api.listMyApplications.mockResolvedValue({
      data: { applications: [], mentorshipRoles: [] },
    });
    const { result } = renderHook(() => useMyApplications());

    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.hiredMentorshipRoles).toEqual([]);
    expect(result.current.applications).toEqual([]);
  });

  // A reload that fails leaves nothing standing: the mentorship section is
  // gated on these roles, and stale ones would keep it offering entry
  // points no response confirms.
  it("clears previously loaded roles when a reload fails", async () => {
    api.listMyApplications.mockResolvedValue({
      data: { applications: [row()], mentorshipRoles: ["mentor"] },
    });
    const { result } = renderHook(() => useMyApplications());
    await waitFor(() =>
      expect(result.current.hiredMentorshipRoles).toEqual(["mentor"]),
    );

    api.listMyApplications.mockRejectedValue(new Error("network error"));
    result.current.load();

    await waitFor(() => expect(result.current.loadError).toBe(true));
    expect(result.current.hiredMentorshipRoles).toEqual([]);
  });
});
