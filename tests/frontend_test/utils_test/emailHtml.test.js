import { describe, expect, it } from "vitest";
import {
  EMAIL_ALLOWED_TAGS,
  EMAIL_BODY_BOX_CLASS,
  sanitizeEmailBody,
  sanitizeEmailHtml,
} from "@/utils/emailHtml";

describe("sanitizeEmailBody", () => {
  it("drops style tags so a message cannot restyle the page", () => {
    const { html } = sanitizeEmailBody(
      "<style>.sidebar{display:none}</style><p>Hi</p>",
    );
    expect(html).toBe("<p>Hi</p>");
  });

  it("keeps formatting and inline styles of the message itself", () => {
    const { html } = sanitizeEmailBody(
      '<p style="color: red"><b>Bold</b> <a href="https://x.test">link</a></p>',
    );
    expect(html).toContain('style="color: red"');
    expect(html).toContain("<b>Bold</b>");
    expect(html).toContain('href="https://x.test"');
  });

  it("still removes scripts and event handlers", () => {
    const { html } = sanitizeEmailBody(
      '<script>alert(1)</script><img src="x" onerror="alert(1)">',
    );
    expect(html).not.toContain("script");
    expect(html).not.toContain("onerror");
  });

  it("reports nothing blocked for a message with no remote content", () => {
    const result = sanitizeEmailBody(
      '<p>Hi <a href="https://x.test">link</a></p><img src="data:image/png;base64,AAAA">',
    );
    expect(result.remoteContentBlocked).toBe(false);
    expect(result.html).toContain('src="data:image/png;base64,AAAA"');
  });

  // Each of these makes the browser fetch from the sender's server the moment
  // the message is shown, which tells them it was opened, when and from where.
  it.each([
    ["an image", '<img src="https://t.test/open.gif">'],
    ["a protocol-relative image", '<img src="//t.test/open.gif">'],
    ["a responsive image", '<img srcset="https://t.test/a.gif 1x, b.gif 2x">'],
    [
      "a table background",
      '<table><tr><td background="https://t.test/bg.gif">x</td></tr></table>',
    ],
    ["a video poster", '<video poster="https://t.test/p.gif"></video>'],
    [
      "an inline background",
      '<div style="background: url(https://t.test/bg.gif) no-repeat">x</div>',
    ],
    [
      "a quoted inline background",
      "<div style=\"background-image: url('//t.test/bg.gif')\">x</div>",
    ],
    ["an svg image", '<svg><image href="https://t.test/i.gif"></image></svg>'],
    [
      "an svg image by xlink",
      '<svg><image xlink:href="https://t.test/i.gif"></image></svg>',
    ],
  ])("blocks %s by default", (_, body) => {
    const result = sanitizeEmailBody(body);
    expect(result.html).not.toContain("t.test");
  });

  it("says when it blocked something", () => {
    expect(
      sanitizeEmailBody('<img src="https://t.test/open.gif">')
        .remoteContentBlocked,
    ).toBe(true);
  });

  it("keeps the rest of an inline style when it drops a remote background", () => {
    const { html } = sanitizeEmailBody(
      '<div style="color: red; background: url(https://t.test/bg.gif)">x</div>',
    );
    expect(html).toContain("color: red");
    expect(html).not.toContain("t.test");
  });

  it("loads remote content once the reader asks for it", () => {
    const result = sanitizeEmailBody(
      '<img src="https://t.test/open.gif"><div style="background: url(https://t.test/bg.gif)">x</div>',
      { loadRemoteContent: true },
    );
    expect(result.html).toContain('src="https://t.test/open.gif"');
    expect(result.html).toContain("url(https://t.test/bg.gif)");
    expect(result.remoteContentBlocked).toBe(false);
  });

  it("leaves no hook behind to affect a later sanitize", () => {
    sanitizeEmailBody('<img src="https://t.test/open.gif">');
    const { html } = sanitizeEmailBody('<img src="https://t.test/open.gif">', {
      loadRemoteContent: true,
    });
    expect(html).toContain("t.test");
  });

  it("points a cid image at the part it names, without asking", () => {
    const result = sanitizeEmailBody(
      '<img src="cid:ii_1"><img src="CID:logo%40x"><img src="https://t.test/open.gif">',
      {
        inlineImageUrl: (id) =>
          ({
            ii_1: "https://api.test/a/0",
            "logo@x": "https://api.test/a/1",
          })[id],
      },
    );
    expect(result.html).toContain('src="https://api.test/a/0"');
    expect(result.html).toContain('src="https://api.test/a/1"');
    expect(result.html).not.toContain("t.test");
    expect(result.remoteContentBlocked).toBe(true);
  });

  it("leaves a cid image it cannot match as it was", () => {
    const result = sanitizeEmailBody('<img src="cid:gone">', {
      inlineImageUrl: () => null,
    });
    expect(result.html).toContain('src="cid:gone"');
    expect(result.remoteContentBlocked).toBe(false);
  });

  it("resolves cid images after the reader loads remote content too", () => {
    const { html } = sanitizeEmailBody('<img src="cid:ii_1">', {
      loadRemoteContent: true,
      inlineImageUrl: () => "/api/a/0",
    });
    expect(html).toContain('src="/api/a/0"');
  });
});

describe("EMAIL_BODY_BOX_CLASS", () => {
  it("contains and clips what the message paints", () => {
    expect(EMAIL_BODY_BOX_CLASS).toContain("[contain:paint]");
    expect(EMAIL_BODY_BOX_CLASS).toContain("overflow-hidden");
  });
});

describe("sanitizeEmailHtml", () => {
  it("is exactly the recruiting whitelist", () => {
    expect(EMAIL_ALLOWED_TAGS).toEqual([
      "p",
      "br",
      "b",
      "strong",
      "i",
      "em",
      "u",
      "ul",
      "ol",
      "li",
      "a",
    ]);
  });

  it("keeps the whitelisted tags and a working link", () => {
    const html =
      '<p>Hi <b>A</b> <a href="https://x.test" target="_blank" rel="noopener">l</a></p>';
    expect(sanitizeEmailHtml(html)).toBe(html);
  });

  it("drops everything else but keeps its text", () => {
    expect(
      sanitizeEmailHtml(
        '<p style="color:red" onclick="x()">Hi<img src="x"><span>there</span><script>bad()</script></p>',
      ),
    ).toBe("<p>Hithere</p>");
  });

  it("drops javascript links", () => {
    expect(sanitizeEmailHtml('<a href="javascript:alert(1)">x</a>')).toBe(
      "<a>x</a>",
    );
  });
});
