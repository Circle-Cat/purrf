import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Group } from "@/constants/Groups";
import { LdapStatus } from "@/constants/LdapStatus";
import { getLdapsAndDisplayNames } from "@/api/dashboardApi";
import "@/components/common/MemberSelector.css";
import "@/pages/DataSearch.css";

function MsModal({ open, onClose, children }) {
  if (!open) return null;
  return (
    <div className="ds-modal-backdrop" onClick={onClose} role="presentation">
      <div
        className="ds-modal"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
      >
        {children}
      </div>
    </div>
  );
}

const UI_GROUPS = [Group.Employees, Group.Interns, Group.Volunteers];
const GROUP_LOOKUP = new Map(
  Object.values(Group).map((v) => [String(v).toLowerCase(), v]),
);
const STATUS_LOOKUP = new Map(
  Object.values(LdapStatus).map((v) => [String(v).toLowerCase(), v]),
);
function normalizeStatusLabel(k) {
  const key = String(k ?? "")
    .trim()
    .toLowerCase();
  return STATUS_LOOKUP.get(key) ?? null;
}

const _memberCache = {
  /** @type {Map<string, Member[]>} key = groupsKey */
  activeByKey: new Map(),
  /** @type {Map<string, Member[]>} key = groupsKey */
  allByKey: new Map(),
};

/** Normalize backend group label to UI constants (defensive). */
function normalizeGroupLabel(k) {
  const key = String(k ?? "")
    .trim()
    .toLowerCase();
  if (!key) return null;
  const exact = GROUP_LOOKUP.get(key);
  return exact ?? null;
}

const coerceDict = (resp) => resp?.data ?? resp;

/**
 * @typedef {Object} Member
 * @property {string} id
 * @property {string} ldap
 * @property {string} fullName
 * @property {Group[keyof Group]} group
 * @property {boolean} terminated
 */

/**
 * Flatten backend dict to Member[].
 * Shape:
 * {
 *   "<group>": {
 *     "<status>": { "<ldap>": "<displayName>", ... }
 *   }
 * }
 *
 * - Unknown groups are ignored.
 * - Unknown statuses are ignored.
 * - Terminated filtering uses LdapStatus.Terminated (exact, case-insensitive).
 *
 * @param {Record<string, any>} dict
 * @param {boolean} includeTerminated
 * @returns {Member[]}
 */
function flattenLdapsDict(dict, includeTerminated) {
  if (!dict || typeof dict !== "object") return [];

  const out = [];
  for (const [groupKey, byStatus] of Object.entries(dict)) {
    if (!byStatus || typeof byStatus !== "object") continue;

    const uiGroup = normalizeGroupLabel(groupKey);
    if (!uiGroup) continue;

    for (const [statusKey, ldapMap] of Object.entries(byStatus)) {
      const status = normalizeStatusLabel(statusKey);
      if (!status) continue;

      const isTerminated = status === LdapStatus.Terminated;
      if (isTerminated && !includeTerminated) continue;

      if (!ldapMap || typeof ldapMap !== "object") continue;

      for (const [ldap, displayName] of Object.entries(ldapMap)) {
        const id = String(ldap ?? "");
        if (!id) continue;

        out.push({
          id,
          ldap: id,
          fullName: displayName != null ? String(displayName) : "",
          group: uiGroup,
          terminated: isTerminated,
        });
      }
    }
  }
  return out;
}

export function MemberSelectorPanel({
  isOpen = true,
  selectedIds,
  onSelectedChange,
  onConfirm,
  onCancel,
  groups = UI_GROUPS,
}) {
  const [query, setQuery] = useState("");
  const [includeTerminated, setIncludeTerminated] = useState(false);

  const resolvedGroups = useMemo(
    () => (Array.isArray(groups) && groups.length ? groups : UI_GROUPS),
    [groups],
  );

  const groupsKey = useMemo(() => {
    const normalized = (
      Array.isArray(resolvedGroups) ? resolvedGroups : UI_GROUPS
    )
      .map(normalizeGroupLabel)
      .filter(Boolean)
      .sort();
    return normalized.join(",");
  }, [resolvedGroups]);

  const [activeList, setActiveList] = useState(
    /** @type {Member[]|null} */ (
      _memberCache.activeByKey.get(groupsKey) ?? null
    ),
  );
  const [allList, setAllList] = useState(
    /** @type {Member[]|null} */ (_memberCache.allByKey.get(groupsKey) ?? null),
  );

  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState(null);

  const isControlled = Array.isArray(selectedIds);
  const [internalSelected, setInternalSelected] = useState(
    () => new Set(selectedIds ?? []),
  );
  useEffect(() => {
    if (isControlled) setInternalSelected(new Set(selectedIds));
  }, [isControlled, selectedIds]);

  const selectedSet = isControlled ? new Set(selectedIds) : internalSelected;
  const setSelectedSet = (next) => {
    const source = includeTerminated
      ? (allList ?? _memberCache.allByKey.get(groupsKey) ?? [])
      : (activeList ?? _memberCache.activeByKey.get(groupsKey) ?? []);
    if (onSelectedChange) {
      const selectedMembers = source.filter((m) => next.has(m.id));
      onSelectedChange(Array.from(next), selectedMembers);
    }
    if (!isControlled) setInternalSelected(next);
  };

  const inflight = useRef(0);
  const startLoading = () => {
    inflight.current += 1;
    if (inflight.current > 0) setLoading(true);
  };
  const stopLoading = () => {
    inflight.current = Math.max(0, inflight.current - 1);
    if (inflight.current === 0) setLoading(false);
  };

  const fetchAndCacheMembers = useCallback(
    async ({ status, includeTerminatedFlag, setList }) => {
      const cacheMap =
        status === LdapStatus.Active
          ? _memberCache.activeByKey
          : _memberCache.allByKey;

      const cached = cacheMap.get(groupsKey);
      if (cached) {
        setList(cached);
        return;
      }

      startLoading();
      setErr(null);
      try {
        const resp = await getLdapsAndDisplayNames({
          status,
          groups: resolvedGroups,
        });
        const flat = flattenLdapsDict(coerceDict(resp), includeTerminatedFlag);
        cacheMap.set(groupsKey, flat);
        setList(flat);
      } catch (e) {
        setErr(e);
        setList([]);
      } finally {
        stopLoading();
      }
    },
    [groupsKey, resolvedGroups],
  );

  useEffect(() => {
    if (!isOpen) return;

    fetchAndCacheMembers({
      status: LdapStatus.Active,
      includeTerminatedFlag: false,
      setList: setActiveList,
    });

    if (includeTerminated) {
      fetchAndCacheMembers({
        status: LdapStatus.All,
        includeTerminatedFlag: true,
        setList: setAllList,
      });
    }
  }, [isOpen, includeTerminated, fetchAndCacheMembers]);

  // choose base list per toggle
  const base = useMemo(() => {
    const list = includeTerminated
      ? (allList ?? _memberCache.allByKey.get(groupsKey) ?? [])
      : (activeList ?? _memberCache.activeByKey.get(groupsKey) ?? []);
    return list;
  }, [includeTerminated, allList, activeList, groupsKey]);

  // local search
  const filteredMembers = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return base;
    return base.filter(
      (m) =>
        (m.ldap || "").toLowerCase().includes(q) ||
        (m.fullName || "").toLowerCase().includes(q),
    );
  }, [base, query]);

  const groupsMap = useMemo(() => {
    /** @type {Record<string, Member[]>} */
    const byGroup = {
      [Group.Employees]: [],
      [Group.Interns]: [],
      [Group.Volunteers]: [],
    };
    for (const m of filteredMembers) {
      const label = UI_GROUPS.includes(m.group)
        ? m.group
        : normalizeGroupLabel(m.group);
      if (!byGroup[label]) byGroup[label] = [];
      byGroup[label].push(m);
    }
    const allowed = new Set(
      resolvedGroups.map(normalizeGroupLabel).filter(Boolean),
    );
    const limited = {};
    for (const g of UI_GROUPS)
      if (allowed.has(g)) limited[g] = byGroup[g] ?? [];
    return limited;
  }, [filteredMembers, resolvedGroups]);

  // selection helpers
  const toggleMember = (id) => {
    const next = new Set(selectedSet);
    next.has(id) ? next.delete(id) : next.add(id);
    setSelectedSet(next);
  };

  const setGroupSelection = (groupName, checkAll) => {
    const next = new Set(selectedSet);
    const list = groupsMap[groupName] || [];
    for (const m of list) checkAll ? next.add(m.id) : next.delete(m.id);
    setSelectedSet(next);
  };

  const getGroupState = (groupName) => {
    const list = groupsMap[groupName] || [];
    if (list.length === 0) return "unchecked";
    const n = list.reduce((acc, m) => acc + (selectedSet.has(m.id) ? 1 : 0), 0);
    if (n === 0) return "unchecked";
    if (n === list.length) return "checked";
    return "indeterminate";
  };

  const handleConfirm = () => onConfirm?.(Array.from(selectedSet));
  const totalSelected = selectedSet.size;

  return (
    <div className="ms-panel">
      {/* Header */}
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

      {/* Status */}
      <div className="ms-status" role="status" aria-live="polite">
        {loading
          ? "Loading members…"
          : err
            ? `Failed to load members${
                import.meta.env.MODE !== "production"
                  ? `: ${String(err?.message || err)}`
                  : "."
              }`
            : null}
      </div>

      {/* List */}
      <div className="ms-list">
        {UI_GROUPS.filter((g) => groupsMap[g]).map((groupName, gi, arr) => {
          const list = groupsMap[groupName] || [];
          const state = getGroupState(groupName);
          const selectedCount = list.reduce(
            (n, m) => n + +selectedSet.has(m.id),
            0,
          );

          return (
            <div key={groupName} className="ms-section">
              {/* Group row */}
              <button
                type="button"
                className="ms-row ms-row-group"
                onClick={() =>
                  setGroupSelection(groupName, state !== "checked")
                }
                role="checkbox"
                aria-checked={
                  state === "checked"
                    ? true
                    : state === "indeterminate"
                      ? "mixed"
                      : false
                }
                aria-label={`${groupName} (${selectedCount}/${list.length})`}
              >
                <CheckCircle
                  state={state === "checked" ? "checked" : "unchecked"}
                />
                <div className="ms-text">
                  <div className="ms-label-main">
                    {groupName} ({selectedCount}/{list.length})
                  </div>
                </div>
              </button>

              {/* Members */}
              {list.length > 0 ? (
                list.map((m) => (
                  <button
                    key={m.id}
                    type="button"
                    className="ms-row"
                    onClick={() => toggleMember(m.id)}
                    role="checkbox"
                    aria-checked={selectedSet.has(m.id)}
                    aria-label={`${m.fullName || m.ldap}${m.terminated ? " (terminated)" : ""}`}
                  >
                    <CheckCircle
                      state={selectedSet.has(m.id) ? "checked" : "unchecked"}
                    />
                    <div className="ms-text">
                      <div className="ms-label-main">
                        <strong>{m.fullName}</strong>
                      </div>
                      <div className="ms-sub">
                        {m.ldap}
                        {m.terminated && (
                          <span className="ms-chip">terminated</span>
                        )}
                      </div>
                    </div>
                  </button>
                ))
              ) : (
                <div className="ms-empty">No matches</div>
              )}

              {/* Divider */}
              {gi < arr.length - 1 && <div className="ms-divider" />}
            </div>
          );
        })}
      </div>

      {/* Footer */}
      <div className="ms-footer">
        <button className="ms-btn-flat" onClick={() => onCancel?.()}>
          Cancel
        </button>
        <div className="ms-spacer" />
        <div className="ms-count">{totalSelected} selected</div>
        <button className="ms-btn-primary" onClick={handleConfirm}>
          OK
        </button>
      </div>
    </div>
  );
}

/** Small visual state dot */
function CheckCircle({ state }) {
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

/**
 * MemberSelector (Modal)
 *
 * A ready-to-use modal wrapper around MemberSelectorPanel.
 * Pages pass `open`, `onClose`, and controlled selection props.
 *
 * Props:
 * - open: boolean
 * - onClose: () => void
 * - title?: string (default "Select Members")
 * - selectedIds?: string[]
 * - onSelectedChange?: (ids: string[], members: Member[]) => void
 * - onConfirm?: (ids: string[], members: Member[]) => void
 * - onCancel?: () => void
 * - groups?: Group[]
 */
export default function MemberSelector({
  open,
  onClose,
  title = "Select Members",
  selectedIds,
  onSelectedChange,
  onConfirm,
  onCancel,
  groups,
}) {
  return (
    <MsModal open={open} onClose={onClose}>
      <div className="ds-modal-header">
        <h3 style={{ margin: 0 }}>{title}</h3>
      </div>
      <div className="ds-modal-body">
        <MemberSelectorPanel
          isOpen={open}
          selectedIds={selectedIds}
          onSelectedChange={onSelectedChange}
          onConfirm={(ids, members) => {
            onConfirm?.(ids, members);
            onClose?.();
          }}
          onCancel={() => {
            onCancel?.();
            onClose?.();
          }}
          groups={groups}
        />
      </div>
    </MsModal>
  );
}
