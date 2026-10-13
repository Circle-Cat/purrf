import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi } from "vitest";
import EmailThreadCard from "@/components/email/EmailThreadCard";
import { messageOf, replyOf, threadOf } from "./email.helper";

const formatTime = (iso) => `at ${iso}`;

const renderCard = (props = {}) =>
  render(
    <ul>
      <li>
        <EmailThreadCard
          thread={threadOf()}
          formatTime={formatTime}
          {...props}
        />
      </li>
    </ul>,
  );

describe("EmailThreadCard", () => {
  it("shows each message with direction, sender, time, From and To", () => {
    renderCard();
    expect(screen.getByText("Checking in")).toBeInTheDocument();
    expect(screen.getByText("Sent")).toBeInTheDocument();
    expect(screen.getByText("Received")).toBeInTheDocument();
    expect(screen.getByText("by Dana Wu")).toBeInTheDocument();
    expect(screen.getByText("· at 2026-10-01T16:00:00Z")).toBeInTheDocument();
    expect(screen.getByText("· at 2026-10-02T17:30:00Z")).toBeInTheDocument();
    expect(screen.getAllByText("From")).toHaveLength(2);
    expect(screen.getByText("How is it going?")).toBeInTheDocument();
    expect(screen.getByText("All good, thanks")).toBeInTheDocument();
  });

  it("flags Needs reply and an open bounce", () => {
    renderCard({
      thread: threadOf({ openBounce: { bouncedTo: "alice.alt@y.org" } }),
    });
    expect(screen.getByText("Needs reply")).toBeInTheDocument();
    expect(screen.getByRole("alert")).toHaveTextContent(
      "Delivery failed: your email to alice.alt@y.org was not delivered",
    );
  });

  it("tags auto-replies and bounces", () => {
    renderCard({
      thread: threadOf({
        needsReply: false,
        messages: [
          replyOf({ inboundKind: "auto_reply" }),
          replyOf({ messageId: 412, inboundKind: null, failedRecipients: "" }),
        ],
      }),
    });
    expect(screen.getByText("Auto-reply")).toBeInTheDocument();
    expect(screen.getByText("Delivery failed")).toBeInTheDocument();
    expect(screen.queryByText("Needs reply")).not.toBeInTheDocument();
  });

  it("renders bodies through the display sanitizer, as recruiting does today", () => {
    renderCard({
      thread: threadOf({
        messages: [
          replyOf({
            bodyHtml:
              '<style>p{}</style><p style="color: red">Hi <b>there</b></p><table><tbody><tr><td>cell</td></tr></tbody></table><img src="x.png" onerror="x()"><script>bad()</script>',
          }),
        ],
      }),
    });
    const body = screen.getByText("cell").closest("[class*='contain']");
    expect(body.innerHTML).toBe(
      '<p style="color: red">Hi <b>there</b></p><table><tbody><tr><td>cell</td></tr></tbody></table><img src="x.png">',
    );
    expect(body.className).toContain("[&_p]:my-3");
  });

  it("falls back to the plain text body", () => {
    renderCard({
      thread: threadOf({
        messages: [replyOf({ bodyHtml: null, bodyText: "Plain words" })],
      }),
    });
    expect(screen.getByText("Plain words")).toBeInTheDocument();
  });

  it("links attachments to the download URL", () => {
    const attachmentUrl = vi.fn(
      (messageId, index) => `/dl/${messageId}/${index}`,
    );
    renderCard({
      attachmentUrl,
      thread: threadOf({
        messages: [
          replyOf({ attachments: [{ name: "plan.pdf", size: 2048 }] }),
        ],
      }),
    });
    const link = screen.getByRole("link", { name: /plan\.pdf/ });
    expect(link).toHaveAttribute("href", "/dl/411/0");
    expect(link).toHaveAttribute("download");
    expect(link).toHaveTextContent("2 KB");
    expect(attachmentUrl).toHaveBeenCalledWith(411, 0);
  });

  it("lists attachments by name without a download URL, and none when absent", () => {
    renderCard({
      thread: threadOf({
        messages: [
          replyOf({ attachments: [{ name: "plan.pdf", size: 2048 }] }),
          messageOf({ messageId: 413, attachments: undefined }),
        ],
      }),
    });
    expect(screen.getByText("plan.pdf")).toBeInTheDocument();
    expect(screen.queryByRole("link")).not.toBeInTheDocument();
    expect(screen.getAllByRole("list", { name: "Attachments" })).toHaveLength(
      1,
    );
  });

  it("offers Reply only when it can reply", async () => {
    const onReply = vi.fn();
    const { unmount } = renderCard({ onReply });
    expect(
      screen.queryByRole("button", { name: /^Reply/ }),
    ).not.toBeInTheDocument();
    unmount();

    renderCard({ canReply: true, onReply });
    await userEvent.click(
      screen.getByRole("button", { name: "Reply to Checking in" }),
    );
    expect(onReply).toHaveBeenCalledWith(threadOf());
  });

  it("keeps Reply but disabled and titled with a hint", () => {
    renderCard({ canReply: true, replyDisabledHint: "Needs the grant" });
    const reply = screen.getByRole("button", { name: "Reply to Checking in" });
    expect(reply).toBeDisabled();
    expect(reply).toHaveAttribute("title", "Needs the grant");
  });

  it("names Reply after a thread with no subject", () => {
    renderCard({ thread: threadOf({ subject: null }), canReply: true });
    expect(
      screen.getByRole("button", { name: "Reply to (no subject)" }),
    ).toBeInTheDocument();
  });
});
