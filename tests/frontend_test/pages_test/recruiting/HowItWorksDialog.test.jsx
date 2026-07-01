import { describe, it, expect } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import HowItWorksDialog from "@/pages/Recruiting/components/HowItWorksDialog";

const guide = {
  title: "How postings work",
  description: "The lifecycle summary.",
  steps: [
    { title: "Create a draft", detail: "Start here." },
    { title: "Submit for review", detail: "Pick a reviewer." },
  ],
  statuses: [
    { name: "Draft", description: "Editable by you." },
    { name: "Published", description: "Live to candidates." },
  ],
  notes: ["Two approvers required.", "No self-review."],
};

describe("HowItWorksDialog", () => {
  it("renders the trigger button and hides content until opened", () => {
    render(<HowItWorksDialog {...guide} />);
    expect(
      screen.getByRole("button", { name: "How it works" }),
    ).toBeInTheDocument();
    expect(screen.queryByText("How postings work")).not.toBeInTheDocument();
  });

  it("opens the dialog and shows title, steps, statuses, and notes", () => {
    render(<HowItWorksDialog {...guide} />);
    fireEvent.click(screen.getByRole("button", { name: "How it works" }));
    expect(screen.getByText("How postings work")).toBeInTheDocument();
    expect(screen.getByText("Create a draft")).toBeInTheDocument();
    expect(screen.getByText("Submit for review")).toBeInTheDocument();
    expect(screen.getByText("Draft")).toBeInTheDocument();
    expect(screen.getByText("Published")).toBeInTheDocument();
    expect(screen.getByText("Two approvers required.")).toBeInTheDocument();
    expect(screen.getByText("No self-review.")).toBeInTheDocument();
  });

  it("omits the notes section when notes is empty", () => {
    render(<HowItWorksDialog {...guide} notes={[]} />);
    fireEvent.click(screen.getByRole("button", { name: "How it works" }));
    expect(screen.queryByText("Good to know")).not.toBeInTheDocument();
  });

  it("omits the notes section when notes is not provided", () => {
    render(<HowItWorksDialog {...guide} notes={undefined} />);
    fireEvent.click(screen.getByRole("button", { name: "How it works" }));
    expect(screen.queryByText("Good to know")).not.toBeInTheDocument();
  });
});
