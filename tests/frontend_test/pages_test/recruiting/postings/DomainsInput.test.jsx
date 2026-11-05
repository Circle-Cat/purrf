import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import DomainsInput from "@/pages/Recruiting/postings/DomainsInput";

/**
 * Stateful wrapper so onChange feeds the next value back in — mirroring how
 * ScreenRulesEditor owns the rule's condition. A purely controlled render
 * would swallow every second tag.
 */
function Controlled({ initial = [], onChange }) {
  const [value, setValue] = useState(initial);
  return (
    <DomainsInput
      value={value}
      onChange={(next) => {
        setValue(next);
        onChange?.(next);
      }}
    />
  );
}

const input = () => screen.getByLabelText("Email domains");
const tags = () =>
  screen
    .queryAllByRole("button", { name: /^Remove / })
    .map((b) => b.getAttribute("aria-label").replace("Remove ", ""));

describe("DomainsInput", () => {
  it("turns the typed text into a tag on Enter", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<Controlled onChange={onChange} />);

    await user.type(input(), "google.com{Enter}");

    expect(tags()).toEqual(["google.com"]);
    expect(input()).toHaveValue("");
    expect(onChange).toHaveBeenLastCalledWith(["google.com"]);
  });

  it("commits the typed text when a comma is typed instead of inserting it", async () => {
    // The bug this component replaces: the old single-string field round-tripped
    // through split(",")/join(", ") on every keystroke, so a trailing comma was
    // erased in the same frame and a second domain could never be typed.
    const user = userEvent.setup();
    render(<Controlled />);

    await user.type(input(), "a.com,b.com,");

    expect(tags()).toEqual(["a.com", "b.com"]);
    expect(input()).toHaveValue("");
  });

  it("commits the typed text when the Add button is clicked", async () => {
    const user = userEvent.setup();
    render(<Controlled />);

    await user.type(input(), "google.com");
    await user.click(screen.getByRole("button", { name: "Add domain" }));

    expect(tags()).toEqual(["google.com"]);
  });

  it("commits the typed text on blur so a click straight to Save keeps it", async () => {
    // Clicking Save blurs the focused input before the click lands, so blur is
    // what saves a recruiter who typed a domain and never pressed Enter.
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<Controlled onChange={onChange} />);

    await user.type(input(), "google.com");
    fireEvent.blur(input());

    expect(tags()).toEqual(["google.com"]);
    expect(onChange).toHaveBeenLastCalledWith(["google.com"]);
  });

  it("does not commit on a typed space", async () => {
    // Whitespace splits pasted text only. Typing a space must not commit,
    // otherwise every fat-fingered space becomes a bogus tag.
    const user = userEvent.setup();
    render(<Controlled />);

    await user.type(input(), "goo gle");

    expect(tags()).toEqual([]);
    expect(input()).toHaveValue("goo gle");
  });

  it("splits pasted text on commas and whitespace", () => {
    render(<Controlled />);

    fireEvent.paste(input(), {
      clipboardData: { getData: () => "a.com, b.com  c.com" },
    });

    expect(tags()).toEqual(["a.com", "b.com", "c.com"]);
    expect(input()).toHaveValue("");
  });

  it("keeps the first invalid segment of a paste in the box and reports it", () => {
    render(<Controlled />);

    fireEvent.paste(input(), {
      clipboardData: { getData: () => "a.com, @bad, b.com" },
    });

    expect(tags()).toEqual(["a.com", "b.com"]);
    expect(input()).toHaveValue("@bad");
    expect(screen.getByRole("alert")).toHaveTextContent(
      "Enter a domain like google.com",
    );
  });

  it("lowercases a domain before storing it", async () => {
    // screen_rules.py lowercases the candidate's email domain before comparing,
    // so a stored "Google.COM" would silently never match.
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<Controlled onChange={onChange} />);

    await user.type(input(), "Google.COM{Enter}");

    expect(tags()).toEqual(["google.com"]);
    expect(onChange).toHaveBeenLastCalledWith(["google.com"]);
  });

  it.each([
    ["localhost", "no dot"],
    ["@google.com", "leading at-sign"],
    ["https://google.com", "protocol prefix"],
    ["-google.com", "label starting with a hyphen"],
    ["google-.com", "label ending with a hyphen"],
  ])("rejects %s (%s)", async (bad) => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<Controlled onChange={onChange} />);

    await user.type(input(), `${bad}{Enter}`);

    expect(tags()).toEqual([]);
    expect(input()).toHaveValue(bad);
    expect(screen.getByRole("alert")).toHaveTextContent(
      "Enter a domain like google.com",
    );
    expect(onChange).not.toHaveBeenCalled();
  });

  it("rejects a duplicate and keeps the text for editing", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<Controlled initial={["google.com"]} onChange={onChange} />);

    await user.type(input(), "google.com{Enter}");

    expect(tags()).toEqual(["google.com"]);
    expect(input()).toHaveValue("google.com");
    expect(screen.getByRole("alert")).toHaveTextContent("Already added");
    expect(onChange).not.toHaveBeenCalled();
  });

  it("clears the error once the text is edited", async () => {
    const user = userEvent.setup();
    render(<Controlled />);

    await user.type(input(), "localhost{Enter}");
    expect(screen.getByRole("alert")).toBeInTheDocument();

    await user.type(input(), ".com");

    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("removes the clicked tag and leaves the rest in order", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(
      <Controlled initial={["a.com", "b.com", "c.com"]} onChange={onChange} />,
    );

    await user.click(screen.getByRole("button", { name: "Remove b.com" }));

    expect(tags()).toEqual(["a.com", "c.com"]);
    expect(onChange).toHaveBeenLastCalledWith(["a.com", "c.com"]);
  });

  it("removes the right tag when a pending domain is committed by the same click", async () => {
    // The × button's click is preceded by the input's blur, which commits the
    // pending domain and shifts every later index. Removal keys on the domain
    // value for exactly this reason.
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<Controlled initial={["a.com", "b.com"]} onChange={onChange} />);

    await user.type(input(), "z.com");
    await user.click(screen.getByRole("button", { name: "Remove a.com" }));

    expect(tags()).toEqual(["b.com", "z.com"]);
  });

  it("renders one tag per supplied value", () => {
    render(
      <DomainsInput
        value={["google.com", "circlecat.org"]}
        onChange={vi.fn()}
      />,
    );

    expect(tags()).toEqual(["google.com", "circlecat.org"]);
  });
});
