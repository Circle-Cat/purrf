import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import PermissionHoldersTab from "@/pages/AdminPermissions/components/PermissionHoldersTab";
import { usePermissionHolders } from "@/pages/AdminPermissions/hooks/usePermissionHolders";

// Hook-mocked so we can render committed-search states without driving the
// radix Select (which is unreliable in jsdom).
vi.mock("@/pages/AdminPermissions/hooks/usePermissionHolders", () => ({
  usePermissionHolders: vi.fn(),
}));

const base = {
  permissionName: "",
  setPermissionName: vi.fn(),
  includeRevoked: false,
  setIncludeRevoked: vi.fn(),
  submitSearch: vi.fn(),
  hasSearched: false,
  grants: [],
  loading: false,
};

beforeEach(() => vi.clearAllMocks());

describe("PermissionHoldersTab render", () => {
  it("disables Search until a permission is chosen", () => {
    usePermissionHolders.mockReturnValue({ ...base });
    render(<PermissionHoldersTab catalog={["permission.manage"]} />);
    expect(screen.getByRole("button", { name: "Search" })).toBeDisabled();
  });

  it("renders a 'User ID' column (not 'User') once a search has run", () => {
    usePermissionHolders.mockReturnValue({
      ...base,
      permissionName: "permission.manage",
      hasSearched: true,
      grants: [
        {
          userId: 7,
          grantedSource: "manual",
          grantedBy: 1,
          grantedTimestamp: "2026-01-01T00:00:00Z",
          isActive: true,
        },
      ],
    });
    render(<PermissionHoldersTab catalog={["permission.manage"]} />);
    expect(screen.getByText("User ID")).toBeInTheDocument();
    expect(screen.getByText("7")).toBeInTheDocument();
  });

  it("badges a super-admin-derived holder", () => {
    usePermissionHolders.mockReturnValue({
      ...base,
      permissionName: "permission.manage",
      hasSearched: true,
      grants: [
        {
          userId: 7,
          grantedSource: "super_admin",
          grantedBy: null,
          grantedTimestamp: null,
          isActive: true,
          isSuperAdmin: true,
        },
      ],
    });
    render(<PermissionHoldersTab catalog={["permission.manage"]} />);
    expect(screen.getByText("super admin")).toBeInTheDocument();
  });

  it("does not badge a normal holder", () => {
    usePermissionHolders.mockReturnValue({
      ...base,
      permissionName: "permission.manage",
      hasSearched: true,
      grants: [
        {
          userId: 7,
          grantedSource: "admin",
          grantedBy: 1,
          grantedTimestamp: "2026-01-01T00:00:00Z",
          isActive: true,
          isSuperAdmin: false,
        },
      ],
    });
    render(<PermissionHoldersTab catalog={["permission.manage"]} />);
    expect(screen.queryByText("super admin")).not.toBeInTheDocument();
  });

  it("calls submitSearch when Search is clicked", async () => {
    const submitSearch = vi.fn();
    usePermissionHolders.mockReturnValue({
      ...base,
      permissionName: "permission.manage",
      submitSearch,
    });
    const user = userEvent.setup();
    render(<PermissionHoldersTab catalog={["permission.manage"]} />);
    await user.click(screen.getByRole("button", { name: "Search" }));
    expect(submitSearch).toHaveBeenCalledTimes(1);
  });
});
