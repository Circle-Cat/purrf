import { useMemo, useState } from "react";
import { Group } from "@/constants/Groups.jsx";

/**
 * MemberSelector Component
 *
 * A React component for selecting members grouped by category (Employees, Interns, Volunteers).
 * Provides search functionality, group-level select/deselect, and an option to include/exclude
 * terminated members. Designed to allow users to confirm or cancel their selections easily.
 *
 * Props:
 * @param {Array<Object>} members - The list of members to display and select from.
 *   Each member object should include:
 *     @property {string} id - Unique identifier for the member.
 *     @property {string} ldap - LDAP handle of the member.
 *     @property {string} fullName - Full name of the member.
 *     @property {string} group - Group the member belongs to (Employees, Interns, Volunteers).
 *     @property {boolean} terminated - Whether the member is terminated.
 *
 * @param {function} onConfirm - Callback triggered when the user clicks "OK".
 *   Receives an array of selected member IDs: Array<string>.
 *
 * @param {function} onCancel - Callback triggered when the user clicks "Cancel".
 *   No arguments are passed.
 *
 * Features:
 * - Search: Filters members by full name or LDAP handle.
 * - Group Selection: Each group (Employees, Interns, Volunteers) has a tri-state
 *   checkbox (checked, unchecked, indeterminate). Clicking selects/deselects all
 *   visible members in that group.
 * - Individual Selection: Toggle selection state for each member individually.
 * - Include Terminated Members: A toggle to show or hide terminated members
 *   in the selection list.
 * - Visual Feedback: Displays the count of selected members in the footer.
 * - Accessibility: Uses buttons and aria-hidden indicators for compatibility.
 *
 * Example Usage:
 * ```jsx
 * <MemberSelector
 *   members={[
 *     { id: "1", ldap: "jdoe", fullName: "John Doe", group: "Employees", terminated: false },
 *     { id: "2", ldap: "asmith", fullName: "Alice Smith", group: "Interns", terminated: false },
 *   ]}
 *   onConfirm={(ids) => console.log("Selected IDs:", ids)}
 *   onCancel={() => console.log("Cancelled")}
 * />
 * ```
 */

export default function MemberSelector({
  members = [], // [{ id, LDAP, fullName, group, terminated }]
  onConfirm,
  onCancel,
}) {
  const [query, setQuery] = useState("");
  const [includeTerminated, setIncludeTerminated] = useState(false);
  const [selected, setSelected] = useState(() => new Set());
  const GROUP_ORDER = [Group.Employees, Group.Interns, Group.Volunteers];

  // filter by terminated + search
  const filteredMembers = useMemo(() => {
    const q = query.trim().toLowerCase();
    return members.filter((m) => {
      if (!includeTerminated && m.terminated) return false;
      if (!q) return true;
      return (
        (m.ldap || "").toLowerCase().includes(q) ||
        (m.fullName || "").toLowerCase().includes(q)
      );
    });
  }, [members, includeTerminated, query]);

  // group members
  const groups = useMemo(() => {
    const byGroup = { Employees: [], Interns: [], Volunteers: [] };
    for (const m of filteredMembers) {
      if (!byGroup[m.group]) byGroup[m.group] = [];
      byGroup[m.group].push(m);
    }
    return byGroup;
  }, [filteredMembers]);

  // helpers
  const toggleMember = (id) => {
    setSelected((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  };

  const setGroupSelection = (groupName, checkAll) => {
    setSelected((prev) => {
      const next = new Set(prev);
      const list = groups[groupName] || [];
      for (const m of list) checkAll ? next.add(m.id) : next.delete(m.id);
      return next;
    });
  };

  const getGroupState = (groupName) => {
    const list = groups[groupName] || [];
    if (list.length === 0) return "unchecked";
    const checkedCount = list.reduce(
      (n, m) => n + (selected.has(m.id) ? 1 : 0),
      0,
    );
    if (checkedCount === 0) return "unchecked";
    if (checkedCount === list.length) return "checked";
    return "indeterminate";
  };

  const totalSelected = selected.size;

  return (
    <div className="ms-panel">
      {/* search + toggle */}
      <div className="ms-header-row">
        <div className="ms-searchbar">
          <span className="ms-search-ico" aria-hidden />
          <input
            className="ms-input"
            placeholder="Search by LDAP or full name"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </div>

        <label className="ms-toggle">
          <input
            type="checkbox"
            checked={includeTerminated}
            onChange={(e) => setIncludeTerminated(e.target.checked)}
          />
          <span>Include Terminated Members</span>
        </label>
      </div>

      {/* list */}
      <div className="ms-list">
        {GROUP_ORDER.map((groupName, gi) => {
          const list = groups[groupName] || [];
          const state = getGroupState(groupName);
          const selectedCount = list.filter((m) => selected.has(m.id)).length;

          return (
            <div key={groupName} className="ms-section">
              {/* group row */}
              <button
                type="button"
                className="ms-row ms-row-group"
                onClick={() =>
                  setGroupSelection(groupName, state !== "checked")
                }
              >
                <CheckCircle state={state} />
                <div className="ms-text">
                  <div className="ms-label-main">
                    {groupName} ({selectedCount}/{list.length})
                  </div>
                </div>
              </button>

              {/* members */}
              {list.length > 0 && (
                <>
                  {list.map((m) => (
                    <button
                      key={m.id}
                      type="button"
                      className="ms-row"
                      onClick={() => toggleMember(m.id)}
                    >
                      <CheckCircle
                        state={selected.has(m.id) ? "checked" : "unchecked"}
                      />
                      <div className="ms-text">
                        <div className="ms-label-main">{m.fullName}</div>
                        <div className="ms-sub">
                          {m.ldap}
                          {m.terminated && (
                            <span className="ms-chip">terminated</span>
                          )}
                        </div>
                      </div>
                    </button>
                  ))}
                </>
              )}

              {list.length === 0 && <div className="ms-empty">No matches</div>}

              {/* divider between sections */}
              {gi < GROUP_ORDER.length - 1 && <div className="ms-divider" />}
            </div>
          );
        })}
      </div>

      {/* footer */}
      <div className="ms-footer">
        <button className="ms-btn-flat" onClick={() => onCancel && onCancel()}>
          Cancel
        </button>
        <div className="ms-spacer" />
        <div className="ms-count">{totalSelected} selected</div>
        <button
          className="ms-btn-primary"
          onClick={() => onConfirm && onConfirm(Array.from(selected))}
        >
          OK
        </button>
      </div>
    </div>
  );
}

/* circular tri/bi-state indicator */
function CheckCircle({ state }) {
  // state: "checked" | "unchecked" | "indeterminate"
  return (
    <span
      className={
        state === "checked"
          ? "ms-check ms-check-on"
          : state === "indeterminate"
            ? "ms-check ms-check-mixed"
            : "ms-check"
      }
      aria-hidden
    />
  );
}
