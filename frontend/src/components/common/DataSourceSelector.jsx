import { useState } from "react";
import "./DataSourceSelector.css";

/**
 * TODO(API): Replace static DATA_SOURCES with a server call
 * (e.g., GET /api/sources -> { Chat: [...], Jira: [...], ... }).
 */
const DATA_SOURCES = {
  Chat: ["TGIF", "Tech Question"],
  Jira: ["Project A", "Project B"],
  Gerrit: ["Repo1", "Repo2"],
  Calendar: ["Meeting 1", "Meeting 2"],
};

/**
 * Converts a string into a URL/CSS-friendly "slug".
 *
 * Steps:
 * - Trims whitespace and lowercases the string.
 * - Replaces any sequence of non-alphanumeric characters with a single hyphen.
 * - Removes leading or trailing hyphens.
 *
 * Useful for generating stable keys or CSS class suffixes
 * from dynamic labels like project names or calendar events.
 *
 * Examples:
 *   slug(" Project A ")   // "project-a"
 *   slug("Repo 1!")       // "repo-1"
 *   slug("Meeting_2025")  // "meeting-2025"
 *
 * @param {string} s - The input string to normalize.
 * @returns {string} The normalized slug string.
 */

const slug = (s) =>
  String(s)
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/(^-|-$)/g, "");

/**
 * DataSourceSelector Component
 *
 * A UI component that allows users to select items from multiple
 * data sources (Chat, Jira, Gerrit, Calendar).
 *
 * Features:
 * - Sidebar navigation: Switch between data sources.
 * - Sidebar checkboxes: Select/deselect all items for a given source.
 * - Main panel: Displays items for the active source with checkboxes.
 * - "Select All" in main panel: Toggles all visible items.
 * - Confirm/Cancel buttons: Return selection or cancel interaction.
 *
 * Props:
 * @param {function(Object<string, string[]>):void} onConfirm - Callback invoked when "OK" is clicked.
 *        Receives an object mapping source names to arrays of selected item strings.
 *        Example: { Chat: ["TGIF"], Jira: [], Gerrit: ["Repo1"], Calendar: [] }.
 * @param {function():void} onCancel - Callback invoked when "Cancel" is clicked.
 *
 * State:
 * - activeSource {string}: The currently active data source tab (default: "Chat").
 * - selectedItems {Object<string, string[]>}: Tracks selected items per source.
 *
 * Accessibility:
 * - Sidebar items are keyboard-focusable (role="button", tabIndex=0).
 * - Each checkbox includes an aria-label for screen readers.
 */
export default function DataSourceSelector({ onConfirm, onCancel }) {
  const [activeSource, setActiveSource] = useState("Chat");
  const [selectedItems, setSelectedItems] = useState({});

  const items = DATA_SOURCES[activeSource] || [];
  const selected = selectedItems[activeSource] || [];
  const allChecked = items.length > 0 && selected.length === items.length;

  const toggleItem = (item) => {
    setSelectedItems((prev) => {
      const curr = new Set(prev[activeSource] || []);
      curr.has(item) ? curr.delete(item) : curr.add(item);
      return { ...prev, [activeSource]: [...curr] };
    });
  };

  const toggleAll = () => {
    setSelectedItems((prev) => ({
      ...prev,
      [activeSource]: allChecked ? [] : [...items],
    }));
  };

  const toggleSourceAll = (source) => {
    const all = DATA_SOURCES[source] ?? [];
    const curr = selectedItems[source] ?? [];
    const next = curr.length === all.length ? [] : [...all];
    setSelectedItems((prev) => ({ ...prev, [source]: next }));
  };

  return (
    <div className="dss-container">
      {/* Body: sidebar + main in a row */}
      <div className="dss-body">
        <aside className="dss-sidebar">
          {Object.keys(DATA_SOURCES).map((source) => {
            const all = DATA_SOURCES[source];
            const chosen = selectedItems[source] || [];
            const sourceAllChecked =
              all.length > 0 && chosen.length === all.length;

            return (
              <div
                key={source}
                className={`dss-sidebar-item ${slug(source)} ${
                  activeSource === source ? "active" : ""
                }`}
                onClick={() => setActiveSource(source)}
                role="button"
                tabIndex={0}
              >
                <input
                  type="checkbox"
                  checked={sourceAllChecked}
                  onChange={(e) => {
                    e.stopPropagation();
                    toggleSourceAll(source);
                  }}
                  aria-label={`Select all ${source}`}
                />
                <span>{source}</span>
              </div>
            );
          })}
        </aside>

        <main className="dss-main">
          <label className="dss-selectall">
            <input type="checkbox" checked={allChecked} onChange={toggleAll} />{" "}
            Select All
          </label>

          {items.map((item) => (
            <div key={item} className={`dss-item dss-item--${slug(item)}`}>
              <label>
                <input
                  type="checkbox"
                  checked={(selectedItems[activeSource] || []).includes(item)}
                  onChange={() => toggleItem(item)}
                />{" "}
                {item}
              </label>
            </div>
          ))}
        </main>
      </div>

      {/* Footer pinned to bottom */}
      <footer className="dss-footer">
        <button className="cancel-button" onClick={onCancel}>
          Cancel
        </button>
        <button className="ok-button" onClick={() => onConfirm(selectedItems)}>
          OK
        </button>
      </footer>
    </div>
  );
}
