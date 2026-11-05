import { renderHook, waitFor, act } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";

import { useEmailSettings } from "@/pages/SignInSecurity/hooks/useEmailSettings";
import { listEmails } from "@/api/emailApi";
import { toast } from "sonner";

vi.mock("@/api/emailApi", () => ({
  listEmails: vi.fn(),
}));

vi.spyOn(toast, "error").mockImplementation(() => {});

const fullPayload = {
  emails: [
    {
      emailId: 1,
      email: "alice@gmail.com",
      otpConfirmed: true,
      isPrimary: true,
      addedAt: "2026-01-01T00:00:00Z",
      linkedIdentityCount: 1,
    },
  ],
  internalIdentities: [
    {
      identityId: 9,
      subjectIdentifier: "auth0|work",
      emailClaim: "alice@circlecat.org",
      linkedAt: "2026-01-01T00:00:00Z",
      lastUsedAt: "2026-02-01T00:00:00Z",
    },
  ],
  externalIdentities: [
    {
      identityId: 1,
      subjectIdentifier: "google-oauth2|1",
      emailClaim: "alice@gmail.com",
    },
  ],
};

describe("useEmailSettings", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("starts in a loading state", () => {
    listEmails.mockReturnValue(new Promise(() => {}));

    const { result } = renderHook(() => useEmailSettings());

    expect(result.current.isLoading).toBe(true);
    expect(result.current.emails).toEqual([]);
    expect(result.current.internalIdentities).toEqual([]);
    expect(result.current.externalIdentities).toEqual([]);
  });

  it("loads emails and identities on mount", async () => {
    listEmails.mockResolvedValue({ data: fullPayload });

    const { result } = renderHook(() => useEmailSettings());

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(listEmails).toHaveBeenCalledTimes(1);
    expect(result.current.emails).toEqual(fullPayload.emails);
    expect(result.current.internalIdentities).toEqual(
      fullPayload.internalIdentities,
    );
    expect(result.current.externalIdentities).toEqual(
      fullPayload.externalIdentities,
    );
    expect(toast.error).not.toHaveBeenCalled();
  });

  it("falls back to safe defaults when the payload omits fields", async () => {
    listEmails.mockResolvedValue({ data: {} });

    const { result } = renderHook(() => useEmailSettings());

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(result.current.emails).toEqual([]);
    expect(result.current.internalIdentities).toEqual([]);
    expect(result.current.externalIdentities).toEqual([]);
  });

  it("falls back to safe defaults when there is no data object", async () => {
    listEmails.mockResolvedValue({});

    const { result } = renderHook(() => useEmailSettings());

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(result.current.emails).toEqual([]);
    expect(result.current.internalIdentities).toEqual([]);
    expect(result.current.externalIdentities).toEqual([]);
  });

  it("shows the server message in a toast on failure", async () => {
    listEmails.mockRejectedValue({
      response: { data: { message: "Boom from server" } },
    });

    const { result } = renderHook(() => useEmailSettings());

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(toast.error).toHaveBeenCalledWith("Boom from server");
    expect(result.current.emails).toEqual([]);
  });

  it("shows a generic toast message when the error has no server message", async () => {
    listEmails.mockRejectedValue(new Error("network"));

    const { result } = renderHook(() => useEmailSettings());

    await waitFor(() => expect(result.current.isLoading).toBe(false));

    expect(toast.error).toHaveBeenCalledWith(
      "Could not load your email settings. Please try again.",
    );
  });

  it("re-pulls the view when refresh is called", async () => {
    listEmails.mockResolvedValue({ data: fullPayload });

    const { result } = renderHook(() => useEmailSettings());
    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(listEmails).toHaveBeenCalledTimes(1);

    const updated = {
      ...fullPayload,
      emails: [
        ...fullPayload.emails,
        {
          emailId: 2,
          email: "bob@gmail.com",
          otpConfirmed: false,
          isPrimary: false,
          addedAt: "2026-03-01T00:00:00Z",
          linkedIdentityCount: 0,
        },
      ],
    };
    listEmails.mockResolvedValue({ data: updated });

    await act(async () => {
      await result.current.refresh();
    });

    expect(listEmails).toHaveBeenCalledTimes(2);
    expect(result.current.emails).toHaveLength(2);
  });
});
