import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import AdminPermissions from "@/pages/AdminPermissions";
import { useAuth } from "@/context/auth";
import * as api from "@/api/adminPermissionsApi";

vi.mock("@/context/auth", () => ({ useAuth: vi.fn() }));
vi.mock("@/api/adminPermissionsApi");

beforeEach(() => {
  vi.clearAllMocks();
  useAuth.mockReturnValue({
    user: { userId: 99 },
    isSuperAdmin: false,
    permissions: ["permission.manage"],
  });
  api.getPermissionCatalog.mockResolvedValue({
    data: { permissions: ["permission.manage", "mentorship.round.read"] },
  });
  api.getUsers.mockResolvedValue({
    data: {
      users: [
        {
          userId: 1,
          primaryEmail: "a@x.com",
          firstName: "A",
          lastName: "One",
          preferredName: null,
          userType: "internal",
          isActive: true,
          isSuperAdmin: false,
        },
      ],
      total: 1,
    },
  });
  api.getAuditLog.mockResolvedValue({ data: { entries: [], total: 0 } });
});

describe("AdminPermissions page", () => {
  it("renders the three tab triggers and loads the catalog", async () => {
    render(<AdminPermissions />);
    await waitFor(() => expect(api.getPermissionCatalog).toHaveBeenCalled());
    expect(screen.getByRole("tab", { name: "Users" })).toBeInTheDocument();
    expect(
      screen.getByRole("tab", { name: "Permission Holders" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Audit Log" })).toBeInTheDocument();
  });
});
