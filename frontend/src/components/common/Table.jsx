import { ChevronUp, ChevronDown, ChevronsUpDown } from "lucide-react";

/**
 * Table Component
 *
 * A reusable table component that supports sortable columns and displays tabular data.
 *
 * @component
 *
 * @param {Object} props
 * @param {Array<{ header: string, accessor: string, sortable?: boolean }>} props.columns - Array of column definitions.
 *        Each column can optionally be sortable.
 * @param {Array<Object>} props.data - Array of row data objects. Each object should have keys matching the column accessors.
 * @param {function} [props.onSort] - Optional callback triggered when a sortable column header is clicked. Receives the column accessor as argument.
 * @param {string} [props.sortColumn] - Optional accessor of the currently sorted column.
 * @param {"asc" | "desc"} [props.sortDirection] - Optional sort direction for the sorted column ("asc" or "desc").
 *
 * @example
 * const columns = [
 *   { header: "Name", accessor: "name", sortable: true },
 *   { header: "Age", accessor: "age", sortable: true }
 * ];
 * const data = [
 *   { name: "Alice", age: 25 },
 *   { name: "Bob", age: 30 }
 * ];
 *
 * <Table
 *   columns={columns}
 *   data={data}
 *   onSort={(accessor) => console.log("Sort by", accessor)}
 *   sortColumn="age"
 *   sortDirection="asc"
 * />
 */
const Table = ({ columns, data, onSort, sortColumn, sortDirection }) => {
  return (
    <div className="overflow-auto rounded-lg border">
      <table className="w-full min-w-fit border-collapse text-sm leading-normal [&_tbody_tr:hover]:bg-muted [&_tbody_tr:nth-child(even)]:bg-muted [&_td]:whitespace-nowrap [&_td]:border-b [&_td]:px-[15px] [&_td]:py-3 [&_td]:text-left [&_th]:sticky [&_th]:top-0 [&_th]:z-[1] [&_th]:whitespace-nowrap [&_th]:border-b [&_th]:bg-muted [&_th]:py-3 [&_th]:pl-[15px] [&_th]:pr-[25px] [&_th]:text-left [&_th]:font-bold [&_th]:text-foreground">
        <thead>
          <tr>
            {columns.map((col, index) => {
              const isSorted = sortColumn === col.accessor;
              return (
                <th
                  key={index}
                  className={
                    col.sortable ? "cursor-pointer select-none" : undefined
                  }
                  aria-sort={
                    isSorted
                      ? sortDirection === "asc"
                        ? "ascending"
                        : "descending"
                      : col.sortable
                        ? "none"
                        : undefined
                  }
                  onClick={() => col.sortable && onSort && onSort(col.accessor)}
                >
                  {col.header}
                  {col.sortable &&
                    (isSorted ? (
                      sortDirection === "asc" ? (
                        <ChevronUp className="ml-1 inline size-3.5 align-middle text-foreground" />
                      ) : (
                        <ChevronDown className="ml-1 inline size-3.5 align-middle text-foreground" />
                      )
                    ) : (
                      <ChevronsUpDown className="ml-1 inline size-3.5 align-middle text-gray-400" />
                    ))}
                </th>
              );
            })}
          </tr>
        </thead>
        <tbody>
          {data.length > 0 ? (
            data.map((row, rowIndex) => (
              <tr key={rowIndex}>
                {columns.map((col, colIndex) => (
                  <td key={colIndex}>{row[col.accessor]}</td>
                ))}
              </tr>
            ))
          ) : (
            <tr>
              <td colSpan={columns.length} style={{ textAlign: "center" }}>
                N/A
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
};

export default Table;
