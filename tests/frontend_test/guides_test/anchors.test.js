import { describe, test, expect, afterEach } from "vitest";

import { anchorExists, visibleIndices, waitForAnchors } from "@/guides/anchors";

const addAnchor = (name) => {
  const element = document.createElement("span");
  element.dataset.tour = name;
  document.body.appendChild(element);
  return element;
};

describe("anchors", () => {
  afterEach(() => {
    document.body.innerHTML = "";
  });

  test("anchorExists looks for the data-tour attribute", () => {
    addAnchor("present");

    expect(anchorExists("present")).toBe(true);
    expect(anchorExists("absent")).toBe(false);
  });

  describe("visibleIndices", () => {
    test("lists the steps whose anchors are on the page", () => {
      addAnchor("b");
      addAnchor("d");

      expect(
        visibleIndices([
          { anchor: "a" },
          { anchor: "b" },
          { anchor: "c" },
          { anchor: "d" },
        ]),
      ).toEqual([1, 3]);
    });

    test("counts one variant of a step even when two are present", () => {
      addAnchor("variant-b");
      addAnchor("variant-c");
      addAnchor("after");

      expect(
        visibleIndices([
          { anchor: "variant-a", alternative: "partner" },
          { anchor: "variant-b", alternative: "partner" },
          { anchor: "variant-c", alternative: "partner" },
          { anchor: "after" },
        ]),
      ).toEqual([1, 3]);
    });
  });

  describe("waitForAnchors", () => {
    const STEPS = [{ anchor: "one" }, { anchor: "two" }];

    test("resolves at once when enough anchors are present", async () => {
      addAnchor("two");

      await expect(waitForAnchors(STEPS, 1, 1000)).resolves.toEqual([1]);
    });

    test("resolves once the missing anchors render", async () => {
      addAnchor("one");
      const waiting = waitForAnchors(STEPS, 2, 5000);
      setTimeout(() => addAnchor("two"), 20);

      await expect(waiting).resolves.toEqual([0, 1]);
    });

    test("resolves null when the anchors never render", async () => {
      addAnchor("one");

      await expect(waitForAnchors(STEPS, 2, 30)).resolves.toBeNull();
    });

    test("resolves null at once when there are too few steps", async () => {
      await expect(
        waitForAnchors([{ anchor: "one" }], 2, 60000),
      ).resolves.toBeNull();
    });
  });
});
