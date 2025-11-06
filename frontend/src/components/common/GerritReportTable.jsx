import { useEffect, useMemo, useState, useCallback } from "react";
import { getGerritStats } from "@/api/dataSearchApi";
import "@/components/common/GerritReportTable.css";
import Table from "@/components/common/Table";

const COLUMNS = [
  { header: "LDAP", accessor: "ldap", sortable: true },
  { header: "CL MERGED", accessor: "cl_merged", sortable: true },
  { header: "LOC MERGED", accessor: "loc_merged", sortable: true },
  { header: "CL REVIEWED", accessor: "cl_reviewed", sortable: true },
  {
    header: "CL UNDER REVIEW (TODAY)",
    accessor: "cl_under_review",
    sortable: true,
  },
  { header: "CL ABANDONED", accessor: "cl_abandoned", sortable: true },
];

const toRows = (dict = {}) =>
  Object.entries(dict).map(([ldap, v]) => ({
    ldap,
    cl_merged: Number(v?.cl_merged ?? 0),
    cl_under_review:
      v?.cl_under_review == null ? "N/A" : Number(v?.cl_under_review),
    loc_merged: Number(v?.loc_merged ?? 0),
    cl_abandoned: Number(v?.cl_abandoned ?? 0),
    cl_reviewed: Number(v?.cl_reviewed ?? 0),
  }));

/**
 * GerritReportTable
 *
 * React component to fetch and display Gerrit stats in a sortable table.
 *
 * ### Behavior
 * - Fetches Gerrit stats only when:
 *   - `startDate` and `endDate` are both provided, AND
 *   - `ldaps` array is non-empty.
 * - Converts the backend response (dict keyed by LDAP) into an array of row objects.
 * - Supports sorting by clicking on table headers.
 * - Displays loading/error/empty states consistently.
 *
 *  * @component
 * @param {Object} props - Component props
 * @param {Object} props.gerritReportProps - Wrapper object for Gerrit report parameters.
 * @param {Object} props.gerritReportProps.searchParams - Search parameters for fetching Gerrit stats.
 * @param {Array<string>} props.gerritReportProps.searchParams.
 *  - ldaps - Array of LDAP user identifiers.
 * - startDate - Start date (YYYY-MM-DD).
 * - endDate - End date (YYYY-MM-DD).
 * - project - Optional Gerrit project filter.
 *
 * @returns {JSX.Element} Rendered Gerrit stats table or status message.
 */
export default function GerritReportTable({ gerritReportProps }) {
  const sp = gerritReportProps?.searchParams ?? {};
  const { ldaps = [], startDate, endDate, project, includeAllProjects } = sp;

  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [sort, setSort] = useState({ key: null, direction: "asc" });

  useEffect(() => {
    let alive = true;

    const hasDates = !!(startDate && endDate);
    const hasLdaps = Array.isArray(ldaps) && ldaps.length > 0;

    if (!hasDates || !hasLdaps) {
      setRows([]);
      setError(null);
      setLoading(false);
      return () => {
        alive = false;
      };
    }

    (async () => {
      setLoading(true);
      setError(null);
      try {
        const resp = await getGerritStats({
          ldaps,
          startDate,
          endDate,
          project,
          includeAllProjects,
        });
        if (!alive) return;
        setRows(toRows(resp?.data));
      } catch (e) {
        if (!alive) return;
        setError(
          e?.response?.data?.message ||
            e?.message ||
            "Failed to fetch Gerrit stats",
        );
      } finally {
        if (alive) setLoading(false);
      }
    })();

    return () => {
      alive = false;
    };
  }, [startDate, endDate, project, ldaps, includeAllProjects]);

  const handleSort = useCallback((key) => {
    setSort((prev) => ({
      key,
      direction: prev.key === key && prev.direction === "asc" ? "desc" : "asc",
    }));
  }, []);

  const sortedRows = useMemo(() => {
    if (!sort.key) return rows;
    const dir = sort.direction === "asc" ? 1 : -1;
    return [...rows].sort((a, b) => {
      const av = a[sort.key];
      const bv = b[sort.key];

      if (typeof av === "number" && typeof bv === "number") {
        if (av === bv) return 0;
        return (av < bv ? -1 : 1) * dir;
      }
      const sa = String(av ?? "").toLowerCase();
      const sb = String(bv ?? "").toLowerCase();
      if (sa === sb) return 0;
      return (sa < sb ? -1 : 1) * dir;
    });
  }, [rows, sort]);

  const displayRows = useMemo(
    () =>
      sortedRows.map((r) => ({
        ...r,
        cl_merged: r.cl_merged.toLocaleString(),
        cl_under_review: r.cl_under_review.toLocaleString(),
        loc_merged: r.loc_merged.toLocaleString(),
        cl_abandoned: r.cl_abandoned.toLocaleString(),
        cl_reviewed: r.cl_reviewed.toLocaleString(),
      })),
    [sortedRows],
  );

  if (loading) return <div className="loading">Loading Gerrit stats…</div>;
  if (error) return <div className="error">{error}</div>;
  if (!rows.length) return <div className="no-data">No data.</div>;

  return (
    <Table
      columns={COLUMNS}
      data={displayRows}
      onSort={handleSort}
      sortColumn={sort.key}
      sortDirection={sort.direction}
    />
  );
}
