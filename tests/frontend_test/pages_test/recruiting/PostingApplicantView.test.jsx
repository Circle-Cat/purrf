import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import PostingApplicantView from "@/pages/Recruiting/components/PostingApplicantView";

const questions = [
  {
    id: "q1",
    type: "single_choice",
    label: "Referred?",
    options: ["yes", "no"],
  },
  {
    id: "q2",
    type: "short_text",
    label: "Referrer name",
    showWhen: { questionId: "q1", equals: "yes" },
  },
];

describe("PostingApplicantView", () => {
  it("renders title, kind, description, profile form and the questions", () => {
    render(
      <PostingApplicantView
        title="SWE Intern"
        kind="employment"
        description="Great role."
        questions={questions}
        profileConfig={{ resume: "required" }}
      />,
    );
    expect(
      screen.getByRole("heading", { name: "SWE Intern" }),
    ).toBeInTheDocument();
    expect(screen.getByText("employment")).toBeInTheDocument();
    expect(screen.getByText("Great role.")).toBeInTheDocument();
    expect(screen.getByText("Profile")).toBeInTheDocument();
    expect(screen.getByText("Contact email")).toBeInTheDocument();
    expect(
      screen.getByRole("radiogroup", { name: "Referred?" }),
    ).toBeInTheDocument();
  });

  it("reveals a showWhen question when its dependency is answered (throwaway state)", () => {
    render(<PostingApplicantView title="T" questions={questions} />);
    expect(screen.queryByLabelText("Referrer name")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("radio", { name: "yes" }));
    expect(screen.getByLabelText("Referrer name")).toBeInTheDocument();
  });

  it("lifts profile value and answers to a parent when controlled props are provided", () => {
    const onProfileChange = vi.fn();
    const onAnswerChange = vi.fn();
    const profileValue = {
      personal: { firstName: "Ada" },
      education: [],
      experience: [],
    };
    render(
      <PostingApplicantView
        title="T"
        questions={questions}
        profileValue={profileValue}
        onProfileChange={onProfileChange}
        answers={{ q1: "yes" }}
        onAnswerChange={onAnswerChange}
      />,
    );
    expect(screen.getByDisplayValue("Ada")).toBeInTheDocument();
    // Controlled `answers` already reveals the showWhen-dependent question.
    expect(screen.getByLabelText("Referrer name")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("radio", { name: "no" }));
    expect(onAnswerChange).toHaveBeenCalledWith("q1", "no");
  });

  it("emits profile changes on field edit when controlled", () => {
    const onProfileChange = vi.fn();
    const profileValue = {
      personal: { firstName: "Sam" },
      education: [],
      experience: [],
    };
    render(
      <PostingApplicantView
        title="T"
        questions={questions}
        profileValue={profileValue}
        onProfileChange={onProfileChange}
      />,
    );
    fireEvent.change(screen.getByLabelText("First name"), {
      target: { value: "Casey" },
    });
    expect(onProfileChange).toHaveBeenCalledWith(
      expect.objectContaining({
        personal: expect.objectContaining({ firstName: "Casey" }),
      }),
    );
  });
});
