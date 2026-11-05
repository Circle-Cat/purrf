import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import EmptyState from "@/pages/Recruiting/components/EmptyState";

describe("EmptyState", () => {
  it("renders all three parts", () => {
    render(
      <EmptyState
        what="Interviews you've been assigned to appear here."
        how="A recruiter assigns you to an interview session from their applications board."
        who="You can't add yourself."
      />,
    );
    expect(
      screen.getByText("Interviews you've been assigned to appear here."),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        "A recruiter assigns you to an interview session from their applications board.",
      ),
    ).toBeInTheDocument();
    expect(screen.getByText("You can't add yourself.")).toBeInTheDocument();
  });

  it("renders what before how before who in document order", () => {
    const { container } = render(
      <EmptyState what="First." how="Second." who="Third." />,
    );
    expect(container.textContent).toBe("First.Second.Third.");
  });

  it("renders an optional action", () => {
    render(
      <EmptyState
        what="Nothing here."
        how="Someone adds one."
        who="Not you."
        action={<button type="button">Browse postings</button>}
      />,
    );
    expect(
      screen.getByRole("button", { name: "Browse postings" }),
    ).toBeInTheDocument();
  });

  it("renders no action when none is given", () => {
    render(<EmptyState what="A." how="B." who="C." />);
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });
});
