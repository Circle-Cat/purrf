import { render, screen, cleanup, waitFor } from "@testing-library/react";
import { describe, test, expect, afterEach, vi } from "vitest";
import Header from "@/components/layout/Header";
import Profile from "@/pages/Profile";
import { getCookie, extractCloudflareUserName } from "@/utils/auth";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import userEvent from "@testing-library/user-event";

import "@testing-library/jest-dom/vitest";

vi.mock("@/utils/auth", () => ({
  getCookie: vi.fn(),
  extractCloudflareUserName: vi.fn(),
}));

vi.mock("@/pages/Profile", () => ({
  default: () => <div data-testid="profile-page">Mocked Profile Page</div>,
}));

describe("Header Component", () => {
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

    const userNameElement = screen.getByText("", { selector: ".user-name" });
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
    expect(spanElement.closest("button")).toHaveClass("user-name");
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
    expect(spanElement.closest("button")).toHaveClass("user-name");
  });

  test("displays an empty user initial if the extracted name is null or empty", () => {
    getCookie.mockReturnValue("some-jwt-cookie-string");
    extractCloudflareUserName.mockReturnValue("");
    const { rerender } = render(
      <MemoryRouter>
        <Header />
      </MemoryRouter>,
    );

    let userNameElement = screen.getByText("", { selector: ".user-name" });
    expect(userNameElement.textContent).toBe("");

    extractCloudflareUserName.mockReturnValue(null);
    rerender(
      <MemoryRouter>
        <Header />
      </MemoryRouter>,
    );
    userNameElement = screen.getByText("", { selector: ".user-name" });
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
});
