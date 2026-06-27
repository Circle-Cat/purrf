import { render, screen, cleanup, waitFor } from "@testing-library/react";
import { describe, test, expect, afterEach, vi } from "vitest";
import Header from "@/components/layout/Header";
import Profile from "@/pages/Profile";
import {
  getCookie,
  extractCloudflareUserName,
  performGlobalLogout,
} from "@/utils/auth";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { ROUTE_PATHS } from "@/constants/RoutePaths";
import userEvent from "@testing-library/user-event";

import "@testing-library/jest-dom/vitest";

vi.mock("@/utils/auth", () => ({
  getCookie: vi.fn(),
  extractCloudflareUserName: vi.fn(),
  performGlobalLogout: vi.fn(),
}));

vi.mock("@/pages/Profile", () => ({
  default: () => <div data-testid="profile-page">Mocked Profile Page</div>,
}));

describe("Header Component", () => {
  const setup = (cookieValue = null, userName = "") => {
    getCookie.mockReturnValue(cookieValue);
    extractCloudflareUserName.mockReturnValue(userName);

    render(
      <MemoryRouter>
        <Header />
      </MemoryRouter>,
    );
  };

  afterEach(() => {
    cleanup();
    vi.resetAllMocks();
  });

  test("renders the logo and title correctly", () => {
    render(
      <MemoryRouter>
        <Header />
      </MemoryRouter>,
    );
    expect(screen.getByAltText("Purrf Logo")).toBeInTheDocument();
    expect(screen.getByText("Purrf")).toBeInTheDocument();
  });

  test("displays an empty user initial when no cookie is found", () => {
    getCookie.mockReturnValue(null);
    render(
      <MemoryRouter>
        <Header />
      </MemoryRouter>,
    );

    const userNameElement = screen.getByRole("button", { name: "User menu" });
    expect(userNameElement).toBeInTheDocument();
    expect(userNameElement.textContent).toBe("");
    expect(extractCloudflareUserName).not.toHaveBeenCalled();
  });

  test("displays the correct user initial when a valid cookie and name are found", () => {
    getCookie.mockReturnValue("some-jwt-cookie-string");
    extractCloudflareUserName.mockReturnValue("Alice");
    render(
      <MemoryRouter>
        <Header />
      </MemoryRouter>,
    );

    const spanElement = screen.getByText("A");
    expect(spanElement).toBeInTheDocument();
    expect(spanElement.closest("button")).toHaveAttribute(
      "aria-label",
      "User menu",
    );
  });

  test("handles lowercase names and correctly uppercases the initial", () => {
    getCookie.mockReturnValue("some-jwt-cookie-string");
    extractCloudflareUserName.mockReturnValue("mei");
    render(
      <MemoryRouter>
        <Header />
      </MemoryRouter>,
    );

    const spanElement = screen.getByText("M");
    expect(spanElement).toBeInTheDocument();
    expect(spanElement.closest("button")).toHaveAttribute(
      "aria-label",
      "User menu",
    );
  });

  test("displays an empty user initial if the extracted name is null or empty", () => {
    getCookie.mockReturnValue("some-jwt-cookie-string");
    extractCloudflareUserName.mockReturnValue("");
    const { rerender } = render(
      <MemoryRouter>
        <Header />
      </MemoryRouter>,
    );

    let userNameElement = screen.getByRole("button", { name: "User menu" });
    expect(userNameElement.textContent).toBe("");

    extractCloudflareUserName.mockReturnValue(null);
    rerender(
      <MemoryRouter>
        <Header />
      </MemoryRouter>,
    );
    userNameElement = screen.getByRole("button", { name: "User menu" });
    expect(userNameElement.textContent).toBe("");
  });

  test('should go to the profile when "View Profile" is clicked', async () => {
    const user = userEvent.setup();
    const mockUserName = "Alice";
    getCookie.mockReturnValue("some-jwt-cookie-string");
    extractCloudflareUserName.mockReturnValue(mockUserName);

    render(
      <MemoryRouter initialEntries={["/"]}>
        <Routes>
          <Route path="/" element={<Header />} />
          <Route path="/profile" element={<Profile />} />
        </Routes>
      </MemoryRouter>,
    );

    const userChar = await screen.findByText(
      mockUserName.charAt(0).toUpperCase(),
    );
    const userButton = userChar.closest("button");
    await user.click(userButton);
    const viewProfileItem = await screen.findByRole("menuitem", {
      name: "View Profile",
    });

    await user.click(viewProfileItem);
    await waitFor(() => {
      expect(screen.getByText("Mocked Profile Page")).toBeInTheDocument();
    });
  });

  test('should go to the sign in & security settings when "Settings" is clicked', async () => {
    const user = userEvent.setup();
    const mockUserName = "Alice";
    getCookie.mockReturnValue("some-jwt-cookie-string");
    extractCloudflareUserName.mockReturnValue(mockUserName);

    render(
      <MemoryRouter initialEntries={["/"]}>
        <Routes>
          <Route path="/" element={<Header />} />
          <Route
            path={ROUTE_PATHS.SIGN_IN_SECURITY}
            element={<div>Mocked Settings Page</div>}
          />
        </Routes>
      </MemoryRouter>,
    );

    const userChar = await screen.findByText(
      mockUserName.charAt(0).toUpperCase(),
    );
    await user.click(userChar.closest("button"));
    const settingsItem = await screen.findByRole("menuitem", {
      name: "Settings",
    });

    await user.click(settingsItem);
    await waitFor(() => {
      expect(screen.getByText("Mocked Settings Page")).toBeInTheDocument();
    });
  });

  test("opens modal when clicking on the avatar", async () => {
    setup("some-jwt-cookie-string", "Alice");

    const user = userEvent.setup();
    await user.click(screen.getByText("A"));
    const contactUs = await screen.findByText("Contact Us");
    await user.click(contactUs);
    expect(screen.getByRole("dialog")).toBeInTheDocument();
  });

  test("renders header and content correctly when modal is opened", async () => {
    setup("some-jwt-cookie-string", "Alice");

    const user = userEvent.setup();
    await user.click(screen.getByText("A"));
    const contactUs = await screen.findByText("Contact Us");
    await user.click(contactUs);

    const expectedTexts = [
      "Contact Administrators",
      "If you need support, please contact our admins:",
      "Admin Email:",
      "outreach-programs-comms@circlecat.org",
    ];

    expectedTexts.forEach((text) => {
      expect(screen.getByText(text)).toBeInTheDocument();
    });
  });

  test("closes modal when clicking on the close button", async () => {
    setup("some-jwt-cookie-string", "Alice");

    const user = userEvent.setup();
    await user.click(screen.getByText("A"));
    const contactUs = await screen.findByText("Contact Us");
    await user.click(contactUs);

    const closeContactUs = await screen.findByText("×");
    await user.click(closeContactUs);
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  test("should call performGlobalLogout when logout is clicked", async () => {
    setup("some-jwt", "Alice");
    const user = userEvent.setup();

    await user.click(screen.getByText("A"));

    const logoutItem = await screen.findByText("Logout");
    await user.click(logoutItem);

    expect(performGlobalLogout).toHaveBeenCalled();
  });

  test("does not render the sidebar toggle when onToggleSidebar is not provided", () => {
    render(
      <MemoryRouter>
        <Header />
      </MemoryRouter>,
    );

    expect(
      screen.queryByRole("button", { name: /sidebar/i }),
    ).not.toBeInTheDocument();
  });

  test("calls onToggleSidebar when the sidebar toggle is clicked", async () => {
    const user = userEvent.setup();
    const onToggleSidebar = vi.fn();

    render(
      <MemoryRouter>
        <Header onToggleSidebar={onToggleSidebar} sidebarCollapsed={false} />
      </MemoryRouter>,
    );

    const toggle = screen.getByRole("button", { name: "Collapse sidebar" });
    expect(toggle).toHaveAttribute("aria-expanded", "true");

    await user.click(toggle);
    expect(onToggleSidebar).toHaveBeenCalledTimes(1);
  });

  test("reflects the collapsed state in the toggle's label and aria-expanded", () => {
    render(
      <MemoryRouter>
        <Header onToggleSidebar={vi.fn()} sidebarCollapsed={true} />
      </MemoryRouter>,
    );

    const toggle = screen.getByRole("button", { name: "Expand sidebar" });
    expect(toggle).toHaveAttribute("aria-expanded", "false");
  });
});
