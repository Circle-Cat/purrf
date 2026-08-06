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

describe("read-only mode", () => {
  // No onAnswerChange: read-only mode never calls it, and the prop defaults
  // to a no-op precisely so no call site has to pass ceremony.
  const renderReadOnly = (questions, answers, idPrefix) =>
    render(
      <FormRenderer
        questions={questions}
        answers={answers}
        readOnly
        idPrefix={idPrefix}
      />,
    );

  it("keeps the line breaks in a long_text answer", () => {
    renderReadOnly([{ id: "q1", type: "long_text", label: "Why us?" }], {
      q1: "First paragraph.\n\nSecond paragraph.",
    });
    const block = screen.getByText(/First paragraph/);
    expect(block).toHaveClass("whitespace-pre-wrap");
    expect(block.textContent).toBe("First paragraph.\n\nSecond paragraph.");
  });

  it("renders a short_text answer as text, not an input", () => {
    renderReadOnly([{ id: "q1", type: "short_text", label: "Name?" }], {
      q1: "Alice",
    });
    expect(screen.getByText("Alice")).toBeInTheDocument();
    expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
  });

  it("treats a question with no type as text", () => {
    renderReadOnly([{ id: "q1", label: "Legacy question" }], { q1: "Yes" });
    expect(screen.getByText("Yes")).toBeInTheDocument();
  });

  it("shows Not answered for a blank answer", () => {
    renderReadOnly([{ id: "q1", type: "short_text", label: "Salary?" }], {
      q1: "   ",
    });
    expect(screen.getByText("Not answered")).toBeInTheDocument();
  });

  it("shows Not answered for a missing answer", () => {
    renderReadOnly([{ id: "q1", type: "short_text", label: "Salary?" }], {});
    expect(screen.getByText("Not answered")).toBeInTheDocument();
  });

  it("shows unselected options alongside selected ones, all disabled", () => {
    renderReadOnly(
      [
        {
          id: "q1",
          type: "multi_choice",
          label: "Work mode",
          options: ["Remote", "Hybrid", "On-site"],
        },
      ],
      { q1: ["Remote", "Hybrid"] },
    );
    const boxes = screen.getAllByRole("checkbox");
    expect(boxes).toHaveLength(3);
    expect(boxes[0]).toBeChecked();
    expect(boxes[1]).toBeChecked();
    expect(boxes[2]).not.toBeChecked();
    boxes.forEach((b) => expect(b).toBeDisabled());
  });

  it("shows the other-option free text as text", () => {
    renderReadOnly(
      [
        {
          id: "q1",
          type: "single_choice",
          label: "Work mode",
          options: ["Remote", "Other"],
          otherOption: "Other",
        },
      ],
      { q1: "Other", q1__other: "One day on-site weekly" },
    );
    expect(screen.getByText("One day on-site weekly")).toBeInTheDocument();
    expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
  });

  it("still hides a question whose showWhen condition is unmet", () => {
    renderReadOnly(
      [
        { id: "q1", type: "short_text", label: "Base" },
        {
          id: "q2",
          type: "short_text",
          label: "Conditional",
          showWhen: { questionId: "q1", equals: "yes" },
        },
      ],
      { q1: "no", q2: "stale" },
    );
    expect(screen.queryByText("Conditional")).not.toBeInTheDocument();
  });

  it("renders a recorded array under a question whose type is now text", () => {
    // The owner changed q1 from multi_choice to short_text after this answer
    // was recorded. The value must still show, not read "Not answered".
    renderReadOnly([{ id: "q1", type: "short_text", label: "Work mode" }], {
      q1: ["Remote", "Hybrid"],
    });
    expect(screen.getByText("Remote")).toBeInTheDocument();
    expect(screen.getByText("Hybrid")).toBeInTheDocument();
    expect(screen.queryByText("Not answered")).not.toBeInTheDocument();
  });

  it("renders a recorded object under a text question as JSON", () => {
    renderReadOnly([{ id: "q1", type: "short_text", label: "Work mode" }], {
      q1: { nested: true },
    });
    expect(screen.getByText(/"nested": true/)).toBeInTheDocument();
    expect(screen.queryByText("Not answered")).not.toBeInTheDocument();
  });

  it("keeps a multi_choice answer whose option was deleted from the form", () => {
    renderReadOnly(
      [
        {
          id: "q1",
          type: "multi_choice",
          label: "Work mode",
          options: ["Remote", "Hybrid"],
        },
      ],
      { q1: ["Remote", "Telepathy"] },
    );
    expect(screen.getByRole("checkbox", { name: "Remote" })).toBeChecked();
    const retired = screen.getByRole("checkbox", {
      name: "Telepathy (no longer an option)",
    });
    expect(retired).toBeChecked();
    expect(retired).toBeDisabled();
  });

  it("keeps a single_choice answer whose option was deleted from the form", () => {
    renderReadOnly(
      [
        {
          id: "q1",
          type: "single_choice",
          label: "Work mode",
          options: ["Remote", "Hybrid"],
        },
      ],
      { q1: "Telepathy" },
    );
    const retired = screen.getByRole("radio", {
      name: "Telepathy (no longer an option)",
    });
    expect(retired).toBeChecked();
    expect(retired).toBeDisabled();
  });

  it("checks the matching box when a multi_choice answer was recorded as a string", () => {
    // Drift the other way: the question was single_choice when this answer
    // was recorded, so the value is a bare string.
    renderReadOnly(
      [
        {
          id: "q1",
          type: "multi_choice",
          label: "Work mode",
          options: ["Remote", "Hybrid"],
        },
      ],
      { q1: "Remote" },
    );
    expect(screen.getByRole("checkbox", { name: "Remote" })).toBeChecked();
    expect(screen.getByRole("checkbox", { name: "Hybrid" })).not.toBeChecked();
    expect(screen.queryByText("(no longer an option)")).not.toBeInTheDocument();
  });

  it("keeps a single_choice answer recorded as an array", () => {
    // A radio group can mark only one member, so the whole recorded list is
    // surfaced as one retired row rather than being flattened and half lost.
    renderReadOnly(
      [
        {
          id: "q1",
          type: "single_choice",
          label: "Work mode",
          options: ["Remote", "Hybrid"],
        },
      ],
      { q1: ["Remote", "Telepathy"] },
    );
    expect(
      screen.getByRole("radio", {
        name: "Remote, Telepathy (no longer an option)",
      }),
    ).toBeChecked();
  });

  it("does not render a retired row for a single_choice answer recorded as an empty array", () => {
    // The question was multi_choice with no options picked when this answer
    // was recorded, then changed to single_choice. An empty selection means
    // nothing was picked, not a retired choice — it must not surface as a
    // checked row with no label text.
    renderReadOnly(
      [
        {
          id: "q1",
          type: "single_choice",
          label: "Work mode",
          options: ["Remote", "Hybrid"],
        },
      ],
      { q1: [] },
    );
    expect(screen.queryByText("(no longer an option)")).not.toBeInTheDocument();
    expect(screen.getByRole("radio", { name: "Remote" })).not.toBeChecked();
    expect(screen.getByRole("radio", { name: "Hybrid" })).not.toBeChecked();
  });

  it("does not duplicate the other option into the retired rows", () => {
    renderReadOnly(
      [
        {
          id: "q1",
          type: "single_choice",
          label: "Work mode",
          options: ["Remote", "Other"],
          otherOption: "Other",
        },
      ],
      { q1: "Other", q1__other: "Two days on-site" },
    );
    expect(screen.getAllByRole("radio")).toHaveLength(2);
    expect(screen.queryByText("(no longer an option)")).not.toBeInTheDocument();
    expect(screen.getByText("Two days on-site")).toBeInTheDocument();
  });

  it("drops the required asterisk and labels no control", () => {
    renderReadOnly(
      [{ id: "q1", type: "short_text", label: "Name?", required: true }],
      { q1: "Alice" },
    );
    const label = screen.getByText("Name?");
    expect(label.tagName).toBe("P");
    expect(label.textContent).toBe("Name?");
  });

  it("drops the required asterisk on the other-option label too", () => {
    renderReadOnly(
      [
        {
          id: "q1",
          type: "single_choice",
          label: "Work mode",
          options: ["Remote", "Other"],
          otherOption: "Other",
        },
      ],
      { q1: "Other", q1__other: "Two days on-site" },
    );
    // The option row's own <label> also reads "Other"; the heading above the
    // free text is the <p>.
    const heading = screen
      .getAllByText("Other")
      .find((el) => el.tagName === "P");
    expect(heading).toBeDefined();
    expect(heading.textContent).toBe("Other");
  });

  it("prefixes DOM ids so two copies can coexist", () => {
    const { container } = renderReadOnly(
      [
        {
          id: "q1",
          type: "single_choice",
          label: "Work mode",
          options: ["Remote"],
        },
      ],
      { q1: "Remote" },
      "other-201-",
    );
    expect(
      container.querySelector('input[name="other-201-q1"]'),
    ).toBeInTheDocument();
  });
});
