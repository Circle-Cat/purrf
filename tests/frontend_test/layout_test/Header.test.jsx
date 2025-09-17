import { render, screen, cleanup } from "@testing-library/react";
import { describe, test, expect, afterEach, vi } from "vitest";
import Header from "@/components/layout/Header";
import { getCookie, extractCloudflareUserName } from "@/utils/auth";

import "@testing-library/jest-dom/vitest";

vi.mock("@/utils/auth", () => ({
  getCookie: vi.fn(),
  extractCloudflareUserName: vi.fn(),
}));

describe("Header Component", () => {
  afterEach(() => {
    cleanup();
    vi.resetAllMocks();
  });

  test("renders the logo and title correctly", () => {
    render(<Header />);
    expect(screen.getByAltText("Purrf Logo")).toBeInTheDocument();
    expect(screen.getByText("Purrf")).toBeInTheDocument();
  });

  test("displays an empty user initial when no cookie is found", () => {
    getCookie.mockReturnValue(null);
    render(<Header />);

    const userNameElement = screen.getByText("", { selector: ".user-name" });
    expect(userNameElement).toBeInTheDocument();
    expect(userNameElement.textContent).toBe("");
    expect(extractCloudflareUserName).not.toHaveBeenCalled();
  });

  test("displays the correct user initial when a valid cookie and name are found", () => {
    getCookie.mockReturnValue("some-jwt-cookie-string");
    extractCloudflareUserName.mockReturnValue("Alice");
    render(<Header />);

    expect(screen.getByText("A")).toBeInTheDocument();
    expect(screen.getByText("A")).toHaveClass("user-name");
  });

  test("handles lowercase names and correctly uppercases the initial", () => {
    getCookie.mockReturnValue("some-jwt-cookie-string");
    extractCloudflareUserName.mockReturnValue("mei");
    render(<Header />);

    expect(screen.getByText("M")).toBeInTheDocument();
    expect(screen.getByText("M")).toHaveClass("user-name");
  });

  test("displays an empty user initial if the extracted name is null or empty", () => {
    getCookie.mockReturnValue("some-jwt-cookie-string");
    extractCloudflareUserName.mockReturnValue("");
    const { rerender } = render(<Header />);

    let userNameElement = screen.getByText("", { selector: ".user-name" });
    expect(userNameElement.textContent).toBe("");

    extractCloudflareUserName.mockReturnValue(null);
    rerender(<Header />);
    userNameElement = screen.getByText("", { selector: ".user-name" });
    expect(userNameElement.textContent).toBe("");
  });
});
