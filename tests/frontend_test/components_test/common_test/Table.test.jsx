import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import { describe, it, expect, vi, afterEach } from "vitest";
import Table from "@/components/common/Table";

import "@testing-library/jest-dom/vitest";

describe("Table Component", () => {
  const mockColumns = [
    { header: "Name", accessor: "name", sortable: true },
    { header: "Age", accessor: "age", sortable: true },
    { header: "Location", accessor: "location", sortable: false },
  ];

  const mockData = [
    { name: "Yuji", age: 28, location: "Tokyo" },
    { name: "Mei", age: 32, location: "Kyoto" },
  ];

  afterEach(cleanup);

  it("should render the table headers and data correctly", () => {
    render(<Table columns={mockColumns} data={mockData} />);

    mockColumns.forEach((col) => {
      expect(screen.getByText(col.header)).toBeInTheDocument();
    });

    expect(screen.getByText("Yuji")).toBeInTheDocument();
    expect(screen.getByText("28")).toBeInTheDocument();
    expect(screen.getByText("Tokyo")).toBeInTheDocument();

    expect(screen.getByText("Mei")).toBeInTheDocument();
    expect(screen.getByText("32")).toBeInTheDocument();
    expect(screen.getByText("Kyoto")).toBeInTheDocument();
  });

  it("should display 'N/A' when there is no data", () => {
    render(<Table columns={mockColumns} data={[]} />);

    const noDataCell = screen.getByText("N/A");
    expect(noDataCell).toBeInTheDocument();
    expect(noDataCell).toHaveAttribute("colSpan", `${mockColumns.length}`);
    expect(noDataCell).toHaveStyle({ textAlign: "center" });
  });

  it("should call onSort when a sortable column header is clicked", () => {
    const onSortMock = vi.fn();
    render(<Table columns={mockColumns} data={mockData} onSort={onSortMock} />);

    const nameHeader = screen.getByText("Name");
    fireEvent.click(nameHeader);

    expect(onSortMock).toHaveBeenCalledTimes(1);
    expect(onSortMock).toHaveBeenCalledWith("name");
  });

  it("should not call onSort when a non-sortable column header is clicked", () => {
    const onSortMock = vi.fn();
    render(<Table columns={mockColumns} data={mockData} onSort={onSortMock} />);

    const locationHeader = screen.getByText("Location");
    fireEvent.click(locationHeader);

    expect(onSortMock).not.toHaveBeenCalled();
  });

  it("should not call onSort if the onSort prop is not provided", () => {
    render(<Table columns={mockColumns} data={mockData} />);

    const ageHeader = screen.getByText("Age");

    expect(() => fireEvent.click(ageHeader)).not.toThrow();
  });

  it("should apply ascending sort styles correctly", () => {
    render(
      <Table
        columns={mockColumns}
        data={mockData}
        sortColumn="name"
        sortDirection="asc"
      />,
    );

    const nameHeader = screen.getByText("Name");
    expect(nameHeader).toHaveClass("sortable", "sorted-asc");
  });

  it("should apply descending sort styles correctly", () => {
    render(
      <Table
        columns={mockColumns}
        data={mockData}
        sortColumn="age"
        sortDirection="desc"
      />,
    );

    const ageHeader = screen.getByText("Age");
    expect(ageHeader).toHaveClass("sortable", "sorted-desc");
  });
});
