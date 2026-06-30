import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import JobBasicsSection from "@/pages/Recruiting/postings/JobBasicsSection";

describe("JobBasicsSection", () => {
  const props = { title: "", description: "", kind: "activity" };

  it("emits title changes", () => {
    const onChange = vi.fn();
    render(<JobBasicsSection {...props} onChange={onChange} />);
    fireEvent.change(screen.getByLabelText("Title"), {
      target: { value: "SWE" },
    });
    expect(onChange).toHaveBeenCalledWith({ title: "SWE" });
  });

  it("emits kind changes via native select", () => {
    const onChange = vi.fn();
    render(<JobBasicsSection {...props} onChange={onChange} />);
    fireEvent.change(screen.getByLabelText("Kind"), {
      target: { value: "employment" },
    });
    expect(onChange).toHaveBeenCalledWith({ kind: "employment" });
  });
});
