import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect } from "vitest";
import "@testing-library/jest-dom";

import { Button } from "@/components/ui/button";
import DisabledReason from "@/pages/AdminTraining/components/DisabledReason";

describe("DisabledReason", () => {
  it("renders the control as is when there is no reason", () => {
    render(
      <DisabledReason reason={null}>
        <Button>Publish</Button>
      </DisabledReason>,
    );

    const button = screen.getByRole("button", { name: "Publish" });
    expect(button.parentElement).not.toHaveAttribute("tabindex");
    expect(screen.queryByRole("tooltip")).not.toBeInTheDocument();
  });

  it("lets the pointer through a disabled control to the wrapper", () => {
    render(
      <DisabledReason reason="Pick a course to filter by">
        <select aria-label="On this course" disabled />
      </DisabledReason>,
    );

    // A browser sends a disabled select no mouse events; without this the
    // wrapper under it would never see the hover.
    expect(screen.getByLabelText("On this course").parentElement).toHaveClass(
      "[&>:disabled]:pointer-events-none",
    );
  });

  it("says why on keyboard focus, though the control itself is disabled", async () => {
    const user = userEvent.setup();
    render(
      <DisabledReason reason="Run this package to completion first">
        <Button disabled>Publish</Button>
      </DisabledReason>,
    );

    await user.tab();

    expect(
      screen.getByRole("button", { name: "Publish" }).parentElement,
    ).toHaveFocus();
    expect(
      await screen.findByRole("tooltip", {
        name: "Run this package to completion first",
      }),
    ).toBeInTheDocument();
  });
});
