import { describe, it, expect, beforeEach } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import Tab from "@/components/common/Tab.jsx";

const TAB_LABELS = ["Chat", "Jira", "Gerrit", "Calendar"];
const HEADERS = {
  0: ["LDAP", "CHAT SPACE", "COUNT"],
  1: ["LDAP", "PROJECT", "STATUS"],
  2: ["LDAP", "PROJECT", "CL COUNT"],
  3: ["LDAP", "CALENDAR", "ATTENDANCE"],
};
const EMPTY_ROWS = 8;

describe("Tab (inline SVG version)", () => {
  beforeEach(() => {
    render(<Tab />);
  });

  it("renders the component and all four tabs with labels", () => {
    expect(screen.getByTestId("tab-component")).toBeInTheDocument();

    TAB_LABELS.forEach((label, i) => {
      const btn = screen.getByTestId(`tab-button-${i}`);
      expect(btn).toBeInTheDocument();
      expect(btn).toHaveTextContent(label);
    });

    expect(screen.getByTestId("tab-button-0")).toHaveAttribute(
      "aria-selected",
      "true",
    );
    expect(screen.getByTestId("tab-panel-0")).toBeVisible();
  });

  it("renders an icon (svg) next to each tab label", () => {
    for (let i = 0; i < 4; i++) {
      const btn = screen.getByTestId(`tab-button-${i}`);
      const svgs = btn.querySelectorAll("svg");
      expect(svgs.length).toBe(1);
    }
  });

  it("active tab shows a table with correct headers and 8 empty rows", () => {
    const panel = screen.getByTestId("tab-panel-0");
    expect(panel).toBeVisible();

    const table = within(panel).getByTestId("tab-table-0");
    expect(table).toBeInTheDocument();

    HEADERS[0].forEach((h) => {
      expect(
        within(table).getByRole("columnheader", { name: h }),
      ).toBeInTheDocument();
    });

    const emptyCells = within(table).getAllByLabelText("empty-cell");
    expect(emptyCells.length).toBe(EMPTY_ROWS * HEADERS[0].length);
  });

  it("switches tabs correctly, toggling visibility and headers", async () => {
    const user = userEvent.setup();

    for (let i = 0; i < 4; i++) {
      const btn = screen.getByTestId(`tab-button-${i}`);
      await user.click(btn);

      expect(btn).toHaveAttribute("aria-selected", "true");

      for (let j = 0; j < 4; j++) {
        const panel = screen.getByTestId(`tab-panel-${j}`);
        if (j === i) {
          expect(panel).toBeVisible();
        } else {
          expect(panel).not.toBeVisible();
        }
      }

      const activePanel = screen.getByTestId(`tab-panel-${i}`);
      const table = within(activePanel).getByTestId(`tab-table-${i}`);
      expect(table).toBeInTheDocument();

      HEADERS[i].forEach((h) => {
        expect(
          within(table).getByRole("columnheader", { name: h }),
        ).toBeInTheDocument();
      });

      const emptyCells = within(table).getAllByLabelText("empty-cell");
      expect(emptyCells.length).toBe(EMPTY_ROWS * HEADERS[i].length);
    }
  });

  it("each tab has a table element when active", async () => {
    const user = userEvent.setup();
    for (let i = 0; i < 4; i++) {
      await user.click(screen.getByTestId(`tab-button-${i}`));
      const panel = screen.getByTestId(`tab-panel-${i}`);
      expect(panel).toBeVisible();
      expect(within(panel).getByTestId(`tab-table-${i}`)).toBeInTheDocument();
    }
  });
});
