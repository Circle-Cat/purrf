import { describe, it, expect, vi, beforeEach } from "vitest";
import request from "@/utils/request";
import {
  cancelEmailSend,
  createEmailSend,
  listKitDrafts,
  listNotifiedStages,
  listPersonSends,
  markNotified,
  refreshEmailPreview,
  confirmEmailSend,
} from "@/api/mentorshipEmailApi";

vi.mock("@/utils/request", () => ({
  default: { get: vi.fn(), post: vi.fn() },
}));

describe("mentorshipEmailApi", () => {
  beforeEach(() => vi.clearAllMocks());

  it("lists Kit drafts with Kit's timeout", async () => {
    request.get.mockResolvedValue({
      success: true,
      data: [{ id: 9, subject: "Hi", createdAt: "2026-10-01T00:00:00Z" }],
    });
    await expect(listKitDrafts()).resolves.toEqual([
      { id: 9, subject: "Hi", createdAt: "2026-10-01T00:00:00Z" },
    ]);
    expect(request.get).toHaveBeenCalledWith("/mentorship/admin/kit-drafts", {
      timeout: 60000,
    });
  });

  it("lists the stages notified in a round", async () => {
    request.get.mockResolvedValue({
      success: true,
      data: [{ userId: 11, stages: ["admission"] }],
    });
    await expect(listNotifiedStages(7)).resolves.toEqual([
      { userId: 11, stages: ["admission"] },
    ]);
    expect(request.get).toHaveBeenCalledWith(
      "/mentorship/admin/email-sends/notified",
      { params: { roundId: 7 } },
    );
  });

  it("lists one person's sends in a round", async () => {
    const send = {
      sendId: 14,
      stage: "match_result",
      subject: "Your match",
      delivered: true,
      reason: null,
      at: "2026-10-12T16:00:00Z",
    };
    request.get.mockResolvedValue({ success: true, data: [send] });
    await expect(listPersonSends(7, 3104)).resolves.toEqual([send]);
    expect(request.get).toHaveBeenCalledWith(
      "/mentorship/admin/email-sends/person",
      { params: { roundId: 7, userId: 3104 } },
    );
  });

  it("marks people notified in a round", async () => {
    request.post.mockResolvedValue({
      success: true,
      data: { marked: [11], skipped: [] },
    });
    await expect(
      markNotified(7, {
        userIds: [11],
        stage: "admission",
        body: "Sent on Teams",
      }),
    ).resolves.toEqual({ marked: [11], skipped: [] });
    expect(request.post).toHaveBeenCalledWith(
      "/mentorship/admin/rounds/7/notifications/mark",
      { userIds: [11], stage: "admission", body: "Sent on Teams" },
    );
  });

  it("cancels a send", async () => {
    request.post.mockResolvedValue({ success: true, data: { sendId: 5 } });
    await expect(cancelEmailSend(5)).resolves.toEqual({ sendId: 5 });
    expect(request.post).toHaveBeenCalledWith(
      "/mentorship/admin/email-sends/5/cancel",
      undefined,
      { timeout: 60000 },
    );
  });

  it("creates a send with camelCase body", async () => {
    request.post.mockResolvedValue({ success: true, data: { sendId: 5 } });
    await createEmailSend({
      roundId: 1,
      stage: "match_result",
      kitDraftId: 11,
      userIds: [1],
    });
    expect(request.post).toHaveBeenCalledWith(
      "/mentorship/admin/email-sends",
      {
        roundId: 1,
        stage: "match_result",
        kitDraftId: 11,
        userIds: [1],
      },
      { timeout: 60000 },
    );
  });

  it("uses a longer timeout for Kit-backed calls", async () => {
    request.post.mockResolvedValue({ success: true, data: {} });
    await refreshEmailPreview(5);
    expect(request.post.mock.calls[0][2]).toEqual({ timeout: 60000 });
  });

  it("schedules with the preview token", async () => {
    request.post.mockResolvedValue({ success: true, data: {} });
    await confirmEmailSend(5, {
      sendAt: "2026-10-08T13:00:00Z",
      previewToken: "t",
    });
    expect(request.post).toHaveBeenCalledWith(
      "/mentorship/admin/email-sends/5/confirm",
      { sendAt: "2026-10-08T13:00:00Z", previewToken: "t" },
      { timeout: 60000 },
    );
  });
});
