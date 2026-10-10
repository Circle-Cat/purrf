import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi } from "vitest";
import RecipientPicker from "@/components/email/RecipientPicker";
import { conversationOf } from "./email.helper";

const OPTIONS = conversationOf().recipientOptions;

describe("RecipientPicker", () => {
  it("shows every option with its label and the ticked ones ticked", () => {
    render(
      <RecipientPicker
        options={OPTIONS}
        selected={["alice@x.com"]}
        onChange={vi.fn()}
      />,
    );
    expect(screen.getByRole("group", { name: "To" })).toBeInTheDocument();
    expect(
      screen.getByRole("checkbox", { name: /^alice@x\.com\s*\(Primary contact\)$/ }),
    ).toBeChecked();
    expect(
      screen.getByRole("checkbox", {
        name: /^alice\.alt@y\.org\s*\(Alternative\)$/,
      }),
    ).not.toBeChecked();
  });

  it("emits the ticked addresses in option order", async () => {
    const onChange = vi.fn();
    render(
      <RecipientPicker
        options={OPTIONS}
        selected={["alice.alt@y.org"]}
        onChange={onChange}
      />,
    );
    await userEvent.click(
      screen.getByRole("checkbox", { name: /alice@x\.com/ }),
    );
    expect(onChange).toHaveBeenCalledWith(["alice@x.com", "alice.alt@y.org"]);
  });

  it("drops an address when it is unticked", async () => {
    const onChange = vi.fn();
    render(
      <RecipientPicker
        options={OPTIONS}
        selected={["alice@x.com", "alice.alt@y.org"]}
        onChange={onChange}
      />,
    );
    await userEvent.click(
      screen.getByRole("checkbox", { name: /alice\.alt@y\.org/ }),
    );
    expect(onChange).toHaveBeenCalledWith(["alice@x.com"]);
  });

  it("shows an option without a label as the bare address", () => {
    render(
      <RecipientPicker
        options={[{ address: "cand@x.com", label: null }]}
        selected={[]}
        onChange={vi.fn()}
      />,
    );
    expect(
      screen.getByRole("checkbox", { name: "cand@x.com" }),
    ).toBeInTheDocument();
  });

  it("says so when there is no address", () => {
    render(<RecipientPicker options={[]} selected={[]} onChange={vi.fn()} />);
    expect(screen.getByText("No email address on file.")).toBeInTheDocument();
    expect(screen.queryByRole("checkbox")).not.toBeInTheDocument();
  });
});
