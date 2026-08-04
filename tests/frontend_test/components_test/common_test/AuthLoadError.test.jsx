import { describe, test, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";

import AuthLoadError from "@/components/common/AuthLoadError";
import { performGlobalLogout } from "@/utils/auth";

vi.mock("@/utils/auth", () => ({
  performGlobalLogout: vi.fn(),
}));

describe("AuthLoadError Component", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  test("shows the connectivity copy and a working Retry button by default", () => {
    const onRetry = vi.fn();
    render(<AuthLoadError onRetry={onRetry} />);

    expect(screen.getByText("Couldn't load your account")).toBeInTheDocument();
    expect(
      screen.getByText(
        "We couldn't reach the server to load your account. Check your connection and try again.",
      ),
    ).toBeInTheDocument();

    const retryButton = screen.getByRole("button", { name: "Retry" });
    expect(retryButton).toBeInTheDocument();
    retryButton.click();
    expect(onRetry).toHaveBeenCalledTimes(1);

    expect(
      screen.getByRole("button", { name: "Log in again" }),
    ).toBeInTheDocument();
  });

  test("shows the session-expired copy with no Retry button", () => {
    render(<AuthLoadError sessionExpired onRetry={vi.fn()} />);

    expect(screen.getByText("Your session has expired")).toBeInTheDocument();
    expect(
      screen.getByText("Please log in again to continue."),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Retry" }),
    ).not.toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Log in again" }),
    ).toBeInTheDocument();
  });

  test("shows the refusal message verbatim with no Retry button", () => {
    const message = "Sign in with a supported method.";
    render(<AuthLoadError refusalMessage={message} onRetry={vi.fn()} />);

    expect(screen.getByText("Sign-in was refused")).toBeInTheDocument();
    expect(screen.getByText(message)).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Retry" }),
    ).not.toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Log in again" }),
    ).toBeInTheDocument();
  });

  test("calls performGlobalLogout when Log in again is clicked on the refusal variant", () => {
    render(<AuthLoadError refusalMessage="Sign in with a supported method." />);

    screen.getByRole("button", { name: "Log in again" }).click();
    expect(performGlobalLogout).toHaveBeenCalledTimes(1);
  });

  test("refusalMessage takes precedence over sessionExpired copy", () => {
    const message = "Sign in with a supported method.";
    render(<AuthLoadError refusalMessage={message} sessionExpired />);

    expect(screen.getByText("Sign-in was refused")).toBeInTheDocument();
    expect(screen.getByText(message)).toBeInTheDocument();
    expect(
      screen.queryByText("Your session has expired"),
    ).not.toBeInTheDocument();
  });
});
