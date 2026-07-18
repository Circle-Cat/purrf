import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
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
    data: {
      permissions: [
        { name: "permission.manage", description: "d1" },
        { name: "mentorship.admin.read", description: "d2" },
      ],
    },
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

  it("does not fetch users on mount; the Users tab waits for Search", async () => {
    render(<AdminPermissions />);
    await waitFor(() => expect(api.getPermissionCatalog).toHaveBeenCalled());

    expect(api.getUsers).not.toHaveBeenCalled();
    expect(
      screen.getByText("Enter search criteria and click Search."),
    ).toBeInTheDocument();
  });

  it("searches by exact User ID and sends the user_id param on Search", async () => {
    const user = userEvent.setup();
    render(<AdminPermissions />);
    await waitFor(() => expect(api.getPermissionCatalog).toHaveBeenCalled());

    await user.type(screen.getByPlaceholderText("User ID"), "42");
    await user.click(screen.getByRole("button", { name: "Search" }));

    await waitFor(() => expect(api.getUsers).toHaveBeenCalledTimes(1));
    expect(api.getUsers).toHaveBeenCalledWith(
      expect.objectContaining({ userId: "42" }),
    );
    // The mocked result row renders once the search completes.
    expect(await screen.findByText("One")).toBeInTheDocument();
  });

  it("strips non-digits from the User ID field", async () => {
    const user = userEvent.setup();
    render(<AdminPermissions />);
    await waitFor(() => expect(api.getPermissionCatalog).toHaveBeenCalled());

    const idInput = screen.getByPlaceholderText("User ID");
    await user.type(idInput, "a1b2c3");
    expect(idInput).toHaveValue("123");
  });

  it("renders the Understand permissions panel trigger", async () => {
    render(<AdminPermissions />);
    await waitFor(() => expect(api.getPermissionCatalog).toHaveBeenCalled());
    expect(
      screen.getByRole("button", { name: "Understand permissions" }),
    ).toBeInTheDocument();
  });
});
