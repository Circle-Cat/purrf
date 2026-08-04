import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, act } from "@testing-library/react";
import PermissionHoldersTab from "@/pages/AdminPermissions/components/PermissionHoldersTab";
import * as api from "@/api/adminPermissionsApi";

vi.mock("@/api/adminPermissionsApi");

const catalog = [
  { name: "permission.manage", description: "d1" },
  { name: "mentorship.admin.read", description: "d2" },
];

beforeEach(() => {
  vi.clearAllMocks();
  api.getPermissionHolders.mockResolvedValue({
    data: {
      grants: [
        {
          id: 1,
          userId: 5,
          permissionName: "permission.manage",
          grantedSource: "manual",
          grantedBy: 9,
          grantedTimestamp: "2026-06-01T00:00:00Z",
          revokedTimestamp: null,
          isActive: true,
        },
      ],
    },
  });
});

describe("PermissionHoldersTab", () => {
  it("prompts to pick a permission and fetches nothing initially", async () => {
    render(<PermissionHoldersTab catalog={catalog} />);
    await act(async () => {});
    expect(api.getPermissionHolders).not.toHaveBeenCalled();
    expect(screen.getByText(/choose a permission/i)).toBeInTheDocument();
  });
});
