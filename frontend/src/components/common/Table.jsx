import "@/components/common/Table.css";

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
    <div className="table-container">
      <table className="custom-table">
        <thead>
          <tr>
            {columns.map((col, index) => (
              <th
                key={index}
                className={`${col.sortable ? "sortable" : ""} ${sortColumn === col.accessor ? (sortDirection === "asc" ? "sorted-asc" : "sorted-desc") : ""}`}
                onClick={() => col.sortable && onSort && onSort(col.accessor)}
              >
                {col.header}
                {col.sortable && <span className="sort-indicator"></span>}
              </th>
            ))}
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
