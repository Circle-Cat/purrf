import { render, screen, cleanup } from "@testing-library/react";
import { describe, test, expect, afterEach } from "vitest";
import Card from "@/components/common/Card";

import "@testing-library/jest-dom/vitest";

describe("Card", () => {
  const mockTitle = "Total Users";
  const mockValue = "1,234";
  const mockNumericValue = 5678;

  afterEach(cleanup);

  test("renders card correctly with title, value and main class", () => {
    render(<Card title={mockTitle} value={mockValue} />);

    const cardElement = screen.getByTestId("card");
    const titleElement = screen.getByText(mockTitle);
    const valueElement = screen.getByText(mockValue);

    expect(cardElement).toHaveClass("card");
    expect(titleElement).toBeInTheDocument();
    expect(titleElement).toHaveClass("card-title");
    expect(valueElement).toHaveClass("card-value");
  });

  test("handles numeric values", () => {
    render(<Card title={mockTitle} value={mockNumericValue} />);

    const valueElement = screen.getByText(mockNumericValue.toString());

    expect(valueElement).toBeInTheDocument();
    expect(valueElement).toHaveClass("card-value");
  });
});
