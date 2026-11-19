import { describe, it, expect } from "vitest";
import { safeHttpUrl, safeLinkedinUrl } from "@/utils/url";

describe("safeHttpUrl", () => {
  it("returns https URLs unchanged", () => {
    expect(safeHttpUrl("https://linkedin.com/in/yuji")).toBe(
      "https://linkedin.com/in/yuji",
    );
  });

  it("returns http URLs unchanged", () => {
    expect(safeHttpUrl("http://example.com/path?q=1")).toBe(
      "http://example.com/path?q=1",
    );
  });

  it("prepends https:// when no scheme is present", () => {
    expect(safeHttpUrl("linkedin.com/in/yuji")).toBe(
      "https://linkedin.com/in/yuji",
    );
  });

  it("trims surrounding whitespace before parsing", () => {
    expect(safeHttpUrl("  https://example.com  ")).toBe("https://example.com");
  });

  it("rejects javascript: URLs", () => {
    expect(safeHttpUrl("javascript:alert(document.domain)")).toBeNull();
  });

  it("rejects javascript: URLs regardless of surrounding whitespace", () => {
    expect(safeHttpUrl("  javascript:alert(1)  ")).toBeNull();
  });

  it("rejects data: URLs", () => {
    expect(safeHttpUrl("data:text/html,<script>alert(1)</script>")).toBeNull();
  });

  it("rejects vbscript: URLs", () => {
    expect(safeHttpUrl("vbscript:msgbox(1)")).toBeNull();
  });

  it("rejects mailto: and other non-http schemes", () => {
    expect(safeHttpUrl("mailto:a@b.com")).toBeNull();
  });

  it("rejects empty, whitespace-only, null, and non-string input", () => {
    expect(safeHttpUrl("")).toBeNull();
    expect(safeHttpUrl("   ")).toBeNull();
    expect(safeHttpUrl(null)).toBeNull();
    expect(safeHttpUrl(undefined)).toBeNull();
    expect(safeHttpUrl(42)).toBeNull();
  });

  it("rejects a scheme-only string with no host", () => {
    expect(safeHttpUrl("https://")).toBeNull();
  });
});

describe("safeLinkedinUrl", () => {
  it("keeps https LinkedIn links and upgrades bare ones", () => {
    expect(safeLinkedinUrl("https://www.linkedin.com/in/ann")).toBe(
      "https://www.linkedin.com/in/ann",
    );
    expect(safeLinkedinUrl(" linkedin.com/in/ann ")).toBe(
      "https://linkedin.com/in/ann",
    );
  });

  it("rejects script URLs that mention linkedin.com", () => {
    expect(safeLinkedinUrl("javascript:alert(1)//linkedin.com")).toBeNull();
  });

  it("rejects other and lookalike hosts", () => {
    expect(safeLinkedinUrl("https://github.com/ann")).toBeNull();
    expect(
      safeLinkedinUrl("https://linkedin.com.evil.example/in/ann"),
    ).toBeNull();
    expect(safeLinkedinUrl("https://evil.example/linkedin.com")).toBeNull();
  });
});
