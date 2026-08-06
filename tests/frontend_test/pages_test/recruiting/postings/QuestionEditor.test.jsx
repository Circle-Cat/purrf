import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent, act } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import QuestionEditor from "@/pages/Recruiting/postings/QuestionEditor";

/** Stateful wrapper so onChange updates actually re-render the editor. */
function ControlledEditor({
  initialQuestion,
  onChange,
  onRemove,
  onMoveUp,
  onMoveDown,
}) {
  const [question, setQuestion] = useState(initialQuestion);
  const handleChange = (q) => {
    setQuestion(q);
    onChange(q);
  };
  return (
    <QuestionEditor
      question={question}
      allQuestions={[question]}
      onChange={handleChange}
      onRemove={onRemove ?? (() => {})}
      onMoveUp={onMoveUp ?? (() => {})}
      onMoveDown={onMoveDown ?? (() => {})}
      optionOps={spyOps()}
    />
  );
}

const base = { id: "q2", type: "short_text", label: "Why", required: false };

/** The five whole-form ops FormBuilder supplies, as spies. */
const spyOps = () => ({
  add: vi.fn(),
  rename: vi.fn(),
  remove: vi.fn(),
  reveal: vi.fn(),
  hide: vi.fn(),
});

describe("QuestionEditor", () => {
  it("edits the label", () => {
    const onChange = vi.fn();
    render(
      <QuestionEditor
        question={base}
        allQuestions={[base]}
        onChange={onChange}
        onRemove={() => {}}
        onMoveUp={() => {}}
        onMoveDown={() => {}}
        optionOps={spyOps()}
      />,
    );
    fireEvent.change(screen.getByLabelText("Question"), {
      target: { value: "Why us" },
    });
    expect(onChange).toHaveBeenCalledWith({ ...base, label: "Why us" });
  });

  it("edits the description and clears it to undefined when emptied", () => {
    const onChange = vi.fn();
    render(<ControlledEditor initialQuestion={base} onChange={onChange} />);
    const desc = screen.getByLabelText("Description");
    fireEvent.change(desc, { target: { value: "Explain briefly" } });
    expect(onChange).toHaveBeenCalledWith({
      ...base,
      description: "Explain briefly",
    });
    fireEvent.change(desc, { target: { value: "" } });
    expect(onChange).toHaveBeenLastCalledWith({
      ...base,
      description: undefined,
    });
  });

  it("shows OptionsEditor for choice types", () => {
    render(
      <QuestionEditor
        question={{
          id: "q1",
          type: "single_choice",
          label: "Pick",
          options: ["a"],
        }}
        allQuestions={[]}
        onChange={() => {}}
        onRemove={() => {}}
        onMoveUp={() => {}}
        onMoveDown={() => {}}
        optionOps={spyOps()}
      />,
    );
    expect(
      screen.getByRole("button", { name: "Add option" }),
    ).toBeInTheDocument();
  });

  // The rule is authored from the choice question that reveals this one, so
  // this editor only explains it.
  it("explains the rule that reveals it, naming the revealing question", () => {
    render(
      <QuestionEditor
        question={{ ...base, showWhen: { questionId: "q1", equals: "Yes" } }}
        allQuestions={[
          { id: "q1", type: "single_choice", label: "Car?" },
          base,
        ]}
        onChange={() => {}}
        onRemove={() => {}}
        onMoveUp={() => {}}
        onMoveDown={() => {}}
        optionOps={spyOps()}
      />,
    );
    expect(
      screen.getByText('Only shown when "Car?" = "Yes"'),
    ).toBeInTheDocument();
  });

  it("says so when the question that revealed it is gone", () => {
    render(
      <QuestionEditor
        question={{ ...base, showWhen: { questionId: "q1", equals: "Yes" } }}
        allQuestions={[base]}
        onChange={() => {}}
        onRemove={() => {}}
        onMoveUp={() => {}}
        onMoveDown={() => {}}
        optionOps={spyOps()}
      />,
    );
    expect(
      screen.getByText('Only shown when a removed question = "Yes"'),
    ).toBeInTheDocument();
  });

  it("shows no rule at all for an unconditional question", () => {
    render(
      <QuestionEditor
        question={base}
        allQuestions={[base]}
        onChange={() => {}}
        onRemove={() => {}}
        onMoveUp={() => {}}
        onMoveDown={() => {}}
        optionOps={spyOps()}
      />,
    );
    expect(screen.queryByText(/Only shown when/)).not.toBeInTheDocument();
  });

  it("calls onRemove when the Remove question button is clicked", () => {
    const onRemove = vi.fn();
    render(
      <QuestionEditor
        question={base}
        allQuestions={[base]}
        onChange={() => {}}
        onRemove={onRemove}
        onMoveUp={() => {}}
        onMoveDown={() => {}}
        optionOps={spyOps()}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "Remove question" }));
    expect(onRemove).toHaveBeenCalledTimes(1);
  });

  it("coerces Max length to number and undefined when cleared", () => {
    const onChange = vi.fn();
    const longTextQ = {
      id: "q3",
      type: "long_text",
      label: "Essay",
      required: false,
    };
    render(
      <ControlledEditor initialQuestion={longTextQ} onChange={onChange} />,
    );

    const maxLenInput = screen.getByLabelText("Max length");

    act(() => {
      fireEvent.change(maxLenInput, { target: { value: "10" } });
    });
    expect(onChange).toHaveBeenCalledWith({ ...longTextQ, maxLength: 10 });

    act(() => {
      fireEvent.change(maxLenInput, { target: { value: "" } });
    });
    expect(onChange).toHaveBeenLastCalledWith({
      ...longTextQ,
      maxLength: undefined,
    });
  });

  it("designates an other-specify option", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(
      <QuestionEditor
        question={{
          id: "q1",
          type: "single_choice",
          label: "Src",
          options: ["A", "Others"],
        }}
        allQuestions={[]}
        onChange={onChange}
        onRemove={() => {}}
        onMoveUp={() => {}}
        onMoveDown={() => {}}
        optionOps={spyOps()}
      />,
    );
    await user.click(screen.getByRole("combobox", { name: "Other option" }));
    await user.click(screen.getByRole("option", { name: "Others" }));
    expect(onChange).toHaveBeenCalledWith(
      expect.objectContaining({ otherOption: "Others" }),
    );
  });

  it("offers each option a picker over the form's other questions", async () => {
    const user = userEvent.setup();
    const parent = {
      id: "q1",
      type: "single_choice",
      label: "Car?",
      options: ["Yes"],
    };
    const ops = spyOps();
    render(
      <QuestionEditor
        question={parent}
        allQuestions={[
          parent,
          { id: "q2", type: "short_text", label: "Model" },
        ]}
        onChange={() => {}}
        onRemove={() => {}}
        onMoveUp={() => {}}
        onMoveDown={() => {}}
        optionOps={ops}
      />,
    );
    await user.click(
      screen.getByRole("combobox", {
        name: "Reveal a question when option 1 is selected",
      }),
    );
    // Its own label is never offered -- a question cannot reveal itself.
    expect(screen.queryByRole("option", { name: "Car?" })).toBeNull();
    await user.click(screen.getByRole("option", { name: "Model" }));
    expect(ops.reveal).toHaveBeenCalledWith("Yes", "q2");
  });

  it("shows what each option already reveals", () => {
    const parent = {
      id: "q1",
      type: "single_choice",
      label: "Car?",
      options: ["Yes", "No"],
    };
    render(
      <QuestionEditor
        question={parent}
        allQuestions={[
          parent,
          {
            id: "q2",
            type: "short_text",
            label: "Model",
            showWhen: { questionId: "q1", equals: "Yes" },
          },
        ]}
        onChange={() => {}}
        onRemove={() => {}}
        onMoveUp={() => {}}
        onMoveDown={() => {}}
        optionOps={spyOps()}
      />,
    );
    expect(
      screen.getByRole("button", { name: "Stop revealing Model" }),
    ).toBeInTheDocument();
    // "Yes" is pinned by Model; "No" reveals nothing and stays removable.
    const removes = screen.getAllByRole("button", { name: "Remove option" });
    expect(removes[0]).toBeDisabled();
    expect(removes[1]).not.toBeDisabled();
  });

  // A pair that reveals each other can never be answered, so neither appears.
  it("never offers the question that reveals this one", async () => {
    const user = userEvent.setup();
    const parent = {
      id: "q2",
      type: "single_choice",
      label: "Colour?",
      options: ["Red"],
      showWhen: { questionId: "q1", equals: "Yes" },
    };
    render(
      <QuestionEditor
        question={parent}
        allQuestions={[
          { id: "q1", type: "single_choice", label: "Car?" },
          parent,
          { id: "q3", type: "short_text", label: "Model" },
        ]}
        onChange={() => {}}
        onRemove={() => {}}
        onMoveUp={() => {}}
        onMoveDown={() => {}}
        optionOps={spyOps()}
      />,
    );
    await user.click(
      screen.getByRole("combobox", {
        name: "Reveal a question when option 1 is selected",
      }),
    );
    expect(screen.getByRole("option", { name: "Model" })).toBeInTheDocument();
    expect(screen.queryByRole("option", { name: "Car?" })).toBeNull();
  });

  it("blocks removing a question that other questions are revealed by", () => {
    // Same bind as an option's Remove one level down: dropping it would leave
    // the questions it reveals waiting on an answer no one can give.
    const parent = {
      id: "q1",
      type: "single_choice",
      label: "Need sponsorship?",
      options: ["Yes", "No"],
    };
    const child = {
      id: "q2",
      type: "short_text",
      label: "Which visa?",
      showWhen: { questionId: "q1", equals: "Yes" },
    };
    render(
      <QuestionEditor
        question={parent}
        allQuestions={[parent, child]}
        onChange={vi.fn()}
        onRemove={vi.fn()}
        onMoveUp={vi.fn()}
        onMoveDown={vi.fn()}
        optionOps={spyOps()}
      />,
    );
    expect(
      screen.getByRole("button", { name: "Remove question" }),
    ).toBeDisabled();
    expect(
      screen.getByText(/Stop revealing "Which visa\?" to remove this question/),
    ).toBeInTheDocument();
  });

  it("allows removing a question nothing depends on", () => {
    const question = { id: "q1", type: "short_text", label: "Name" };
    render(
      <QuestionEditor
        question={question}
        allQuestions={[question]}
        onChange={vi.fn()}
        onRemove={vi.fn()}
        onMoveUp={vi.fn()}
        onMoveDown={vi.fn()}
        optionOps={spyOps()}
      />,
    );
    expect(
      screen.getByRole("button", { name: "Remove question" }),
    ).not.toBeDisabled();
  });
});
