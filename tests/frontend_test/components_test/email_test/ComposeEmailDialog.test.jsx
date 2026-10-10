import {
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi } from "vitest";
import ComposeEmailDialog from "@/components/email/ComposeEmailDialog";
import { conversationOf, replyOf, threadOf } from "./email.helper";

const props = (overrides = {}) => ({
  open: true,
  onOpenChange: vi.fn(),
  mode: "text",
  recipientOptions: conversationOf().recipientOptions,
  defaultTo: "alice@x.com",
  senderAddress: "mentorship@circlecat.org",
  maxBodyLength: 10000,
  formatTime: (iso) => `at ${iso}`,
  onSend: vi.fn().mockResolvedValue(undefined),
  sending: false,
  ...overrides,
});

const message = () => screen.getByRole("textbox", { name: "Message" });
const sendButton = () => screen.getByRole("button", { name: "Send" });

describe("ComposeEmailDialog", () => {
  it("ticks the default address and sends to every ticked one", async () => {
    const p = props();
    const user = userEvent.setup();
    render(<ComposeEmailDialog {...p} />);

    expect(
      screen.getByText("From: mentorship@circlecat.org"),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("checkbox", { name: /alice@x\.com/ }),
    ).toBeChecked();
    expect(
      screen.getByRole("checkbox", { name: /alice\.alt@y\.org/ }),
    ).not.toBeChecked();
    await user.click(
      screen.getByRole("checkbox", { name: /alice\.alt@y\.org/ }),
    );
    await user.type(screen.getByLabelText("Subject"), "Checking in");
    await user.type(message(), "How is it going?");
    await user.click(sendButton());

    expect(p.onSend).toHaveBeenCalledWith({
      to: ["alice@x.com", "alice.alt@y.org"],
      subject: "Checking in",
      body: "How is it going?",
      threadId: null,
    });
    await waitFor(() => expect(p.onOpenChange).toHaveBeenCalledWith(false));
  });

  it("ticks the default address whatever its case", () => {
    render(<ComposeEmailDialog {...props({ defaultTo: "Alice@X.com" })} />);
    expect(
      screen.getByRole("checkbox", { name: /alice@x\.com/ }),
    ).toBeChecked();
  });

  it("keeps Send disabled with no recipient ticked", async () => {
    const user = userEvent.setup();
    render(<ComposeEmailDialog {...props()} />);
    await user.type(screen.getByLabelText("Subject"), "Hi");
    await user.type(message(), "Body");
    expect(sendButton()).toBeEnabled();
    await user.click(screen.getByRole("checkbox", { name: /alice@x\.com/ }));
    expect(sendButton()).toBeDisabled();
  });

  it("sends a plain-text body exactly as typed", async () => {
    const p = props();
    const user = userEvent.setup();
    render(<ComposeEmailDialog {...p} />);
    await user.type(screen.getByLabelText("Subject"), "Hi");
    await user.type(message(), "a < b <b>not bold</b>");
    await user.click(sendButton());
    expect(p.onSend.mock.calls[0][0].body).toBe("a < b <b>not bold</b>");
  });

  it("refuses a body over the limit", async () => {
    const user = userEvent.setup();
    render(<ComposeEmailDialog {...props()} />);
    await user.type(screen.getByLabelText("Subject"), "Hi");
    expect(message()).toHaveAttribute("maxlength", "10000");
    fireEvent.change(message(), { target: { value: "x".repeat(10001) } });
    expect(screen.getByText("10001 / 10000")).toBeInTheDocument();
    expect(sendButton()).toBeDisabled();
  });

  it("offers no template in text mode and never loads any", () => {
    const loadTemplates = vi.fn();
    render(<ComposeEmailDialog {...props({ loadTemplates })} />);
    expect(
      screen.queryByRole("combobox", { name: /template/i }),
    ).not.toBeInTheDocument();
    expect(loadTemplates).not.toHaveBeenCalled();
  });

  it("replies to the fixed address under the thread subject", async () => {
    const p = props({ replyThread: threadOf({ replyTo: "alice.alt@y.org" }) });
    const user = userEvent.setup();
    render(<ComposeEmailDialog {...p} />);

    const dialog = screen.getByRole("dialog", { name: "Reply" });
    expect(within(dialog).queryByRole("checkbox")).not.toBeInTheDocument();
    expect(within(dialog).getByText("alice.alt@y.org")).toBeInTheDocument();
    const subject = within(dialog).getByLabelText("Subject");
    expect(subject).toHaveValue("Re: Checking in");
    expect(subject).toHaveAttribute("readonly");
    await user.type(message(), "Thanks");
    await user.click(sendButton());

    expect(p.onSend).toHaveBeenCalledWith({
      to: ["alice.alt@y.org"],
      subject: "Re: Checking in",
      body: "Thanks",
      threadId: 41,
    });
  });

  it.each(["text", "rich"])(
    "caps the subject at the backend limit (%s)",
    (mode) => {
      render(<ComposeEmailDialog {...props({ mode })} />);
      expect(screen.getByLabelText("Subject")).toHaveAttribute(
        "maxlength",
        "990",
      );
    },
  );

  it("shows Unknown and refuses to send a reply with no reply address", async () => {
    const p = props({ replyThread: threadOf({ replyTo: null }) });
    const user = userEvent.setup();
    render(<ComposeEmailDialog {...p} />);

    const dialog = screen.getByRole("dialog", { name: "Reply" });
    expect(within(dialog).getByText("Unknown")).toBeInTheDocument();
    expect(within(dialog).queryByText("alice@x.com")).not.toBeInTheDocument();
    await user.type(message(), "Thanks");
    expect(sendButton()).toBeDisabled();
  });

  it("keeps the draft when the conversation reloads under an open reply", async () => {
    const p = props({ replyThread: threadOf() });
    const user = userEvent.setup();
    const { rerender } = render(<ComposeEmailDialog {...p} />);
    await user.type(message(), "My draft");

    const newer = replyOf({
      messageId: 412,
      bodyHtml: "<p>One more thing</p>",
      bodyText: "One more thing",
    });
    rerender(
      <ComposeEmailDialog
        {...p}
        replyThread={threadOf({
          messages: [...threadOf().messages, newer],
        })}
        staleMessages={[newer]}
      />,
    );

    expect(message()).toHaveValue("My draft");
    expect(screen.getByRole("status")).toHaveTextContent(
      "Not sent: this thread has new messages since you opened it.",
    );
    expect(
      within(screen.getByRole("list", { name: "New messages" })).getByText(
        "One more thing",
      ),
    ).toBeInTheDocument();
  });

  it("keeps the dialog and the draft when sending fails", async () => {
    const p = props({ onSend: vi.fn().mockRejectedValue(new Error("down")) });
    const user = userEvent.setup();
    render(<ComposeEmailDialog {...p} />);
    await user.type(screen.getByLabelText("Subject"), "Hi");
    await user.type(message(), "Body");
    await user.click(sendButton());
    await waitFor(() => expect(p.onSend).toHaveBeenCalled());
    expect(p.onOpenChange).not.toHaveBeenCalledWith(false);
    expect(message()).toHaveValue("Body");
  });

  it("shows a notice about the person", () => {
    render(
      <ComposeEmailDialog
        {...props({
          notice: "Alice Chen is blocked from Purrf. The email is still sent.",
        })}
      />,
    );
    expect(
      screen.getByText(
        "Alice Chen is blocked from Purrf. The email is still sent.",
      ),
    ).toBeInTheDocument();
  });

  it("loads templates once per open, whatever function the parent passes next", async () => {
    const first = vi
      .fn()
      .mockResolvedValue({ templates: [], signatureHtml: "" });
    const base = props({ mode: "rich", loadTemplates: first });
    const { rerender } = render(<ComposeEmailDialog {...base} />);
    await waitFor(() => expect(first).toHaveBeenCalledTimes(1));

    const second = vi
      .fn()
      .mockResolvedValue({ templates: [], signatureHtml: "" });
    rerender(<ComposeEmailDialog {...base} loadTemplates={second} />);
    rerender(<ComposeEmailDialog {...base} loadTemplates={second} sending />);

    expect(first).toHaveBeenCalledTimes(1);
    expect(second).not.toHaveBeenCalled();
  });
});
