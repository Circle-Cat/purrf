import { describe, it, expect, vi, beforeEach } from "vitest";
import {
  render,
  screen,
  fireEvent,
  waitFor,
  within,
} from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { toast } from "sonner";
import AdminAccounts from "@/pages/AdminAccounts";
import AccountList from "@/pages/AdminAccounts/components/AccountList";
import * as api from "@/api/adminAccountsApi";

vi.mock("@/api/adminAccountsApi");
// Bazel-sandbox module resolution: a `vi.mock("sonner", factory)` does not
// intercept the module the page resolved at import time. Spy on the real
// toast instead, as the other page tests do.
vi.spyOn(toast, "error").mockImplementation(() => {});
vi.spyOn(toast, "success").mockImplementation(() => {});

// The console reads the caller through useAuth(); a hoisted holder lets a test
// change who is looking before render.
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

/** One UserAccountRowDto, with the whole envelope the backend actually ships. */
const row = (overrides = {}) => ({
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

/** One BlockRequestDto waiting on the caller. */
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

/** Render the presentational list alone, with everything it needs stubbed. */
const renderList = (props = {}) =>
  render(
    <AccountList
      accounts={[row()]}
      total={1}
      loading={false}
      search=""
      onSearchChange={vi.fn()}
      userId=""
      onUserIdChange={vi.fn()}
      onSearchSubmit={vi.fn()}
      userType=""
      onUserTypeChange={vi.fn()}
      status=""
      onStatusChange={vi.fn()}
      offset={0}
      limit={20}
      onPrev={vi.fn()}
      onNext={vi.fn()}
      onOpen={vi.fn()}
      focusedUserId={null}
      {...props}
    />,
  );

/** Render the whole page on the real route, so the query string is live. */
const renderPage = (search = "") => {
  const router = createMemoryRouter(
    [{ path: "/admin/accounts", element: <AdminAccounts /> }],
    { initialEntries: [`/admin/accounts${search}`] },
  );
  return { ...render(<RouterProvider router={router} />), router };
};

beforeEach(() => {
  vi.clearAllMocks();
  api.getAccounts.mockResolvedValue({
    data: { accounts: [row()], total: 1 },
  });
  api.getPendingBlockRequests.mockResolvedValue({ data: [] });
});

describe("AccountList state chips", () => {
  // Scoped to the row: the Status filter carries options with the same words,
  // so a bare getByText would match the picker instead of the chip.
  const chipsIn = () => within(screen.getByTestId("account-row-1203"));

  it("renders Blocked and Deactivated on one row", () => {
    renderList({ accounts: [row({ isBlocked: true, isActive: false })] });
    expect(chipsIn().getByText("Blocked")).toBeInTheDocument();
    expect(chipsIn().getByText("Deactivated")).toBeInTheDocument();
  });

  it("shows Block requested from the caller-scoped flag", () => {
    renderList({ accounts: [row({ hasPendingBlockRequest: true })] });
    expect(chipsIn().getByText("Block requested")).toBeInTheDocument();
  });

  it("does not show Block requested when the flag is false", () => {
    renderList({ accounts: [row({ hasPendingBlockRequest: false })] });
    expect(chipsIn().queryByText("Block requested")).not.toBeInTheDocument();
  });
});

describe("AccountList columns", () => {
  const cellsIn = () => within(screen.getByTestId("account-row-1203"));

  it("names the email column for the field it actually shows", () => {
    // The row carries primary_email specifically -- a person can hold several
    // addresses, and "Email" reads as though this were all of them.
    renderList();
    expect(
      screen.getByRole("columnheader", { name: "Primary contact email" }),
    ).toBeInTheDocument();
  });

  it("gives each of the three names its own column", () => {
    // Same shape as the permission page's user list, which is the product rule
    // for admin surfaces: the three names travel and render separately.
    renderList();
    for (const header of ["First Name", "Last Name", "Preferred Name"]) {
      expect(
        screen.getByRole("columnheader", { name: header }),
      ).toBeInTheDocument();
    }
    expect(cellsIn().getByText("Sam")).toBeInTheDocument();
    expect(cellsIn().getByText("Rivera")).toBeInTheDocument();
  });

  it("shows a dash when someone has no preferred name", () => {
    renderList({ accounts: [row({ preferredName: null })] });
    expect(cellsIn().getByText("\u2014")).toBeInTheDocument();
  });

  it("shows the preferred name on its own when there is one", () => {
    renderList({ accounts: [row({ preferredName: "Sammy" })] });
    expect(cellsIn().getByText("Sammy")).toBeInTheDocument();
  });
});

describe("AccountList controls", () => {
  it("searches over more than a name, and says so", () => {
    renderList();
    expect(
      screen.getByPlaceholderText("Name, email, or block reason"),
    ).toBeInTheDocument();
  });

  it("gives the user id a box of its own", () => {
    renderList();
    expect(screen.getByPlaceholderText("User ID")).toBeInTheDocument();
  });

  it("keeps everything but digits out of the id box", () => {
    const onUserIdChange = vi.fn();
    renderList({ onUserIdChange });

    fireEvent.change(screen.getByPlaceholderText("User ID"), {
      target: { value: "12a3" },
    });

    expect(onUserIdChange).toHaveBeenCalledWith("123");
  });

  it("offers the Type and Status filters as labelled native selects", () => {
    renderList();
    expect(screen.getByLabelText("Type")).toBeInTheDocument();
    expect(screen.getByLabelText("Status")).toBeInTheDocument();
  });

  it("reports the page window and disables Prev on the first page", () => {
    renderList({ total: 42 });
    expect(screen.getByText("1–20 of 42")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Prev" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Next" })).toBeEnabled();
  });

  it("marks the row the viewer came back from", () => {
    renderList({ focusedUserId: 1203 });
    expect(screen.getByTestId("account-row-1203")).toHaveAttribute(
      "data-focused",
      "true",
    );
  });
});

describe("AdminAccounts list page", () => {
  it("deep-links ?status=blocked into the filter", async () => {
    renderPage("?status=blocked");
    await waitFor(() =>
      expect(api.getAccounts).toHaveBeenCalledWith(
        expect.objectContaining({ status: "blocked" }),
      ),
    );
    expect(screen.getByLabelText("Status")).toHaveValue("blocked");
  });

  it("puts a chosen filter into the query string so the list survives a return trip", async () => {
    const { router } = renderPage();
    await screen.findByText("sam@example.com");

    fireEvent.change(screen.getByLabelText("Type"), {
      target: { value: "external" },
    });

    await waitFor(() =>
      expect(router.state.location.search).toContain("user_type=external"),
    );
    await waitFor(() =>
      expect(api.getAccounts).toHaveBeenLastCalledWith(
        expect.objectContaining({ userType: "external" }),
      ),
    );
  });

  it("commits the search box to the query string on Enter", async () => {
    const { router } = renderPage();
    await screen.findByText("sam@example.com");

    const box = screen.getByPlaceholderText("Name, email, or block reason");
    fireEvent.change(box, { target: { value: "ai-generated" } });
    fireEvent.keyDown(box, { key: "Enter" });

    await waitFor(() =>
      expect(router.state.location.search).toContain("search=ai-generated"),
    );
    await waitFor(() =>
      expect(api.getAccounts).toHaveBeenLastCalledWith(
        expect.objectContaining({ search: "ai-generated" }),
      ),
    );
  });

  it("commits the id box under its own key, not the one that opens a person", async () => {
    const { router } = renderPage();
    await screen.findByText("sam@example.com");

    const box = screen.getByPlaceholderText("User ID");
    fireEvent.change(box, { target: { value: "1203" } });
    fireEvent.keyDown(box, { key: "Enter" });

    await waitFor(() =>
      expect(router.state.location.search).toContain("id=1203"),
    );
    expect(router.state.location.search).not.toContain("user_id=1203");
    await waitFor(() =>
      expect(api.getAccounts).toHaveBeenLastCalledWith(
        expect.objectContaining({ userId: "1203" }),
      ),
    );
  });

  it("deep-links ?id= back into the box and the query", async () => {
    renderPage("?id=1203");

    await waitFor(() =>
      expect(api.getAccounts).toHaveBeenCalledWith(
        expect.objectContaining({ userId: "1203" }),
      ),
    );
    expect(screen.getByPlaceholderText("User ID")).toHaveValue("1203");
  });

  it("shows the pending banner with the caller's own count", async () => {
    api.getPendingBlockRequests.mockResolvedValue({
      data: [request({ id: 1 }), request({ id: 2, targetUserId: 1300 })],
    });
    renderPage();
    expect(
      await screen.findByText("2 block requests awaiting your decision"),
    ).toBeInTheDocument();
  });

  it("says nothing about block requests when none are waiting on the caller", async () => {
    renderPage();
    await screen.findByText("sam@example.com");
    expect(
      screen.queryByText(/awaiting your decision/),
    ).not.toBeInTheDocument();
  });

  it("Show them narrows the list to the people the caller has to decide on", async () => {
    api.getPendingBlockRequests.mockResolvedValue({
      data: [request({ id: 1, targetUserId: 1203 })],
    });
    renderPage();
    fireEvent.click(await screen.findByRole("button", { name: "Show them" }));

    await waitFor(() =>
      expect(api.getAccounts).toHaveBeenLastCalledWith(
        expect.objectContaining({ userId: 1203 }),
      ),
    );
    expect(
      await screen.findByRole("button", { name: "Show all accounts" }),
    ).toBeInTheDocument();
  });

  it("keeps the list up when the pending-request read fails", async () => {
    api.getPendingBlockRequests.mockRejectedValue(new Error("nope"));
    renderPage();
    expect(await screen.findByText("sam@example.com")).toBeInTheDocument();
  });

  it("reports a failed list read instead of showing a silent empty table", async () => {
    api.getAccounts.mockRejectedValue({
      response: { data: { message: "Boom" } },
    });
    renderPage();
    await waitFor(() => expect(toast.error).toHaveBeenCalledWith("Boom"));
  });
});
