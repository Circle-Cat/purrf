import { describe, it, expect, vi, beforeEach } from "vitest";
import request from "@/utils/request";
import * as inboxApi from "@/api/inboxApi";
import {
  listInboxThreads,
  getInboxCount,
  getInboxThread,
  replyToInboxThread,
  archiveInboxThread,
  unarchiveInboxThread,
  assignInboxThread,
  moveInboxThread,
  getInboxAssignOptions,
  searchInboxPeople,
  inboxAttachmentUrl,
} from "@/api/inboxApi";
import { INBOX_PERMISSIONS, PERMISSIONS } from "@/constants/Permissions";
import { ROUTE_PATHS } from "@/constants/RoutePaths";

vi.mock("@/utils/request", () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
    defaults: { baseURL: "/api" },
  },
}));

describe("inboxApi", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("listInboxThreads GETs /inbox/threads with params", async () => {
    await listInboxThreads({ tab: "open" });
    expect(request.get).toHaveBeenCalledWith("/inbox/threads", {
      params: { tab: "open" },
    });
  });

  it("getInboxCount GETs /inbox/count", async () => {
    await getInboxCount();
    expect(request.get).toHaveBeenCalledWith("/inbox/count");
  });

  it("getInboxThread GETs /inbox/threads/:id", async () => {
    await getInboxThread(5);
    expect(request.get).toHaveBeenCalledWith("/inbox/threads/5");
  });

  it("replyToInboxThread POSTs the body to /reply", async () => {
    await replyToInboxThread(5, { body: "hi" });
    expect(request.post).toHaveBeenCalledWith("/inbox/threads/5/reply", {
      body: "hi",
    });
  });

  it("archiveInboxThread POSTs /archive", async () => {
    await archiveInboxThread(5);
    expect(request.post).toHaveBeenCalledWith("/inbox/threads/5/archive");
  });

  it("unarchiveInboxThread POSTs /unarchive", async () => {
    await unarchiveInboxThread(5);
    expect(request.post).toHaveBeenCalledWith("/inbox/threads/5/unarchive");
  });

  it("assignInboxThread PUTs the body to /assignment", async () => {
    await assignInboxThread(5, { userId: 9 });
    expect(request.put).toHaveBeenCalledWith("/inbox/threads/5/assignment", {
      userId: 9,
    });
  });

  it("has no unassign call", () => {
    expect(inboxApi.unassignInboxThread).toBeUndefined();
  });

  it("moveInboxThread POSTs {service} to /move", async () => {
    await moveInboxThread(5, "mentorship");
    expect(request.post).toHaveBeenCalledWith("/inbox/threads/5/move", {
      service: "mentorship",
    });
  });

  it("getInboxAssignOptions GETs /assign-options with userId", async () => {
    await getInboxAssignOptions(5, 9);
    expect(request.get).toHaveBeenCalledWith(
      "/inbox/threads/5/assign-options",
      { params: { userId: 9 } },
    );
  });

  it("searchInboxPeople GETs /inbox/people with q", async () => {
    await searchInboxPeople("wang");
    expect(request.get).toHaveBeenCalledWith("/inbox/people", {
      params: { q: "wang" },
    });
  });

  it("inboxAttachmentUrl builds the absolute attachment URL", () => {
    expect(inboxAttachmentUrl(5, 7, 0)).toBe(
      "/api/inbox/threads/5/messages/7/attachments/0",
    );
  });

  it("exposes the route path and permission set", () => {
    expect(ROUTE_PATHS.INBOX).toBe("/inbox");
    expect(PERMISSIONS.INQUIRIES_MANAGE).toBe("inquiries.manage");
    expect(INBOX_PERMISSIONS).toEqual([
      "mentorship.admin.write",
      "recruiting.application.advance",
      "inquiries.manage",
    ]);
  });
});
