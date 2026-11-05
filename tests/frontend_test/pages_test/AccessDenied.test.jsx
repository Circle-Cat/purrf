import { describe, test, expect } from "vitest";
import { render, screen } from "@testing-library/react";

import AccessDenied from "@/pages/AccessDenied";

describe("AccessDenied Page", () => {
  test("always renders the 403 heading", () => {
    render(<AccessDenied />);

    expect(screen.getByText("403 Forbidden")).toBeInTheDocument();
  });

  test("renders the supplied denial message", () => {
    const message =
      "Your account has been deactivated. Contact an administrator to restore access.";
    render(<AccessDenied message={message} />);

    expect(screen.getByText(message)).toBeInTheDocument();
    expect(
      screen.queryByText("You do not have permission to access this site."),
    ).not.toBeInTheDocument();
  });

  test("falls back to the generic text when no message is passed", () => {
    render(<AccessDenied />);

    expect(
      screen.getByText("You do not have permission to access this site."),
    ).toBeInTheDocument();
  });

  test("falls back to the generic text when the message is an empty string", () => {
    render(<AccessDenied message="" />);

    expect(
      screen.getByText("You do not have permission to access this site."),
    ).toBeInTheDocument();
  });
});
