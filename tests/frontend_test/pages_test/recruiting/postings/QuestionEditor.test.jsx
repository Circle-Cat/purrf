import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent, act } from "@testing-library/react";
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
    />
  );
}

const base = { id: "q2", type: "short_text", label: "Why", required: false };

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
      />,
    );
    fireEvent.change(screen.getByLabelText("Label"), {
      target: { value: "Why us" },
    });
    expect(onChange).toHaveBeenCalledWith({ ...base, label: "Why us" });
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
      />,
    );
    expect(
      screen.getByRole("button", { name: "Add option" }),
    ).toBeInTheDocument();
  });

  it("lists only OTHER questions in the showWhen dependency dropdown", () => {
    const q1 = { id: "q1", type: "short_text", label: "First" };
    render(
      <QuestionEditor
        question={base}
        allQuestions={[q1, base]}
        onChange={() => {}}
        onRemove={() => {}}
        onMoveUp={() => {}}
        onMoveDown={() => {}}
      />,
    );
    const select = screen.getByLabelText("Depends on");
    const values = Array.from(select.options).map((o) => o.value);
    expect(values).toEqual(["", "q1"]); // "none" + the other question, not q2 itself
  });

  it("sets showWhen when a dependency and value are chosen", () => {
    const q1 = { id: "q1", type: "short_text", label: "First" };
    const onChange = vi.fn();
    render(
      <QuestionEditor
        question={base}
        allQuestions={[q1, base]}
        onChange={onChange}
        onRemove={() => {}}
        onMoveUp={() => {}}
        onMoveDown={() => {}}
      />,
    );
    fireEvent.change(screen.getByLabelText("Depends on"), {
      target: { value: "q1" },
    });
    expect(onChange).toHaveBeenCalledWith({
      ...base,
      showWhen: { questionId: "q1", equals: "" },
    });
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

  it("designates an other-specify option", () => {
    const onChange = vi.fn();
    render(
      <QuestionEditor
        question={{ id: "q1", type: "single_choice", label: "Src", options: ["A", "Others"] }}
        allQuestions={[]}
        onChange={onChange}
        onRemove={() => {}}
        onMoveUp={() => {}}
        onMoveDown={() => {}}
      />,
    );
    fireEvent.change(screen.getByLabelText("Other option"), {
      target: { value: "Others" },
    });
    expect(onChange).toHaveBeenCalledWith(
      expect.objectContaining({ otherOption: "Others" }),
    );
  });

  it("clears otherOption when its option is removed", () => {
    const onChange = vi.fn();
    render(
      <QuestionEditor
        question={{
          id: "q1", type: "single_choice", label: "Src",
          options: ["A", "Others"], otherOption: "Others",
        }}
        allQuestions={[]}
        onChange={onChange}
        onRemove={() => {}}
        onMoveUp={() => {}}
        onMoveDown={() => {}}
      />,
    );
    // Remove the 2nd option ("Others") via OptionsEditor.
    fireEvent.click(screen.getAllByRole("button", { name: "Remove option" })[1]);
    expect(onChange).toHaveBeenCalledWith(
      expect.objectContaining({ options: ["A"], otherOption: undefined }),
    );
  });
});
