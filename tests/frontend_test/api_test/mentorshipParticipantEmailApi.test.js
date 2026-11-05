import { vi, describe, it, expect, beforeEach } from "vitest";
import request from "@/utils/request";
import {
  getParticipantEmails,
  participantEmailAttachmentUrl,
  refreshParticipantEmails,
  replyParticipantEmail,
  sendParticipantEmail,
} from "@/api/mentorshipApi";

vi.mock("@/utils/request", () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
    defaults: { baseURL: "/api" },
  },
}));

const BASE = "/mentorship/admin/rounds/7/participants/3104/emails";

describe("mentorship participant email API", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    request.get.mockResolvedValue({ data: {} });
    request.post.mockResolvedValue({ data: {} });
  });

  it("reads the conversation", async () => {
    await getParticipantEmails(7, 3104);
    expect(request.get).toHaveBeenCalledWith(BASE);
  });

  it("sends a new email with only to, subject and body", async () => {
    await sendParticipantEmail(7, 3104, {
      to: ["alice@x.com"],
      subject: "Checking in",
      body: "How is it going?",
      threadId: null,
    });
    expect(request.post).toHaveBeenCalledWith(BASE, {
      to: ["alice@x.com"],
      subject: "Checking in",
      body: "How is it going?",
    });
  });

  it("replies with the body and the last message seen", async () => {
    await replyParticipantEmail(7, 3104, 41, {
      body: "Thanks",
      lastSeenMessageId: 411,
    });
    expect(request.post).toHaveBeenCalledWith(`${BASE}/41/reply`, {
      body: "Thanks",
      lastSeenMessageId: 411,
    });
  });

  it("refreshes with no body", async () => {
    await refreshParticipantEmails(7, 3104);
    expect(request.post).toHaveBeenCalledWith(`${BASE}/refresh`);
  });

  it("builds the attachment download URL", () => {
    expect(participantEmailAttachmentUrl(7, 3104, 411, 0)).toBe(
      `/api${BASE}/messages/411/attachments/0`,
    );
  });
});
