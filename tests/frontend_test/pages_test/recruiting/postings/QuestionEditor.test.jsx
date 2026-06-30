import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import QuestionEditor from "@/pages/Recruiting/postings/QuestionEditor";

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
        question={{ id: "q1", type: "single_choice", label: "Pick", options: ["a"] }}
        allQuestions={[]}
        onChange={() => {}}
        onRemove={() => {}}
        onMoveUp={() => {}}
        onMoveDown={() => {}}
      />,
    );
    expect(screen.getByRole("button", { name: "Add option" })).toBeInTheDocument();
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
});
