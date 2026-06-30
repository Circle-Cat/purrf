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

  it("multi_choice toggle: selects then deselects an option", () => {
    const onAnswerChange = vi.fn();
    const question = {
      id: "q1",
      type: "multi_choice",
      label: "Skills",
      options: ["React", "Vue"],
    };
    const { rerender } = render(
      <FormRenderer
        questions={[question]}
        answers={{}}
        onAnswerChange={onAnswerChange}
      />,
    );
    // clicking an option adds it
    fireEvent.click(screen.getByRole("checkbox", { name: "React" }));
    expect(onAnswerChange).toHaveBeenCalledWith("q1", ["React"]);

    // clicking again with that option already selected removes it
    onAnswerChange.mockClear();
    rerender(
      <FormRenderer
        questions={[question]}
        answers={{ q1: ["React"] }}
        onAnswerChange={onAnswerChange}
      />,
    );
    fireEvent.click(screen.getByRole("checkbox", { name: "React" }));
    expect(onAnswerChange).toHaveBeenCalledWith("q1", []);
  });

  it("showWhen with an array answer: visible when equals is a member of the array", () => {
    const questions = [
      {
        id: "q1",
        type: "multi_choice",
        label: "Topics",
        options: ["Yes", "No"],
      },
      {
        id: "q2",
        type: "short_text",
        label: "Details",
        showWhen: { questionId: "q1", equals: "No" },
      },
    ];
    render(
      <FormRenderer
        questions={questions}
        answers={{ q1: ["No"] }}
        onAnswerChange={() => {}}
      />,
    );
    expect(screen.getByText("Details")).toBeInTheDocument();
  });

  it("long_text renders a textarea and fires onAnswerChange on change", () => {
    const onAnswerChange = vi.fn();
    render(
      <FormRenderer
        questions={[{ id: "q1", type: "long_text", label: "Bio" }]}
        answers={{}}
        onAnswerChange={onAnswerChange}
      />,
    );
    const textarea = screen.getByRole("textbox", { name: "Bio" });
    expect(textarea.tagName.toLowerCase()).toBe("textarea");
    fireEvent.change(textarea, { target: { value: "Hello" } });
    expect(onAnswerChange).toHaveBeenCalledWith("q1", "Hello");
  });

  it("exact_text renders a text input", () => {
    render(
      <FormRenderer
        questions={[{ id: "q1", type: "exact_text", label: "Code" }]}
        answers={{}}
        onAnswerChange={() => {}}
      />,
    );
    const input = screen.getByRole("textbox", { name: "Code" });
    expect(input.tagName.toLowerCase()).toBe("input");
  });
});
