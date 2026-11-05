import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import PendingNotice from "@/pages/Recruiting/components/PendingNotice";

describe("PendingNotice", () => {
  it("renders the headline", () => {
    render(<PendingNotice headline="Submitted for review" />);
    expect(screen.getByText("Submitted for review")).toBeInTheDocument();
  });

  it("names who is being waited on", () => {
    render(
      <PendingNotice headline="Submitted for review" waitingOn="Alice Chen" />,
    );
    expect(screen.getByText("Waiting on Alice Chen.")).toBeInTheDocument();
  });

  it("omits the waiting sentence when nobody is named", () => {
    render(<PendingNotice headline="Submitted for review" />);
    expect(screen.queryByText(/Waiting on/)).not.toBeInTheDocument();
  });

  it("renders the detail line", () => {
    render(
      <PendingNotice
        headline="Submitted for review"
        detail="Editing is locked until they approve or reject."
      />,
    );
    expect(
      screen.getByText("Editing is locked until they approve or reject."),
    ).toBeInTheDocument();
  });
});
