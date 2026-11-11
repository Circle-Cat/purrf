import { describe, test, expect, beforeEach, afterEach, vi } from "vitest";
import { highlightAnchor } from "@/whatsNew/highlightAnchor";

describe("highlightAnchor", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
    document.body.innerHTML = "";
  });

  const addTarget = (anchor) => {
    const element = document.createElement("button");
    element.dataset.whatsNew = anchor;
    element.style.outline = "1px dotted red";
    element.scrollIntoView = vi.fn();
    document.body.appendChild(element);
    return element;
  };

  test("waits for the element, scrolls it to the centre and outlines it for 3 s", () => {
    highlightAnchor("add-email");
    vi.advanceTimersByTime(1200);
    const element = addTarget("add-email");
    // A different anchor on the page must not be picked up.
    const other = addTarget("other-anchor");
    vi.advanceTimersByTime(100);

    expect(element.scrollIntoView).toHaveBeenCalledWith({
      behavior: "smooth",
      block: "center",
    });
    expect(element.style.outline).toBe("3px solid var(--primary)");
    expect(other.scrollIntoView).not.toHaveBeenCalled();

    vi.advanceTimersByTime(2999);
    expect(element.style.outline).toBe("3px solid var(--primary)");
    vi.advanceTimersByTime(1);
    expect(element.style.outline).toBe("1px dotted red");
    expect(element.style.outlineOffset).toBe("");
  });

  test("gives up after 5 s when the element never renders", () => {
    highlightAnchor("missing");
    vi.advanceTimersByTime(5000);
    expect(vi.getTimerCount()).toBe(0);

    const late = addTarget("missing");
    vi.advanceTimersByTime(1000);
    expect(late.scrollIntoView).not.toHaveBeenCalled();
  });

  test("cancelling removes the outline early", () => {
    const element = addTarget("add-email");
    const cancel = highlightAnchor("add-email");
    expect(element.style.outline).toBe("3px solid var(--primary)");

    cancel();

    expect(element.style.outline).toBe("1px dotted red");
    expect(vi.getTimerCount()).toBe(0);
  });
});
