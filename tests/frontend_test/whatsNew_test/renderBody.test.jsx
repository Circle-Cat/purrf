import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { renderBody } from "@/whatsNew/renderBody";

describe("renderBody", () => {
  it("bolds each **span** and keeps the text around it", () => {
    const { container } = render(
      <p>{renderBody("Open **Emails & sign-in** and **Add email** now.")}</p>,
    );

    const bold = container.querySelectorAll("strong");
    expect([...bold].map((el) => el.textContent)).toEqual([
      "Emails & sign-in",
      "Add email",
    ]);
    expect(container.textContent).toBe(
      "Open Emails & sign-in and Add email now.",
    );
  });

  it("leaves a body without markers unchanged", () => {
    render(<p>{renderBody("Plain body, no bold.")}</p>);

    expect(screen.getByText("Plain body, no bold.")).toBeTruthy();
  });
});
