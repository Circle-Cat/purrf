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
    render(
      <FormRenderer questions={QS} answers={{}} onAnswerChange={() => {}} />,
    );
    expect(screen.getByText("Fluent?")).toBeInTheDocument();
  });

  it("renders a question's description as help text, and omits it when absent", () => {
    render(
      <FormRenderer
        questions={[
          {
            id: "q1",
            type: "short_text",
            label: "Name",
            description: "Your legal name",
          },
          { id: "q2", type: "short_text", label: "Age" },
        ]}
        answers={{}}
        onAnswerChange={() => {}}
      />,
    );
    expect(screen.getByText("Your legal name")).toBeInTheDocument();
    // The description-less question renders only its label.
    expect(screen.getByText("Age")).toBeInTheDocument();
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

  it("does not render blank/whitespace options in a single_choice preview", () => {
    render(
      <FormRenderer
        questions={[
          {
            id: "q1",
            type: "single_choice",
            label: "Pick",
            options: ["Yes", "", "  "],
          },
        ]}
        answers={{}}
        onAnswerChange={() => {}}
      />,
    );
    expect(screen.getAllByRole("radio")).toHaveLength(1);
    expect(screen.getByRole("radio", { name: "Yes" })).toBeInTheDocument();
  });

  it("does not render blank/whitespace options in a multi_choice preview", () => {
    render(
      <FormRenderer
        questions={[
          {
            id: "q1",
            type: "multi_choice",
            label: "Pick",
            options: ["A", "", "B"],
          },
        ]}
        answers={{}}
        onAnswerChange={() => {}}
      />,
    );
    expect(screen.getAllByRole("checkbox")).toHaveLength(2);
  });

  it("reveals an inline specify input when the designated single_choice option is selected", () => {
    const onAnswerChange = vi.fn();
    const q = {
      id: "q1",
      type: "single_choice",
      label: "Src",
      options: ["Friend", "Others"],
      otherOption: "Others",
    };
    const { rerender } = render(
      <FormRenderer
        questions={[q]}
        answers={{ q1: "Friend" }}
        onAnswerChange={onAnswerChange}
      />,
    );
    expect(
      screen.queryByLabelText("Others (please specify)"),
    ).not.toBeInTheDocument();
    rerender(
      <FormRenderer
        questions={[q]}
        answers={{ q1: "Others" }}
        onAnswerChange={onAnswerChange}
      />,
    );
    const input = screen.getByLabelText("Others (please specify)");
    fireEvent.change(input, { target: { value: "Hackathon" } });
    expect(onAnswerChange).toHaveBeenCalledWith("q1__other", "Hackathon");
  });

  it("reveals the specify input for multi_choice only when the designated option is among the selected", () => {
    const q = {
      id: "q1",
      type: "multi_choice",
      label: "Src",
      options: ["A", "Others"],
      otherOption: "Others",
    };
    const { rerender } = render(
      <FormRenderer
        questions={[q]}
        answers={{ q1: ["A"] }}
        onAnswerChange={() => {}}
      />,
    );
    expect(
      screen.queryByLabelText("Others (please specify)"),
    ).not.toBeInTheDocument();
    rerender(
      <FormRenderer
        questions={[q]}
        answers={{ q1: ["A", "Others"] }}
        onAnswerChange={() => {}}
      />,
    );
    expect(
      screen.getByLabelText("Others (please specify)"),
    ).toBeInTheDocument();
  });
});
