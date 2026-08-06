import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import OptionsEditor from "@/pages/Recruiting/postings/OptionsEditor";

/** All five ops as spies, so a test can assert on the one it exercises. */
const spyOps = () => ({
  add: vi.fn(),
  rename: vi.fn(),
  remove: vi.fn(),
  reveal: vi.fn(),
  hide: vi.fn(),
});

/**
 * Render with sensible defaults: no option reveals anything, and one other
 * question ("Model") is available to reveal.
 */
const renderEditor = ({
  options = ["a", "b"],
  revealedBy = () => [],
  pickable = () => [{ id: "q9", label: "Model" }],
  ops = spyOps(),
} = {}) => {
  render(
    <OptionsEditor
      options={options}
      revealedBy={revealedBy}
      pickable={pickable}
      ops={ops}
    />,
  );
  return ops;
};

describe("OptionsEditor", () => {
  it("adds an option", () => {
    const ops = renderEditor({ options: [] });
    fireEvent.click(screen.getByRole("button", { name: "Add option" }));
    expect(ops.add).toHaveBeenCalledTimes(1);
  });

  it("renames an option by index", () => {
    const ops = renderEditor();
    fireEvent.change(screen.getByLabelText("Option 2"), {
      target: { value: "bb" },
    });
    expect(ops.rename).toHaveBeenCalledWith(1, "bb");
  });

  it("removes an option by index", () => {
    const ops = renderEditor();
    fireEvent.click(
      screen.getAllByRole("button", { name: "Remove option" })[0],
    );
    expect(ops.remove).toHaveBeenCalledWith(0);
  });

  it("reveals a question when one is picked for an option", async () => {
    const user = userEvent.setup();
    const ops = renderEditor({ options: ["Yes"] });
    await user.click(
      screen.getByRole("combobox", {
        name: "Reveal a question when option 1 is selected",
      }),
    );
    await user.click(screen.getByRole("option", { name: "Model" }));
    expect(ops.reveal).toHaveBeenCalledWith("Yes", "q9");
  });

  it("lists the questions an option already reveals, with a way to unlink", () => {
    const ops = renderEditor({
      options: ["Yes"],
      revealedBy: (o) => (o === "Yes" ? [{ id: "q9", label: "Model" }] : []),
    });
    expect(screen.getByText("Model")).toBeInTheDocument();
    fireEvent.click(
      screen.getByRole("button", { name: "Stop revealing Model" }),
    );
    expect(ops.hide).toHaveBeenCalledWith("q9");
  });

  it("falls back to the question id when its label is blank", () => {
    renderEditor({
      options: ["Yes"],
      revealedBy: () => [{ id: "q9", label: "" }],
    });
    expect(screen.getByText("q9")).toBeInTheDocument();
  });

  // Removing it would leave those questions waiting on an answer no one can
  // give, so the option has to be freed first.
  it("blocks removing an option that still reveals a question", () => {
    renderEditor({
      options: ["Yes"],
      revealedBy: () => [{ id: "q9", label: "Model" }],
    });
    expect(
      screen.getByRole("button", { name: "Remove option" }),
    ).toBeDisabled();
    expect(
      screen.getByText("Stop revealing these to remove this option."),
    ).toBeInTheDocument();
  });

  it("leaves an option that reveals nothing removable", () => {
    renderEditor({ options: ["Yes"] });
    expect(
      screen.getByRole("button", { name: "Remove option" }),
    ).not.toBeDisabled();
    expect(screen.queryByText(/Stop revealing these/)).not.toBeInTheDocument();
  });

  // An option with no text can never be answered, so there is nothing to hang
  // a question on yet.
  it("offers no picker for a blank option", () => {
    renderEditor({ options: ["  "] });
    expect(screen.queryByRole("combobox")).not.toBeInTheDocument();
  });

  it("offers no picker when there is no other question to reveal", () => {
    renderEditor({ options: ["Yes"], pickable: () => [] });
    expect(screen.queryByRole("combobox")).not.toBeInTheDocument();
  });
});
