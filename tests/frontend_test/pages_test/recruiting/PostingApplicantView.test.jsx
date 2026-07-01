import { describe, it, expect } from "vitest";
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
});
