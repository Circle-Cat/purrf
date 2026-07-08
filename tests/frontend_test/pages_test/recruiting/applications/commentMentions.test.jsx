import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import {
  getActiveMentionQuery,
  insertMention,
  renderCommentBody,
} from "@/pages/Recruiting/applications/commentMentions";

describe("getActiveMentionQuery", () => {
  it("finds an in-progress @query ending at the cursor", () => {
    expect(getActiveMentionQuery("Hey @Ev", 7)).toEqual({
      start: 4,
      query: "Ev",
    });
  });

  it("returns null when there is no @ before the cursor", () => {
    expect(getActiveMentionQuery("Hey there", 9)).toBeNull();
  });

  it("returns null once a space ends the run after the @", () => {
    expect(getActiveMentionQuery("Hey @Eve check this", 19)).toBeNull();
  });

  it("does not match inside an already-inserted @[id] token", () => {
    expect(getActiveMentionQuery("Hey @[42] there", 9)).toBeNull();
  });

  it("matches an empty query right after a bare @", () => {
    expect(getActiveMentionQuery("Hey @", 5)).toEqual({ start: 4, query: "" });
  });
});

describe("insertMention", () => {
  it("replaces the @query span with a token and trailing space", () => {
    const result = insertMention("Hey @Ev", 4, 7, 42);
    expect(result.text).toBe("Hey @[42] ");
    expect(result.cursorPos).toBe(10);
  });

  it("preserves text after the cursor", () => {
    const result = insertMention("Hey @Ev, can you look?", 4, 7, 42);
    expect(result.text).toBe("Hey @[42] , can you look?");
  });
});

describe("renderCommentBody", () => {
  it("returns the plain body unchanged when there is no mention token", () => {
    const nodes = renderCommentBody("Just a comment.", []);
    expect(nodes.join("")).toBe("Just a comment.");
  });

  it("substitutes a resolved mention token with a highlighted name", () => {
    render(
      <p>
        {renderCommentBody("Hey @[42] check this", [
          { userId: 42, name: "Eve Evaluator" },
        ])}
      </p>,
    );
    expect(screen.getByText("@Eve Evaluator")).toBeInTheDocument();
    expect(screen.getByText(/Hey/)).toBeInTheDocument();
    expect(screen.getByText(/check this/)).toBeInTheDocument();
  });

  it("drops a token with no matching entry in mentions rather than crash", () => {
    render(<p>{renderCommentBody("Hey @[42] check this", [])}</p>);
    expect(screen.queryByText(/@\[42\]/)).not.toBeInTheDocument();
    expect(screen.getByText(/Hey/)).toBeInTheDocument();
  });
});
