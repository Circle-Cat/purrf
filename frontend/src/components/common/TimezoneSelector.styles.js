/**
 * Default react-select styles for TimezoneSelector.
 *
 * To partially override individual style keys while preserving the default look:
 *
 * @example
 * styles={{
 *   ...defaultTimezoneSelectStyles,
 *   control: (base) => ({
 *     ...defaultTimezoneSelectStyles.control(base),
 *     borderRadius: "4px",
 *   }),
 * }}
 */
export const defaultTimezoneSelectStyles = {
  menuPortal: (base) => ({ ...base, zIndex: 202, pointerEvents: "auto" }),
  menu: (base) => ({
    ...base,
    zIndex: 202,
    backgroundColor: "var(--popover)",
    borderRadius: "var(--radius)",
    border: "1px solid var(--border)",
    padding: "0.25rem",
    overflow: "hidden",
  }),
  menuList: (base) => ({ ...base, padding: 0 }),
  control: (base) => ({
    ...base,
    border: "none",
    backgroundColor: "var(--color-gray-50)",
    borderRadius: "0.5rem",
    boxShadow: "none",
    cursor: "pointer",
  }),
  indicatorSeparator: () => ({ display: "none" }),
  dropdownIndicator: (base) => ({
    ...base,
    padding: "0 8px",
    color: "var(--muted-foreground)",
  }),
  option: (base, state) => ({
    ...base,
    fontSize: "0.875rem",
    backgroundColor: state.isFocused ? "var(--accent)" : "transparent",
    color: state.isFocused ? "var(--accent-foreground)" : "inherit",
    borderRadius: "calc(var(--radius) - 2px)",
    padding: "0.25rem 0.375rem",
    cursor: "default",
    // Prevent react-select from flashing the default primary blue on mousedown.
    ":active": {
      backgroundColor: state.isFocused ? "var(--accent)" : "transparent",
    },
  }),
};
