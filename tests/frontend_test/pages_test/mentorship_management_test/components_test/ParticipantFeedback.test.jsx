import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import ParticipantFeedback from "@/pages/MentorshipManagement/components/ParticipantFeedback";

const sent = {
  userId: 3104,
  name: "Alice Chen",
  role: "mentee",
  hasSubmitted: true,
  mostValuableAspects: "Career advice",
  challenges: "Scheduling",
  programRating: 4,
  partnerFeedback: [
    { partnerId: 22, partnerName: "Bob Smith", rating: 2, feedback: "Often late" },
    { partnerId: 3999, partnerName: null, rating: 5, feedback: null },
  ],
};

describe("ParticipantFeedback", () => {
  it("renders nothing when no feedback is owed", () => {
    const { container } = render(<ParticipantFeedback feedback={null} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("says Not sent yet when it is owed but not sent", () => {
    render(
      <ParticipantFeedback
        feedback={{ ...sent, hasSubmitted: false, partnerFeedback: [] }}
      />,
    );
    expect(screen.getByText("Not sent yet.")).toBeInTheDocument();
  });

  it("shows the answers in form order, each partner with their ID", () => {
    render(<ParticipantFeedback feedback={sent} />);
    expect(screen.getByText("Career advice")).toBeInTheDocument();
    expect(screen.getByText("Scheduling")).toBeInTheDocument();
    expect(screen.getByText("4/5")).toBeInTheDocument();
    expect(
      screen.getByText("Bob Smith (ID 22): 2/5 — “Often late”"),
    ).toBeInTheDocument();
    expect(screen.getByText(/3999.*: 5\/5$/)).toBeInTheDocument();
  });
});
