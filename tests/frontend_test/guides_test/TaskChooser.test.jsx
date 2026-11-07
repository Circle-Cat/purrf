import { describe, test, expect, afterEach, vi } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import "@testing-library/jest-dom/vitest";

import TaskChooser from "@/guides/TaskChooser";

const TASKS = [
  { key: "task-alpha", title: "Do alpha", completed: false },
  { key: "task-beta", title: "Do beta", completed: true },
];

describe("TaskChooser", () => {
  afterEach(() => {
    cleanup();
  });

  test("offers each task and marks the completed ones", () => {
    render(<TaskChooser tasks={TASKS} onChoose={vi.fn()} onClose={vi.fn()} />);

    expect(
      screen.getByRole("dialog", { name: "What would you like to do?" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Do alpha" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Do beta (completed)" }),
    ).toBeInTheDocument();
  });

  test("reports the task picked", async () => {
    const onChoose = vi.fn();
    render(<TaskChooser tasks={TASKS} onChoose={onChoose} onClose={vi.fn()} />);

    await userEvent.click(screen.getByRole("button", { name: "Do alpha" }));

    expect(onChoose).toHaveBeenCalledWith("task-alpha");
  });

  test("reports exploring alone", async () => {
    const onClose = vi.fn();
    const onExplore = vi.fn();
    render(
      <TaskChooser
        tasks={TASKS}
        onChoose={vi.fn()}
        onClose={onClose}
        onExplore={onExplore}
      />,
    );

    await userEvent.click(
      screen.getByRole("button", { name: "I'll explore on my own" }),
    );

    expect(onExplore).toHaveBeenCalledTimes(1);
    expect(onClose).not.toHaveBeenCalled();
  });

  test("reports being closed", async () => {
    const onClose = vi.fn();
    const onExplore = vi.fn();
    render(
      <TaskChooser
        tasks={TASKS}
        onChoose={vi.fn()}
        onClose={onClose}
        onExplore={onExplore}
      />,
    );

    await userEvent.click(screen.getByRole("button", { name: "Close" }));

    expect(onClose).toHaveBeenCalledTimes(1);
    expect(onExplore).not.toHaveBeenCalled();
  });
});
