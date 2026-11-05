import { describe, it, expect } from "vitest";
import { render, screen, within } from "@testing-library/react";
import AwaitingDecisionCard from "@/components/approval/AwaitingDecisionCard";

describe("AwaitingDecisionCard", () => {
  it("shows the title, who asked and when, the reason and the actions", () => {
    render(
      <AwaitingDecisionCard
        title="Red flag awaiting your decision"
        meta={[
          "Raised by Dana Wu on 2026-10-09 01:00",
          null,
          "About the pair with Cy Lee",
        ]}
        reason="Rude in the kickoff call"
      >
        <button type="button">Approve</button>
      </AwaitingDecisionCard>,
    );

    const card = screen.getByRole("region", {
      name: "Red flag awaiting your decision",
    });
    expect(
      within(card).getByRole("heading", {
        name: "Red flag awaiting your decision",
      }),
    ).toBeInTheDocument();
    expect(
      within(card).getByText("Raised by Dana Wu on 2026-10-09 01:00"),
    ).toBeInTheDocument();
    expect(
      within(card).getByText("About the pair with Cy Lee"),
    ).toBeInTheDocument();
    expect(
      within(card).getByText("Rude in the kickoff call"),
    ).toBeInTheDocument();
    expect(
      within(card).getByRole("button", { name: "Approve" }),
    ).toBeInTheDocument();
  });

  it("says when no reason was given, in the caller's words when it has some", () => {
    const { rerender } = render(<AwaitingDecisionCard title="T" meta={[]} />);
    expect(screen.getByText("No reason given.")).toBeInTheDocument();

    rerender(
      <AwaitingDecisionCard title="T" meta={[]} emptyReason="No note given." />,
    );
    expect(screen.getByText("No note given.")).toBeInTheDocument();
  });
});
