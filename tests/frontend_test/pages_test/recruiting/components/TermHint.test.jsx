import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import TermHint from "@/pages/Recruiting/components/TermHint";

describe("TermHint", () => {
  it("renders the glossary label when given no child", () => {
    render(<TermHint id="stage.recruiter_screening" />);
    expect(screen.getByText("Recruiter screening")).toBeInTheDocument();
  });

  it("renders an explicit child instead of the glossary label", () => {
    render(<TermHint id="stage.recruiter_screening">Screening</TermHint>);
    expect(screen.getByText("Screening")).toBeInTheDocument();
    expect(screen.queryByText("Recruiter screening")).not.toBeInTheDocument();
  });

  it("reveals the hint on keyboard focus", async () => {
    const user = userEvent.setup();
    render(<TermHint id="stage.recruiter_screening" />);

    await user.tab();

    expect(
      await screen.findByText(
        "A recruiter is reviewing your application. Nothing is needed from you right now.",
      ),
    ).toBeInTheDocument();
  });

  it("stacks the hint above the fixed header and sidebar", async () => {
    const user = userEvent.setup();
    render(<TermHint id="stage.recruiter_screening" />);

    await user.tab();

    const hint = await screen.findByText(
      "A recruiter is reviewing your application. Nothing is needed from you right now.",
    );
    expect(hint).toHaveClass("z-[110]");
  });

  it("degrades an unknown id to plain text with no trigger and no throw", () => {
    render(<TermHint id="stage.does_not_exist">Mystery</TermHint>);
    expect(screen.getByText("Mystery")).toBeInTheDocument();
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });

  it("renders nothing for an unknown id with no child", () => {
    const { container } = render(<TermHint id="stage.does_not_exist" />);
    expect(container).toBeEmptyDOMElement();
  });
});
