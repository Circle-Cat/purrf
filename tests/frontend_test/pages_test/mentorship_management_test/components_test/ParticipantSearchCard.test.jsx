import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import ParticipantSearchCard from "@/pages/MentorshipManagement/components/ParticipantSearchCard";
import { getAllMentorshipRounds } from "@/api/mentorshipApi";

vi.mock("@/api/mentorshipApi", () => ({
  getAllMentorshipRounds: vi.fn(),
}));

vi.mock("@/pages/MentorshipManagement/components/ParticipantSearchTab", () => ({
  default: vi.fn(({ participationStatus, rounds }) => (
    <div data-testid="mock-participant-search-tab">
      <span data-testid="participation-status">{participationStatus}</span>
      <span data-testid="rounds-count">{rounds?.length ?? 0}</span>
    </div>
  )),
}));

const TEST_ROUNDS = [{ id: 1, name: "Spring 2026" }];

describe("ParticipantSearchCard", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getAllMentorshipRounds.mockResolvedValue({ data: TEST_ROUNDS });
  });

  it("renders both tab triggers, defaulting to Participants", () => {
    render(<ParticipantSearchCard />);
    expect(
      screen.getByRole("tab", { name: "Participants" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("tab", { name: "Non-participants" }),
    ).toBeInTheDocument();
    expect(screen.getByTestId("participation-status").textContent).toBe(
      "participant",
    );
  });

  it("switches to the Non-participants tab on click", async () => {
    render(<ParticipantSearchCard />);
    await userEvent.click(
      screen.getByRole("tab", { name: "Non-participants" }),
    );
    expect(screen.getByTestId("participation-status").textContent).toBe(
      "non_participant",
    );
  });

  it("passes the fetched rounds to the Participants tab", async () => {
    render(<ParticipantSearchCard />);
    await waitFor(() =>
      expect(screen.getByTestId("rounds-count").textContent).toBe(
        String(TEST_ROUNDS.length),
      ),
    );
  });
});
