import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { toast } from "sonner";
import AdminAccounts from "@/pages/AdminAccounts";
import * as api from "@/api/adminAccountsApi";

vi.mock("@/api/adminAccountsApi");
// Spy on the real toast: in the Bazel sandbox a `vi.mock("sonner", factory)`
// does not intercept the module the page already resolved.
vi.spyOn(toast, "error").mockImplementation(() => {});
vi.spyOn(toast, "success").mockImplementation(() => {});

// Who is looking. The page has no permission gate of its own -- the route
// carries user.admin -- so these tests flip the holder to prove it.
const authState = vi.hoisted(() => ({
  userId: 900,
  permissions: ["user.admin"],
}));
vi.mock("@/context/auth/AuthContext", () => ({
  useAuth: () => ({
    user: { userId: authState.userId },
    permissions: authState.permissions,
  }),
}));

const account = (overrides = {}) => ({
  userId: 1203,
  primaryEmail: "sam@example.com",
  firstName: "Sam",
  lastName: "Rivera",
  preferredName: null,
  userType: "internal",
  isSuperAdmin: false,
  isActive: true,
  deactivatedAt: null,
  deactivatedBy: null,
  deactivatedByName: null,
  deactivatedReason: null,
  isBlocked: false,
  blockedAt: null,
  blockedBy: null,
  blockedByName: null,
  blockedReason: null,
  hasPendingBlockRequest: false,
  ...overrides,
});

const signInMethods = (overrides = {}) => ({
  emails: [
    {
      email: "sam@example.com",
      otpConfirmed: true,
      isPrimary: true,
      lastLoginAt: "2026-09-01T10:00:00Z",
    },
  ],
  identities: [
    {
      subjectIdentifier: "google-oauth2|1",
      emailClaim: "sam@example.com",
      linkedAt: "2026-01-01T00:00:00Z",
      lastLoginAt: "2026-09-01T10:00:00Z",
    },
  ],
  ...overrides,
});

const request = (overrides = {}) => ({
  id: 7,
  targetUserId: 1203,
  targetName: "Sam Rivera",
  raisedBy: 42,
  raisedByName: "Dana Raiser",
  raisedFrom: "recruiting_board",
  raisedAt: "2026-09-01T10:00:00Z",
  reason: "Submitted AI-generated answers.",
  reviewerId: 900,
  reviewerName: "Me Reviewer",
  status: "pending",
  decidedBy: null,
  decidedByName: null,
  decidedAt: null,
  decisionNote: null,
  ...overrides,
});

const renderPage = (search = "?user_id=1203") => {
  const router = createMemoryRouter(
    [{ path: "/admin/accounts", element: <AdminAccounts /> }],
    { initialEntries: [`/admin/accounts${search}`] },
  );
  return { ...render(<RouterProvider router={router} />), router };
};

/** Wait until the account has loaded. */
const waitLoaded = () => screen.findByText("Sam Rivera");

beforeEach(() => {
  vi.clearAllMocks();
  authState.userId = 900;
  authState.permissions = ["user.admin"];
  api.getAccounts.mockResolvedValue({
    data: { accounts: [account()], total: 1 },
  });
  api.getSignInMethods.mockResolvedValue({ data: signInMethods() });
  api.getPendingBlockRequests.mockResolvedValue({ data: [] });
  api.getBlockPreflight.mockResolvedValue({
    data: { applicationCount: 0, interviewTimes: [] },
  });
  api.deactivateAccount.mockResolvedValue({ data: null });
  api.reactivateAccount.mockResolvedValue({ data: null });
  api.unblockAccount.mockResolvedValue({ data: null });
  api.blockAccount.mockResolvedValue({ data: null });
  api.decideBlockRequest.mockResolvedValue({ data: null });
});

describe("AccountDetailPage — getting back out", () => {
  it("names where back goes instead of saying Back", async () => {
    renderPage();
    await waitLoaded();
    expect(screen.getByRole("link", { name: /Accounts/ })).toBeInTheDocument();
    expect(
      screen.queryByRole("link", { name: /^Back$/ }),
    ).not.toBeInTheDocument();
  });

  it("keeps filters and highlights the row it came from", async () => {
    renderPage("?status=blocked");
    fireEvent.click(
      await screen.findByRole("button", { name: "Open account 1203" }),
    );
    await waitLoaded();

    fireEvent.click(screen.getByRole("link", { name: /Accounts/ }));

    await waitFor(() =>
      expect(api.getAccounts).toHaveBeenLastCalledWith(
        expect.objectContaining({ status: "blocked" }),
      ),
    );
    expect(await screen.findByTestId("account-row-1203")).toHaveAttribute(
      "data-focused",
      "true",
    );
  });
});

describe("AccountDetailPage — sign-in methods", () => {
  it("says so explicitly when there is no sign-in identity", async () => {
    api.getSignInMethods.mockResolvedValue({
      data: signInMethods({ identities: [] }),
    });
    renderPage();
    await waitLoaded();
    expect(
      screen.getByText(/has only ever signed in with an email code/i),
    ).toBeInTheDocument();
  });

  it("lists a linked identity when there is one", async () => {
    renderPage();
    await waitLoaded();
    expect(screen.getByText(/Linked identities/)).toBeInTheDocument();
    expect(
      screen.queryByText(/has only ever signed in with an email code/i),
    ).not.toBeInTheDocument();
  });
});

describe("AccountDetailPage — the permission page next door", () => {
  it("links to permissions when the viewer may manage them", async () => {
    authState.permissions = ["user.admin", "permission.manage"];
    renderPage();
    await waitLoaded();
    expect(
      screen.getByRole("link", { name: /Manage permissions/ }),
    ).toHaveAttribute("href", expect.stringContaining("user_id=1203"));
  });

  it("drops the section entirely for a viewer who may not", async () => {
    // The permission page keeps its own gate, so the link was safe -- but it
    // led a user.admin holder to a full-page 403 that never says which
    // permission is missing. The heading goes with the link, or the section
    // is left standing empty.
    authState.permissions = ["user.admin"];
    renderPage();
    await waitLoaded();
    expect(
      screen.queryByRole("link", { name: /Manage permissions/ }),
    ).not.toBeInTheDocument();
    expect(screen.queryByText("Permissions")).not.toBeInTheDocument();
  });
});

describe("AccountDetailPage — the block request card", () => {
  it("renders the request card only for the named reviewer", async () => {
    api.getPendingBlockRequests.mockResolvedValue({ data: [request()] });
    renderPage();
    await waitLoaded();
    expect(
      await screen.findByRole("button", { name: /Approve and block/ }),
    ).toBeEnabled();
    expect(
      screen.getByText("Submitted AI-generated answers."),
    ).toBeInTheDocument();
    expect(screen.getByText(/Dana Raiser/)).toBeInTheDocument();
  });

  it("renders no request card when none is assigned to me", async () => {
    api.getPendingBlockRequests.mockResolvedValue({
      data: [request({ id: 9, targetUserId: 1300 })],
    });
    renderPage();
    await waitLoaded();
    expect(
      screen.queryByRole("button", { name: /Approve and block/ }),
    ).toBeNull();
  });

  it("approves through the decide endpoint", async () => {
    api.getPendingBlockRequests.mockResolvedValue({ data: [request()] });
    renderPage();
    fireEvent.click(
      await screen.findByRole("button", { name: /Approve and block/ }),
    );
    await waitFor(() =>
      expect(api.decideBlockRequest).toHaveBeenCalledWith(7, true, null),
    );
  });

  it("sends the reviewer's note so the raiser is told why", async () => {
    // The outcome email renders this note. Without a field for it a rejection
    // reaches the raiser as a bare no.
    api.getPendingBlockRequests.mockResolvedValue({ data: [request()] });
    renderPage();
    fireEvent.change(await screen.findByLabelText(/Note/), {
      target: { value: "  not enough evidence  " },
    });
    fireEvent.click(screen.getByRole("button", { name: "Reject" }));

    await waitFor(() =>
      expect(api.decideBlockRequest).toHaveBeenCalledWith(
        7,
        false,
        "not enough evidence",
      ),
    );
  });

  it("rejects through the same endpoint", async () => {
    api.getPendingBlockRequests.mockResolvedValue({ data: [request()] });
    renderPage();
    fireEvent.click(await screen.findByRole("button", { name: "Reject" }));
    await waitFor(() =>
      expect(api.decideBlockRequest).toHaveBeenCalledWith(7, false, null),
    );
  });
});

describe("AccountDetailPage — actions", () => {
  it("deactivates through the dialog, note and all", async () => {
    renderPage();
    await waitLoaded();
    fireEvent.click(screen.getByRole("button", { name: "Deactivate" }));

    fireEvent.change(screen.getByLabelText(/Note/), {
      target: { value: "Asked to leave Purrf" },
    });
    fireEvent.click(
      screen.getAllByRole("button", { name: "Deactivate" }).at(-1),
    );

    await waitFor(() =>
      expect(api.deactivateAccount).toHaveBeenCalledWith(
        1203,
        "Asked to leave Purrf",
      ),
    );
  });

  it("offers Reactivate instead once the account is off", async () => {
    api.getAccounts.mockResolvedValue({
      data: { accounts: [account({ isActive: false })], total: 1 },
    });
    renderPage();
    await waitLoaded();
    fireEvent.click(screen.getByRole("button", { name: "Reactivate" }));
    await waitFor(() =>
      expect(api.reactivateAccount).toHaveBeenCalledWith(1203),
    );
  });

  it("unblocks a blocked account", async () => {
    api.getAccounts.mockResolvedValue({
      data: { accounts: [account({ isBlocked: true })], total: 1 },
    });
    renderPage();
    await waitLoaded();
    fireEvent.click(screen.getByRole("button", { name: "Unblock" }));
    await waitFor(() => expect(api.unblockAccount).toHaveBeenCalledWith(1203));
  });

  it("reads the pre-flight when the block dialog opens, then blocks with a reason", async () => {
    renderPage();
    await waitLoaded();
    fireEvent.click(screen.getByRole("button", { name: "Block" }));

    await waitFor(() =>
      expect(api.getBlockPreflight).toHaveBeenCalledWith(1203),
    );
    fireEvent.change(screen.getByLabelText(/Reason/), {
      target: { value: "Sanctioned" },
    });
    fireEvent.click(screen.getAllByRole("button", { name: "Block" }).at(-1));

    await waitFor(() =>
      expect(api.blockAccount).toHaveBeenCalledWith(1203, "Sanctioned"),
    );
  });

  it("gates its own actions no second time: the route already carries user.admin", async () => {
    // Every action on this page is reachable on user.admin alone. The one
    // thing that reads the viewer's other permissions is the cross-link to
    // the permission page, which is not an action of this page.
    authState.permissions = [];
    renderPage();
    await waitLoaded();
    expect(screen.getByRole("button", { name: "Deactivate" })).toBeEnabled();
    expect(screen.getByRole("button", { name: "Block" })).toBeEnabled();
  });

  it("does not offer the two actions the backend refuses on yourself", async () => {
    // Deactivating or blocking your own account locks you out of the only
    // console that can undo it. The backend answers 403; the click should not
    // be on offer in the first place.
    authState.userId = 1203;
    renderPage();

    const deactivate = await screen.findByRole("button", {
      name: "Deactivate",
    });
    expect(deactivate).toBeDisabled();
    expect(deactivate).toHaveAttribute(
      "title",
      "You cannot deactivate your own account",
    );
    expect(screen.getByRole("button", { name: "Block" })).toBeDisabled();
  });

  it("says the sign-in methods could not be read instead of inventing a fact", async () => {
    // "No linked identity" is a claim about the person. It may only appear
    // when the read that establishes it succeeded.
    api.getSignInMethods.mockRejectedValue(new Error("boom"));
    renderPage();

    // Both halves of the section say it: neither the addresses nor the
    // identities were established by a read that failed.
    expect(
      await screen.findAllByText(
        /Couldn't read this account's sign-in methods/,
      ),
    ).toHaveLength(2);
    expect(
      screen.queryByText(/has only ever signed in with an email code/),
    ).toBeNull();
  });

  it("warns when the chip says a request exists but the request could not be read", async () => {
    // Without this the operator sees the chip, no card, no reason -- and the
    // Block button beside it would close that undecided request as superseded.
    api.getAccounts.mockResolvedValue({
      data: { accounts: [account({ hasPendingBlockRequest: true })], total: 1 },
    });
    api.getPendingBlockRequests.mockRejectedValue(new Error("boom"));
    renderPage();

    expect(
      await screen.findByText(/couldn't be loaded. Reload before acting/),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /Approve and block/ }),
    ).toBeNull();
  });

  it("says which account is missing rather than rendering an empty shell", async () => {
    api.getAccounts.mockResolvedValue({ data: { accounts: [], total: 0 } });
    renderPage();
    expect(
      await screen.findByText("No account with user ID 1203."),
    ).toBeInTheDocument();
  });
});
