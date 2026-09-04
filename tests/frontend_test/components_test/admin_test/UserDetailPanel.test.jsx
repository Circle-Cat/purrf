import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import UserDetailPanel from "@/pages/AdminPermissions/components/UserDetailPanel";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { useAuth } from "@/context/auth";
import * as api from "@/api/adminPermissionsApi";

vi.mock("@/context/auth", () => ({ useAuth: vi.fn() }));
vi.mock("@/api/adminPermissionsApi");

const catalog = [
  { name: "mentorship.admin.read", description: "d1" },
  { name: "permission.manage", description: "d2" },
];

const selectedUser = {
  userId: 1,
  primaryEmail: "a@x.com",
  firstName: "A",
  lastName: "One",
  preferredName: null,
  userType: "internal",
  isActive: true,
  isSuperAdmin: false,
};

/** Build `count` distinct history rows so the table is longer than the box. */
const makeHistory = (count) =>
  Array.from({ length: count }, (_, i) => ({
    permissionName: "mentorship.admin.read",
    isActive: true,
    grantedSource: "manual",
    // granted_by is an int on the wire, not a string. The panel renders it
    // through the shared actor label, which names the person when the payload
    // resolves one and otherwise keeps the id visible.
    grantedBy: i,
    grantedTimestamp: "2026-07-28T00:00:00Z",
    revokedBy: null,
    revokedTimestamp: null,
  }));

// The panel renders a DialogHeader, which needs a Dialog ancestor for context.
// Mirror how UsersTab mounts it so the test exercises the real nesting.
const renderPanel = () =>
  render(
    <Dialog open>
      <DialogContent className="sm:max-w-2xl overflow-y-auto max-h-[90vh]">
        <UserDetailPanel
          selectedUser={selectedUser}
          catalog={catalog}
          onMakeSuperAdmin={vi.fn()}
          onRevokeSuperAdmin={vi.fn()}
        />
      </DialogContent>
    </Dialog>,
  );

describe("UserDetailPanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useAuth.mockReturnValue({
      user: { userId: 99 },
      isSuperAdmin: true,
      permissions: ["permission.manage"],
    });
  });

  it("keeps a long history inside its own scroll box so the dialog does not grow", async () => {
    api.getUserPermissions.mockResolvedValue({
      data: { userId: 1, active: [], history: makeHistory(40) },
    });
    renderPanel();

    const box = await screen.findByTestId("history-scroll");
    // A height cap plus its own overflow is what stops the history from
    // pushing the dialog past its max height and scrolling the title and the
    // close button out of view.
    expect(box).toHaveClass("max-h-64");
    expect(box).toHaveClass("overflow-y-auto");
    // The rows still render in full - they are reachable by scrolling the box,
    // not truncated away.
    expect(await screen.findByText("User 39")).toBeInTheDocument();
  });

  it("wraps the history in the scroll box even when there is none", async () => {
    api.getUserPermissions.mockResolvedValue({
      data: { userId: 1, active: [], history: [] },
    });
    renderPanel();

    await waitFor(() =>
      expect(screen.getByText("No history")).toBeInTheDocument(),
    );
    expect(screen.getByTestId("history-scroll")).toContainElement(
      screen.getByText("No history"),
    );
  });
});
