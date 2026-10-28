import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect } from "vitest";
import EmailBody from "@/components/email/EmailBody";

const TRACKED =
  '<p>Hello</p><img alt="pixel" src="https://t.test/open.gif?id=abc">';

describe("EmailBody", () => {
  it("shows the plain text when there is no HTML", () => {
    render(<EmailBody html={null} text={"Line one\nLine two"} />);
    expect(screen.getByText(/Line one/)).toBeInTheDocument();
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });

  it("does not load a remote image until the reader asks", () => {
    const { container } = render(<EmailBody html={TRACKED} />);
    expect(screen.getByText("Hello")).toBeInTheDocument();
    expect(container.innerHTML).not.toContain("t.test");
    expect(screen.getByRole("status")).toHaveTextContent(
      "Images are hidden so the sender cannot tell this was opened.",
    );
  });

  it("loads remote images once Show images is clicked", async () => {
    const { container } = render(<EmailBody html={TRACKED} />);

    await userEvent.click(screen.getByRole("button", { name: "Show images" }));

    expect(container.querySelector("img").getAttribute("src")).toBe(
      "https://t.test/open.gif?id=abc",
    );
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });

  it("shows an image pasted into the message from its own attachment", () => {
    const { container } = render(
      <EmailBody
        html='<p>See</p><img alt="shot" src="cid:ii_2">'
        attachments={[{ contentId: null }, { contentId: "ii_2" }]}
        attachmentUrl={(index) => `https://api.test/attachments/${index}`}
      />,
    );
    expect(container.querySelector("img").getAttribute("src")).toBe(
      "https://api.test/attachments/1",
    );
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });

  it("says nothing when the message has no remote content", () => {
    render(<EmailBody html="<p>Hello</p>" />);
    expect(screen.getByText("Hello")).toBeInTheDocument();
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });
});
