import React from "react";
import { render, screen, within, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import RoundFeedbackPage from "@/pages/MentorshipManagement/RoundFeedbackPage";
import { getRoundFeedback } from "@/api/mentorshipApi";

vi.mock("@/api/mentorshipApi", () => ({
  getRoundFeedback: vi.fn(),
}));

// Cara (mentee) sent it, rating her mentor differently from the programme;
// Bob (mentor) sent it about two mentees, one of whom no longer resolves;
// Dan (mentee) did not send it.
const FEEDBACK = {
  roundId: 7,
  roundName: "Mentorship 2026 Fall",
  owed: 3,
  sent: 2,
  participants: [
    {
      userId: 3102,
      name: "Bob Liu",
      role: "mentor",
      hasSubmitted: true,
      mostValuableAspects: null,
      challenges: "Scheduling",
      programRating: 5,
      partnerFeedback: [
        {
          partnerId: 3103,
          partnerName: "Cara Wang",
          rating: 3,
          feedback: null,
        },
        {
          partnerId: 3999,
          partnerName: null,
          rating: 1,
          feedback: "Stopped replying",
        },
      ],
    },
    {
      userId: 3103,
      name: "Cara Wang",
      role: "mentee",
      hasSubmitted: true,
      mostValuableAspects: "Career advice",
      challenges: null,
      programRating: 4,
      partnerFeedback: [
        {
          partnerId: 3102,
          partnerName: "Bob Liu",
          rating: 2,
          feedback: "Often late",
        },
      ],
    },
    {
      userId: 3105,
      name: "Dan Ma",
      role: "mentee",
      hasSubmitted: false,
      mostValuableAspects: null,
      challenges: null,
      programRating: null,
      partnerFeedback: [],
    },
  ],
};

const renderPage = () =>
  render(
    <MemoryRouter initialEntries={["/mentorship-management/rounds/7/feedback"]}>
      <Routes>
        <Route
          path="/mentorship-management/rounds/:roundId/feedback"
          element={<RoundFeedbackPage />}
        />
      </Routes>
    </MemoryRouter>,
  );

const rowOf = (name) => screen.getByText(name).closest("tr");
const cellsOf = (name) =>
  within(rowOf(name))
    .getAllByRole("cell")
    .map((c) => c.textContent);

describe("RoundFeedbackPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getRoundFeedback.mockResolvedValue({ data: FEEDBACK });
  });

  it("asks for the round in the URL and shows its counts", async () => {
    renderPage();

    expect(
      await screen.findByText("Feedback — Mentorship 2026 Fall"),
    ).toBeInTheDocument();
    expect(getRoundFeedback).toHaveBeenCalledWith("7");
    expect(screen.getByText("2 of 3 sent")).toBeInTheDocument();
  });

  it("lays the columns out in the form's order, with no Sent column", async () => {
    renderPage();
    await screen.findByText("Cara Wang");

    expect(
      screen.getAllByRole("columnheader").map((h) => h.textContent),
    ).toEqual([
      "Name",
      "Role",
      "Most Valuable Aspects",
      "Challenges",
      "Program Rating",
      "Rating of Partner",
      "Feedback About Partner",
    ]);
  });

  it("shows what each person wrote, about each partner on their own row", async () => {
    renderPage();
    await screen.findByText("Cara Wang");

    expect(cellsOf("Cara Wang")).toEqual([
      "Cara WangID 3103",
      "mentee",
      "Career advice",
      "—",
      "4/5",
      "Bob Liu: 2/5",
      "Bob Liu: “Often late”",
    ]);
    expect(cellsOf("Bob Liu").slice(2)).toEqual([
      "—",
      "Scheduling",
      "5/5",
      "Cara Wang: 3/5User 3999: 1/5",
      "User 3999: “Stopped replying”",
    ]);
    expect(cellsOf("Dan Ma").slice(1)).toEqual([
      "mentee",
      "—",
      "—",
      "—",
      "—",
      "—",
    ]);
  });

  it("narrows by role and to those who have not sent it", async () => {
    renderPage();
    await screen.findByText("Cara Wang");

    fireEvent.change(screen.getByLabelText("Role"), {
      target: { value: "mentor" },
    });
    expect(screen.getByText("Bob Liu")).toBeInTheDocument();
    expect(screen.queryByText("Cara Wang")).not.toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Role"), {
      target: { value: "all" },
    });
    fireEvent.click(screen.getByLabelText("Not sent only"));
    expect(screen.getByText("Dan Ma")).toBeInTheDocument();
    expect(screen.queryByText("Bob Liu")).not.toBeInTheDocument();
    expect(screen.queryByText("Cara Wang")).not.toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Role"), {
      target: { value: "mentor" },
    });
    expect(screen.getByText("Nobody here.")).toBeInTheDocument();
  });

  it("says so when the feedback cannot be loaded", async () => {
    vi.spyOn(console, "error").mockImplementation(() => {});
    getRoundFeedback.mockRejectedValue(new Error("boom"));

    renderPage();

    expect(
      await screen.findByText("Could not load this round's feedback."),
    ).toBeInTheDocument();
  });
});
