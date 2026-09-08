import { describe, it, expect, vi, beforeEach } from "vitest";
import request from "@/utils/request";
import {
  getAccounts,
  getSignInMethods,
  deactivateAccount,
  reactivateAccount,
  unblockAccount,
  blockAccount,
  getBlockPreflight,
  createBlockRequest,
  getPendingBlockRequests,
  reassignBlockRequest,
  decideBlockRequest,
  getUserAdmins,
} from "@/api/adminAccountsApi";

vi.mock("@/utils/request", () => ({
  default: { get: vi.fn(), post: vi.fn() },
}));

describe("adminAccountsApi", () => {
  beforeEach(() => vi.clearAllMocks());

  it("sends snake_case query params when listing accounts", async () => {
    request.get.mockResolvedValue({ data: { accounts: [], total: 0 } });

    await getAccounts({
      search: "min",
      status: "blocked",
      limit: 20,
      offset: 0,
    });

    expect(request.get).toHaveBeenCalledWith("/admin/accounts", {
      params: {
        search: "min",
        user_id: undefined,
        status: "blocked",
        user_type: undefined,
        limit: 20,
        offset: 0,
      },
    });
  });

  it("returns the envelope untouched", async () => {
    const envelope = { data: { accounts: [{ userId: 1 }], total: 1 } };
    request.get.mockResolvedValue(envelope);

    expect(await getAccounts()).toEqual(envelope);
  });

  it("reads sign-in methods for one account", async () => {
    request.get.mockResolvedValue({ data: { emails: [], identities: [] } });

    await getSignInMethods(7);

    expect(request.get).toHaveBeenCalledWith(
      "/admin/accounts/7/sign-in-methods",
    );
  });

  it("posts the optional note under the key the backend names it", async () => {
    // The body field is `note`, not `reason`: deactivation is not a finding of
    // fault, and the backend DTO reflects that.
    await deactivateAccount(7, "moving on");

    expect(request.post).toHaveBeenCalledWith("/admin/accounts/7/deactivate", {
      note: "moving on",
    });
  });

  it("sends no body when reactivating or unblocking", async () => {
    await reactivateAccount(7);
    await unblockAccount(7);

    expect(request.post).toHaveBeenNthCalledWith(
      1,
      "/admin/accounts/7/reactivate",
    );
    expect(request.post).toHaveBeenNthCalledWith(
      2,
      "/admin/accounts/7/unblock",
    );
  });

  it("posts a reason when blocking directly", async () => {
    await blockAccount(7, "second no-show");

    expect(request.post).toHaveBeenCalledWith("/admin/accounts/7/block", {
      reason: "second no-show",
    });
  });

  it("reads the pre-flight for one user", async () => {
    request.get.mockResolvedValue({
      data: { applicationCount: 2, interviewTimes: [] },
    });

    await getBlockPreflight(7);

    expect(request.get).toHaveBeenCalledWith("/block-preflight/7");
  });

  it("puts raised_from in the query string, not the body", async () => {
    // BaseRequestDto forbids extra body fields, and raised_from describes
    // where the caller is standing rather than what they are asking for.
    await createBlockRequest(
      { userId: 7, reason: "second no-show", reviewerId: 9 },
      "recruiting_board",
    );

    expect(request.post).toHaveBeenCalledWith(
      "/block-requests",
      { userId: 7, reason: "second no-show", reviewerId: 9 },
      { params: { raised_from: "recruiting_board" } },
    );
  });

  it("lists only the caller's own pending requests", async () => {
    request.get.mockResolvedValue({ data: [] });

    await getPendingBlockRequests();

    expect(request.get).toHaveBeenCalledWith("/block-requests");
  });

  it("reassigns and decides by request id", async () => {
    await reassignBlockRequest(41, 11);
    await decideBlockRequest(41, false, "not enough");

    expect(request.post).toHaveBeenNthCalledWith(
      1,
      "/block-requests/41/reassign",
      { reviewerId: 11 },
    );
    expect(request.post).toHaveBeenNthCalledWith(
      2,
      "/block-requests/41/decide",
      { approved: false, note: "not enough" },
    );
  });

  it("reads the pickable reviewers", async () => {
    request.get.mockResolvedValue({ data: [] });

    await getUserAdmins();

    expect(request.get).toHaveBeenCalledWith("/block-request-reviewers");
  });
});
