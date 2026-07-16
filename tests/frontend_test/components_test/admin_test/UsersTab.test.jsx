import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import UsersTab from "@/pages/AdminPermissions/components/UsersTab";
import { useAuth } from "@/context/auth";
import * as api from "@/api/adminPermissionsApi";

vi.mock("@/context/auth", () => ({ useAuth: vi.fn() }));
vi.mock("@/api/adminPermissionsApi");

const catalog = ["mentorship.round.read", "permission.manage"];

describe("UsersTab", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useAuth.mockReturnValue({
      user: { userId: 99 },
      isSuperAdmin: true,
      permissions: ["permission.manage"],
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
    api.getUserPermissions.mockResolvedValue({
      data: { userId: 1, active: ["mentorship.round.read"], history: [] },
    });
  });

  it("lists users in the table after Search, without a dialog open initially", async () => {
    const user = userEvent.setup();
    render(<UsersTab catalog={catalog} />);
    await user.click(screen.getByRole("button", { name: "Search" }));
    await waitFor(() => expect(screen.getByText("A")).toBeInTheDocument());
    // Dialog should not be open yet
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("opens the dialog when 'Manage permissions' is clicked and loads permissions", async () => {
    const user = userEvent.setup();
    render(<UsersTab catalog={catalog} />);
    await user.click(screen.getByRole("button", { name: "Search" }));
    // Wait for user row to appear
    await waitFor(() =>
      expect(
        screen.getAllByRole("button", { name: /manage permissions/i }),
      ).toHaveLength(1),
    );
    fireEvent.click(
      screen.getByRole("button", { name: /manage permissions/i }),
    );

    // Dialog opens
    expect(screen.getByRole("dialog")).toBeInTheDocument();

    // Permissions fetch triggered
    await waitFor(() => expect(api.getUserPermissions).toHaveBeenCalledWith(1));

    // Checklist appears after permissions load
    expect(
      await screen.findByRole("checkbox", { name: "mentorship.round.read" }),
    ).toBeChecked();

    // caller is super-admin, target is not -> Make super-admin offered
    expect(
      screen.getByRole("button", { name: /make super-admin/i }),
    ).toBeInTheDocument();
  });
});
