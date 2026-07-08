import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi, beforeEach } from "vitest";
import ParticipantSearchCard from "@/pages/MentorshipManagement/components/ParticipantSearchCard";
import ParticipantSearchTab from "@/pages/MentorshipManagement/components/ParticipantSearchTab";

vi.mock("@/pages/MentorshipManagement/components/ParticipantSearchTab", () => ({
  default: vi.fn(({ participationStatus }) => (
    <div data-testid="mock-participant-search-tab">
      <span data-testid="participation-status">{participationStatus}</span>
    </div>
  )),
}));

const TEST_ROUNDS = [{ id: 1, name: "Spring 2026" }];

const renderCard = (rounds = TEST_ROUNDS) =>
  render(<ParticipantSearchCard rounds={rounds} />);

describe("ParticipantSearchCard", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders both tab triggers, defaulting to Participants", () => {
    renderCard();
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
    renderCard();
    await userEvent.click(
      screen.getByRole("tab", { name: "Non-participants" }),
    );
    expect(screen.getByTestId("participation-status").textContent).toBe(
      "non_participant",
    );
  });

  it("passes rounds to both participant search tabs", async () => {
    renderCard();

    const propsFor = (participationStatus) =>
      ParticipantSearchTab.mock.calls.find(
        ([props]) => props.participationStatus === participationStatus,
      )?.[0];

    expect(propsFor("participant")).toEqual(
      expect.objectContaining({ rounds: TEST_ROUNDS }),
    );

    await userEvent.click(
      screen.getByRole("tab", { name: "Non-participants" }),
    );
    expect(propsFor("non_participant")).toEqual(
      expect.objectContaining({ rounds: TEST_ROUNDS }),
    );
  });
});
