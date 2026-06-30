import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import OptionsEditor from "@/pages/Recruiting/postings/OptionsEditor";

describe("OptionsEditor", () => {
  it("adds an option", () => {
    const onChange = vi.fn();
    render(<OptionsEditor options={[]} onChange={onChange} />);
    fireEvent.click(screen.getByRole("button", { name: "Add option" }));
    expect(onChange).toHaveBeenCalledWith([""]);
  });

  it("edits an option by index", () => {
    const onChange = vi.fn();
    render(<OptionsEditor options={["a", "b"]} onChange={onChange} />);
    fireEvent.change(screen.getByLabelText("Option 2"), {
      target: { value: "bb" },
    });
    expect(onChange).toHaveBeenCalledWith(["a", "bb"]);
  });

  it("removes an option by index", () => {
    const onChange = vi.fn();
    render(<OptionsEditor options={["a", "b"]} onChange={onChange} />);
    fireEvent.click(screen.getAllByRole("button", { name: "Remove option" })[0]);
    expect(onChange).toHaveBeenCalledWith(["b"]);
  });
});
