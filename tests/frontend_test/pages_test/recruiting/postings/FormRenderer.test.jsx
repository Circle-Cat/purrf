import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import FormRenderer from "@/pages/Recruiting/postings/FormRenderer";

const QS = [
  { id: "q1", type: "single_choice", label: "Fluent?", options: ["Yes", "No"] },
  {
    id: "q2",
    type: "short_text",
    label: "Explain",
    showWhen: { questionId: "q1", equals: "No" },
  },
];

describe("FormRenderer", () => {
  it("renders a labelled control per question", () => {
    render(<FormRenderer questions={QS} answers={{}} onAnswerChange={() => {}} />);
    expect(screen.getByText("Fluent?")).toBeInTheDocument();
  });

  it("hides a showWhen question until the dependency matches", () => {
    const { rerender } = render(
      <FormRenderer questions={QS} answers={{}} onAnswerChange={() => {}} />,
    );
    expect(screen.queryByText("Explain")).not.toBeInTheDocument();
    rerender(
      <FormRenderer
        questions={QS}
        answers={{ q1: "No" }}
        onAnswerChange={() => {}}
      />,
    );
    expect(screen.getByText("Explain")).toBeInTheDocument();
  });

  it("fires onAnswerChange when a short_text answer changes", () => {
    const onAnswerChange = vi.fn();
    render(
      <FormRenderer
        questions={[{ id: "q1", type: "short_text", label: "Name" }]}
        answers={{}}
        onAnswerChange={onAnswerChange}
      />,
    );
    fireEvent.change(screen.getByLabelText("Name"), {
      target: { value: "Ann" },
    });
    expect(onAnswerChange).toHaveBeenCalledWith("q1", "Ann");
  });
});
