import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import MatchingResultDialog from "@/pages/PersonalDashboard/components/MatchingResultDialog";
import { MatchStatus } from "@/constants/matchStatus";

describe("MatchingResultDialog", () => {
  const defaultProps = {
    roundName: "2026 Spring Round",
    canViewMatch: false,
    matchData: null,
  };

  it("should disable the button when not in announcement period and no match data exists", () => {
    render(<MatchingResultDialog {...defaultProps} />);
    const button = screen.getByRole("button", {
      name: /view matching result/i,
    });
    expect(button).toBeDisabled();
  });

  it("should enable the button when status is MATCHED even if not in announcement period", () => {
    const matchedProps = {
      ...defaultProps,
      canViewMatch: false,
      matchData: { currentStatus: MatchStatus.MATCHED, partners: [] },
    };
    render(<MatchingResultDialog {...matchedProps} />);
    const button = screen.getByRole("button", {
      name: /view matching result/i,
    });
    expect(button).not.toBeDisabled();
  });

  it("should enable the button during the announcement period regardless of status", () => {
    const announcementProps = {
      ...defaultProps,
      canViewMatch: true,
      matchData: { currentStatus: MatchStatus.UNMATCHED },
    };
    render(<MatchingResultDialog {...announcementProps} />);
    const button = screen.getByRole("button", {
      name: /view matching result/i,
    });
    expect(button).not.toBeDisabled();
  });

  it("should correctly render partner information when matching succeeds", async () => {
    const mockMatchData = {
      currentStatus: MatchStatus.MATCHED,
      partners: [
        {
          id: "p1",
          firstName: "John",
          lastName: "Doe",
          primaryEmail: "john@example.com",
          participantRole: "mentor",
          recommendationReason: "Similar tech stack",
          isActive: true,
        },
      ],
    };

    render(
      <MatchingResultDialog {...defaultProps} matchData={mockMatchData} />,
    );

    // Open the dialog
    const button = screen.getByRole("button", {
      name: /view matching result/i,
    });
    fireEvent.click(button);

    // Verify title and content
    expect(screen.getByText("Congratulations!")).toBeInTheDocument();
    expect(screen.getByText("John Doe")).toBeInTheDocument();
    expect(screen.getByText("john@example.com")).toBeInTheDocument();
    expect(screen.getByText("mentor")).toBeInTheDocument();
    expect(screen.getByText(/Similar tech stack/i)).toBeInTheDocument();
  });

  const endedPartner = {
    id: "p2",
    firstName: "Jane",
    lastName: "Roe",
    primaryEmail: null,
    participantRole: "mentor",
    isActive: false,
  };

  it("should say the pairing ended when the only pairing has ended", async () => {
    // The user was matched and their partner has since left the round.
    // Congratulating them over an empty list is what the round-scoped
    // filter used to produce.
    render(
      <MatchingResultDialog
        {...defaultProps}
        matchData={{
          currentStatus: MatchStatus.MATCHED,
          partners: [endedPartner],
        }}
      />,
    );
    fireEvent.click(
      screen.getByRole("button", { name: /view matching result/i }),
    );

    expect(screen.getByText("Pairing Ended")).toBeInTheDocument();
    expect(screen.queryByText("Congratulations!")).not.toBeInTheDocument();
    expect(screen.getByText("Jane Roe")).toBeInTheDocument();
    expect(screen.getByText("This pairing has ended.")).toBeInTheDocument();
    expect(
      screen.queryByText("No matching details available."),
    ).not.toBeInTheDocument();
  });

  it("should keep the congratulations copy while a live pairing remains", async () => {
    // Changing mentor mid-round leaves both pairings in the result. One of
    // them is current, so the round's own copy still holds.
    render(
      <MatchingResultDialog
        {...defaultProps}
        matchData={{
          currentStatus: MatchStatus.MATCHED,
          partners: [
            endedPartner,
            {
              id: "p3",
              firstName: "John",
              lastName: "Doe",
              primaryEmail: "john@example.com",
              participantRole: "mentor",
              isActive: true,
            },
          ],
        }}
      />,
    );
    fireEvent.click(
      screen.getByRole("button", { name: /view matching result/i }),
    );

    expect(screen.getByText("Congratulations!")).toBeInTheDocument();
    expect(screen.getByText("This pairing has ended.")).toBeInTheDocument();
    expect(screen.getByText("john@example.com")).toBeInTheDocument();
  });

  it("should display placeholder content when no partner information is available", () => {
    const unmatchedProps = {
      ...defaultProps,
      canViewMatch: true,
      matchData: { currentStatus: MatchStatus.UNMATCHED, partners: [] },
    };

    render(<MatchingResultDialog {...unmatchedProps} />);
    fireEvent.click(
      screen.getByRole("button", { name: /view matching result/i }),
    );

    expect(screen.getByText("No Match Found")).toBeInTheDocument();
    expect(
      screen.getByText("No matching details available."),
    ).toBeInTheDocument();
  });

  it("should fall back to the UNKNOWN configuration when status is invalid", () => {
    render(
      <MatchingResultDialog
        {...defaultProps}
        canViewMatch={true}
        matchData={{ currentStatus: "SOME_INVALID_STATUS" }}
      />,
    );
    fireEvent.click(
      screen.getByRole("button", { name: /view matching result/i }),
    );

    expect(screen.getByText("Status Unknown")).toBeInTheDocument();
  });

  it("should gracefully display the UNKNOWN state when matchData is null", () => {
    render(
      <MatchingResultDialog
        {...defaultProps}
        canViewMatch={true}
        matchData={null}
      />,
    );

    const button = screen.getByRole("button", {
      name: /view matching result/i,
    });
    fireEvent.click(button);

    // Verify fallback to UNKNOWN status configuration
    expect(screen.getByText("Status Unknown")).toBeInTheDocument();
    expect(
      screen.getByText(/We're having trouble determining your match status/i),
    ).toBeInTheDocument();

    // Verify placeholder content in the list section
    expect(
      screen.getByText("No matching details available."),
    ).toBeInTheDocument();
  });
});
