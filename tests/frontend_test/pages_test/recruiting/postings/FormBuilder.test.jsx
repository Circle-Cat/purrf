import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import FormBuilder from "@/pages/Recruiting/postings/FormBuilder";

describe("FormBuilder", () => {
  it("adds a question and advances the counter", async () => {
    const onChange = vi.fn();
    render(<FormBuilder formSchema={{ questions: [] }} onChange={onChange} />);
    await userEvent.click(
      screen.getByRole("button", { name: "Add Short text" }),
    );
    expect(onChange).toHaveBeenCalledWith({
      questions: [{ id: "q1", type: "short_text", label: "", required: false }],
      nextSeq: 2,
    });
  });

  // The counter is what stops a delete-then-add from recycling an id, and
  // only the add path recomputes it — every other edit must carry it through
  // untouched, so each of these pins it explicitly.
  it("removes a question, preserving the counter", () => {
    const onChange = vi.fn();
    const qs = [{ id: "q1", type: "short_text", label: "A", required: false }];
    render(
      <FormBuilder
        formSchema={{ questions: qs, nextSeq: 7 }}
        onChange={onChange}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "Remove question" }));
    expect(onChange).toHaveBeenCalledWith({ questions: [], nextSeq: 7 });
  });

  it("moves a question up, preserving the counter", () => {
    const onChange = vi.fn();
    const qs = [
      { id: "q1", type: "short_text", label: "A", required: false },
      { id: "q2", type: "short_text", label: "B", required: false },
    ];
    render(
      <FormBuilder
        formSchema={{ questions: qs, nextSeq: 7 }}
        onChange={onChange}
      />,
    );
    fireEvent.click(screen.getAllByRole("button", { name: "Move up" })[1]);
    expect(onChange).toHaveBeenCalledWith({
      questions: [qs[1], qs[0]],
      nextSeq: 7,
    });
  });

  it("updates a question, preserving the counter", () => {
    const onChange = vi.fn();
    const qs = [{ id: "q1", type: "short_text", label: "A", required: false }];
    render(
      <FormBuilder
        formSchema={{ questions: qs, nextSeq: 7 }}
        onChange={onChange}
      />,
    );
    fireEvent.change(screen.getByLabelText("Label"), {
      target: { value: "B" },
    });
    expect(onChange).toHaveBeenCalledWith({
      questions: [{ ...qs[0], label: "B" }],
      nextSeq: 7,
    });
  });
});
