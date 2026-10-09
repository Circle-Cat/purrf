import { describe, expect, it } from "vitest";
import { EMAIL_BODY_BOX_CLASS, sanitizeEmailBody } from "@/utils/emailHtml";

describe("sanitizeEmailBody", () => {
  it("drops style tags so a message cannot restyle the page", () => {
    const html = sanitizeEmailBody(
      "<style>.sidebar{display:none}</style><p>Hi</p>",
    );
    expect(html).toBe("<p>Hi</p>");
  });

  it("keeps formatting and inline styles of the message itself", () => {
    const html = sanitizeEmailBody(
      '<p style="color: red"><b>Bold</b> <a href="https://x.test">link</a></p>',
    );
    expect(html).toContain('style="color: red"');
    expect(html).toContain("<b>Bold</b>");
    expect(html).toContain('href="https://x.test"');
  });

  it("still removes scripts and event handlers", () => {
    const html = sanitizeEmailBody(
      '<script>alert(1)</script><img src="x" onerror="alert(1)">',
    );
    expect(html).not.toContain("script");
    expect(html).not.toContain("onerror");
  });
});

describe("EMAIL_BODY_BOX_CLASS", () => {
  it("contains and clips what the message paints", () => {
    expect(EMAIL_BODY_BOX_CLASS).toContain("[contain:paint]");
    expect(EMAIL_BODY_BOX_CLASS).toContain("overflow-hidden");
  });
});
