import { describe, test, expect, afterEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import EnvironmentBanner from "@/components/layout/EnvironmentBanner";

import "@testing-library/jest-dom/vitest";

describe("EnvironmentBanner Component", () => {
  afterEach(() => {
    cleanup();
  });

  test("renders staging banner with the staging variant and label", () => {
    render(<EnvironmentBanner env="staging" />);
    const banner = screen.getByTestId("env-banner");
    expect(banner).toHaveTextContent("STAGING ENVIRONMENT");
    expect(banner).toHaveAttribute("data-variant", "staging");
    expect(banner).toHaveAttribute("role", "status");
  });

  test("renders test banner with the test variant and label", () => {
    render(<EnvironmentBanner env="test" />);
    const banner = screen.getByTestId("env-banner");
    expect(banner).toHaveTextContent("TEST ENVIRONMENT");
    expect(banner).toHaveAttribute("data-variant", "test");
  });

  test.each([["prod"], [""], [undefined], ["preview"], ["dev"]])(
    "renders nothing for env=%p",
    (env) => {
      const { container } = render(<EnvironmentBanner env={env} />);
      expect(container).toBeEmptyDOMElement();
      expect(screen.queryByTestId("env-banner")).toBeNull();
    },
  );
});
