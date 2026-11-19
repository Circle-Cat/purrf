import { render, screen, within } from "@testing-library/react";
import { describe, it, expect } from "vitest";

import StageProgress from "@/components/common/StageProgress";

const narrowText = (label, index, total) =>
  `${label} · step ${index} of ${total}`;

const renderBar = (steps, tone) =>
  render(
    <StageProgress
      steps={steps}
      tone={tone}
      label="Program progress"
      narrowText={narrowText}
    />,
  );

describe("StageProgress", () => {
  it("renders an ordered list with readable step states", () => {
    renderBar([
      { key: "a", label: "Apply", state: "done" },
      { key: "b", label: "Learn", state: "current" },
      { key: "c", label: "Finish", state: "upcoming" },
    ]);

    const list = screen.getByRole("list", { name: "Program progress" });
    expect(list.tagName).toBe("OL");
    const items = within(list).getAllByRole("listitem");
    expect(items[0]).toHaveTextContent("Apply (done)");
    expect(items[1]).toHaveAttribute("aria-current", "step");
    expect(items[1]).toHaveTextContent("Learn (current step)");
    expect(items[2]).toHaveTextContent(/^Finish$/);
  });

  it("strikes and announces a missed step", () => {
    renderBar([
      { key: "a", label: "Apply", state: "failed" },
      { key: "b", label: "Learn", state: "upcoming" },
    ]);

    const missed = screen.getByText("(missed)").parentElement;
    expect(missed).toHaveClass("line-through");
    expect(screen.getByText("Apply · step 1 of 2")).toBeInTheDocument();
  });

  it("colours the current step amber in the amber tone", () => {
    renderBar(
      [
        { key: "a", label: "Apply", state: "current" },
        { key: "b", label: "Learn", state: "upcoming" },
      ],
      "amber",
    );

    const list = screen.getByRole("list");
    const label = within(list).getByText("Apply");
    expect(label.className).toMatch(/amber/);
  });

  it("shows the current step and its position on narrow screens", () => {
    renderBar([
      { key: "a", label: "Apply", state: "done" },
      { key: "b", label: "Learn", state: "done" },
      { key: "c", label: "Finish", state: "current" },
    ]);

    const line = screen.getByText("Finish · step 3 of 3");
    expect(line.parentElement).toHaveClass("sm:hidden");
    expect(screen.getByRole("list")).toHaveClass("hidden", "sm:grid");
  });
});
