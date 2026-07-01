import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import FormBuilder from "@/pages/Recruiting/postings/FormBuilder";

describe("FormBuilder", () => {
  it("adds a question of the chosen type with a unique id", () => {
    const onChange = vi.fn();
    render(<FormBuilder questions={[]} onChange={onChange} />);
    fireEvent.click(screen.getByRole("button", { name: "Add Short text" }));
    expect(onChange).toHaveBeenCalledWith([
      { id: "q1", type: "short_text", label: "", required: false },
    ]);
  });

  it("removes a question", () => {
    const onChange = vi.fn();
    const qs = [{ id: "q1", type: "short_text", label: "A", required: false }];
    render(<FormBuilder questions={qs} onChange={onChange} />);
    fireEvent.click(screen.getByRole("button", { name: "Remove question" }));
    expect(onChange).toHaveBeenCalledWith([]);
  });

  it("moves a question up", () => {
    const onChange = vi.fn();
    const qs = [
      { id: "q1", type: "short_text", label: "A", required: false },
      { id: "q2", type: "short_text", label: "B", required: false },
    ];
    render(<FormBuilder questions={qs} onChange={onChange} />);
    fireEvent.click(screen.getAllByRole("button", { name: "Move up" })[1]);
    expect(onChange).toHaveBeenCalledWith([qs[1], qs[0]]);
  });
});
