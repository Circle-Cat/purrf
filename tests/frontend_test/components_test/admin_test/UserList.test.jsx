import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import UserList from "@/pages/AdminPermissions/components/UserList";

const users = [
  {
    userId: 1,
    primaryEmail: "a@x.com",
    firstName: "Alice",
    lastName: "One",
    preferredName: "Al",
    userType: "internal",
    isActive: true,
    isSuperAdmin: false,
  },
  {
    userId: 2,
    primaryEmail: "b@x.com",
    firstName: "Bob",
    lastName: "Two",
    preferredName: null,
    userType: "external",
    isActive: false,
    isSuperAdmin: true,
  },
];

const baseProps = {
  users,
  total: 2,
  loading: false,
  hasSearched: true,
  search: "",
  onSearchChange: vi.fn(),
  userId: "",
  onUserIdChange: vi.fn(),
  onSearch: vi.fn(),
  offset: 0,
  limit: 20,
  onPrev: vi.fn(),
  onNext: vi.fn(),
  onSelect: vi.fn(),
  sortBy: null,
  order: "asc",
  onToggleSort: vi.fn(),
  isSuperAdmin: false,
  onSuperAdminFilterChange: vi.fn(),
  userType: "",
  onUserTypeChange: vi.fn(),
};

describe("UserList", () => {
  beforeEach(() => vi.clearAllMocks());

  it("renders userId, firstName, lastName, preferredName, userType columns", () => {
    render(<UserList {...baseProps} />);
    expect(screen.getByText("1")).toBeInTheDocument();
    expect(screen.getByText("Alice")).toBeInTheDocument();
    expect(screen.getByText("One")).toBeInTheDocument();
    expect(screen.getByText("Al")).toBeInTheDocument();
    expect(screen.getByText("Internal")).toBeInTheDocument();
  });

  it("shows '—' for null preferredName and 'External' for external userType", () => {
    render(<UserList {...baseProps} />);
    // Bob has null preferredName -> shows em dash, External type
    expect(screen.getByText("External")).toBeInTheDocument();
  });

  it("shows 'Active' badge and 'Deactivated' badge for status", () => {
    render(<UserList {...baseProps} />);
    expect(screen.getByText("Active")).toBeInTheDocument();
    expect(screen.getByText("Deactivated")).toBeInTheDocument();
  });

  it("shows Super-admin badge for isSuperAdmin users", () => {
    render(<UserList {...baseProps} />);
    // The column header and the badge both contain "Super-admin"; assert the badge specifically
    const badges = screen.getAllByText("Super-admin");
    // At least one element should be a badge span (data-slot="badge")
    expect(badges.some((el) => el.closest("[data-slot='badge']"))).toBe(true);
  });

  it("renders 'Manage permissions' icon button per user and fires onSelect with the user object", () => {
    render(<UserList {...baseProps} />);
    const buttons = screen.getAllByRole("button", {
      name: /manage permissions/i,
    });
    expect(buttons).toHaveLength(2);
    fireEvent.click(buttons[0]);
    expect(baseProps.onSelect).toHaveBeenCalledWith(users[0]);
  });

  it("fires onSearchChange when typing", () => {
    render(<UserList {...baseProps} />);
    fireEvent.change(screen.getByPlaceholderText(/search by name/i), {
      target: { value: "jo" },
    });
    expect(baseProps.onSearchChange).toHaveBeenCalledWith("jo");
  });

  it("disables Prev on the first page and enables Next when more remain", () => {
    render(<UserList {...baseProps} total={50} />);
    expect(screen.getByRole("button", { name: /prev/i })).toBeDisabled();
    expect(screen.getByRole("button", { name: /next/i })).toBeEnabled();
  });

  it("clicking a sortable column header calls onToggleSort with the backend field", () => {
    render(<UserList {...baseProps} />);
    // "Last Name" header maps to backend field "last_name"
    fireEvent.click(screen.getByText("Last Name"));
    expect(baseProps.onToggleSort).toHaveBeenCalledWith("last_name");
  });

  it("clicking 'First Name' header calls onToggleSort with 'first_name'", () => {
    render(<UserList {...baseProps} />);
    fireEvent.click(screen.getByText("First Name"));
    expect(baseProps.onToggleSort).toHaveBeenCalledWith("first_name");
  });

  it("clicking 'User Type' header calls onToggleSort with 'user_type'", () => {
    render(<UserList {...baseProps} />);
    fireEvent.click(screen.getByText("User Type"));
    expect(baseProps.onToggleSort).toHaveBeenCalledWith("user_type");
  });

  it("super-admin checkbox fires onSuperAdminFilterChange when clicked", () => {
    render(<UserList {...baseProps} />);
    const checkbox = screen.getByRole("checkbox", {
      name: /super-admins only/i,
    });
    fireEvent.click(checkbox);
    expect(baseProps.onSuperAdminFilterChange).toHaveBeenCalled();
  });

  it("shows the empty prompt and hides the table before a search has run", () => {
    render(<UserList {...baseProps} hasSearched={false} />);
    expect(
      screen.getByText("Enter search criteria and click Search."),
    ).toBeInTheDocument();
    // No table rows rendered yet.
    expect(screen.queryByText("Alice")).not.toBeInTheDocument();
  });

  it("strips non-digits before calling onUserIdChange", () => {
    render(<UserList {...baseProps} />);
    fireEvent.change(screen.getByPlaceholderText("User ID"), {
      target: { value: "a1b2" },
    });
    expect(baseProps.onUserIdChange).toHaveBeenCalledWith("12");
  });

  it("calls onSearch when the Search button is clicked", async () => {
    const user = userEvent.setup();
    render(<UserList {...baseProps} />);
    await user.click(screen.getByRole("button", { name: "Search" }));
    expect(baseProps.onSearch).toHaveBeenCalledTimes(1);
  });
});
