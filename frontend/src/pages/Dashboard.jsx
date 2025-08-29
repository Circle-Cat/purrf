import { useState, useMemo, useEffect } from "react";
import "@/pages/Dashboard.css";
import { Group } from "@/constants/Groups";
import { LdapStatus } from "@/constants/LdapStatus";
import DateRangePicker from "@/components/common/DateRangePicker";
import Card from "@/components/common/Card";
import Table from "@/components/common/Table";
import { getSummary, getLdapsAndDisplayNames } from "@/api/dashboardApi";

/**
 * @typedef {Object} SummaryData
 * @property {number} totalMembers - The total number of members.
 * @property {number} totalCompletedTickets - The total count of completed Jira tickets.
 * @property {number} totalMergedCls - The total count of merged CLs (Gerrit Change Lists).
 * @property {number} totalMergedLoc - The total count of merged LOCs (Lines of Code).
 * @property {number} totalMeetingCount - The total count of Google meetings attended.
 * @property {number} totalMessagesSent - The total count of chat messages sent (Google Chat and Teams Chat).
 */

/**
 * @typedef {Object} TableMemberData
 * @property {string} ldap - The LDAP of the member.
 * @property {number} jiraTicketsDone - Number of Jira tickets completed.
 * @property {number} mergedCls - Number of CLs merged.
 * @property {number} mergedLoc - Number of LOCs merged.
 * @property {number} meetingCount - Number of meetings attended.
 * @property {number} chatMessagesSent - Number of chat messages sent.
 */

/**
 * Dashboard Component
 *
 * Provides a comprehensive overview of team activities and key metrics,
 * offering interactive filtering options. It fetches and displays summary data
 * and a detailed table of member-specific metrics.
 *
 * Features:
 * - Filter data by a selectable date range.
 * - Filter by team groups (Interns, Employees, Volunteers, etc.).
 * - Optionally include or exclude terminated members.
 * - Trigger data fetch with a search button.
 *
 * State:
 * - `selectedStartDate` (string): The start date of the range filter in `YYYY-MM-DD` format.
 * - `selectedEndDate` (string): The end date of the range filter in `YYYY-MM-DD` format.
 * - `groups` (Group[]): Currently selected team groups for filtering.
 * - `includeTerminated` (boolean): Whether terminated members are included in results.
 * - `summaryData` (SummaryData): The fetched summary data from the API.
 * - `tableData` (TableMemberData[]): The detailed member data for the table.
 *
 * Default Behavior:
 * - Date range defaults from the first day of the current month to today (in UTC, ignoring local timezone).
 * - Initial group selection defaults to `[Group.Interns]`.
 * - Initial `includeTerminated` state is set to `false`.
 * - `summaryData` is initialized with all-zero values.
 * - `tableData` is initialized as an empty array `[]`.
 *
 * Component Props:
 * - None.
 *
 * Handlers:
 * - `handleGroupChange(groupName: Group)`: Toggles selection of a group.
 * - `handleDateChange({ startDate, endDate }: { startDate: string; endDate: string })`: Updates selected date range.
 * - `handleSearch()`: Fetches summary data using current filters and updates state.
 *
 * Notes:
 * - The `getSummary` API is asynchronous and updates `summaryData` and `tableData` on success.
 * - Date values are managed in UTC to avoid timezone inconsistencies.
 *
 *
 * @component
 * @returns {JSX.Element} The rendered Dashboard page.
 */
const Dashboard = () => {
  const today = new Date();
  const todayUTC = new Date(
    Date.UTC(today.getUTCFullYear(), today.getUTCMonth(), today.getUTCDate()),
  );
  const firstDayOfThisMonthUTC = new Date(
    Date.UTC(today.getUTCFullYear(), today.getUTCMonth(), 1),
  );

  const defaultStart = firstDayOfThisMonthUTC.toISOString().split("T")[0];
  const defaultEnd = todayUTC.toISOString().split("T")[0];

  const [selectedStartDate, setSelectedStartDate] = useState(defaultStart);
  const [selectedEndDate, setSelectedEndDate] = useState(defaultEnd);

  const [includeTerminated, setIncludeTerminated] = useState(false);

  const [groups, setGroups] = useState([Group.Interns]);
  const groupsData = Object.values(Group);

  const [summaryData, setSummaryData] = useState({
    totalMembers: 0,
    totalCompletedTickets: 0,
    totalMergedCls: 0,
    totalMergedLoc: 0,
    totalMeetingCount: 0,
    totalMessagesSent: 0,
  });

  const [sortColumn, setSortColumn] = useState(null);
  const [sortDirection, setSortDirection] = useState("asc");
  const [tableData, setTableData] = useState([]);

  /**
   * Columns configuration for the members table.
   * Must align with {@link TableMemberData}.
   */
  const tableColumns = [
    { header: "LDAP", accessor: "ldap", sortable: true },
    {
      header: "Jira Tickets (Done)",
      accessor: "jiraTicketsDone",
      sortable: true,
    },
    { header: "Merged CLs", accessor: "mergedCls", sortable: true },
    { header: "Merged LOC", accessor: "mergedLoc", sortable: true },
    { header: "Meeting Count", accessor: "meetingCount", sortable: true },
    {
      header: "Chat Messages Sent",
      accessor: "chatMessagesSent",
      sortable: true,
    },
  ];

  /**
   * Toggles the selection of a team group.
   * This function does not return a value; instead, it updates component state.
   * @param {Group} groupName - The group to add or remove from the selection.
   */
  const handleGroupChange = (groupName) => {
    setGroups((prevGroups) => {
      if (prevGroups.includes(groupName)) {
        return prevGroups.filter((g) => g !== groupName);
      } else {
        return [...prevGroups, groupName];
      }
    });
  };

  /**
   * Updates the state with the new selected date range.
   * @param {{ startDate: string; endDate: string }} newDates
   */
  const handleDateChange = ({ startDate, endDate }) => {
    setSelectedStartDate(startDate);
    setSelectedEndDate(endDate);
  };

  /**
   * Fetches and processes data from the API based on the provided filters.
   * Updates `summaryData` and `tableData` states.
   * @param {string} startDate - The start date for the data fetch.
   * @param {string} endDate - The end date for the data fetch.
   * @param {Group[]} groups - The list of groups to filter by.
   * @param {boolean} includeTerminated - Whether to include terminated members.
   */
  const fetchDataAndRender = async ({
    startDate,
    endDate,
    groups,
    includeTerminated,
  }) => {
    try {
      const [{ data: summaryResult }, { data: ldapsResult }] =
        await Promise.all([
          getSummary({
            startDate: startDate,
            endDate: endDate,
            groups: groups,
            includeTerminated: includeTerminated,
          }),
          getLdapsAndDisplayNames({
            status: includeTerminated ? LdapStatus.All : LdapStatus.Active,
            groups: groups,
          }),
        ]);

      let totalLdaps = 0;
      for (const group in ldapsResult) {
        const statusObject = ldapsResult[group];
        for (const status in statusObject) {
          const ldapMap = statusObject[status];
          totalLdaps += Object.keys(ldapMap).length;
        }
      }

      const accumulatedSummary = summaryResult.reduce(
        (acc, member) => {
          acc.totalCompletedTickets += member.jira_issue_done;
          acc.totalMergedCls += member.cl_merged;
          acc.totalMergedLoc += member.loc_merged;
          acc.totalMeetingCount += member.meeting_count;
          acc.totalMessagesSent += member.chat_count;
          return acc;
        },
        {
          totalCompletedTickets: 0,
          totalMergedCls: 0,
          totalMergedLoc: 0,
          totalMeetingCount: 0,
          totalMessagesSent: 0,
        },
      );

      const newTableData = summaryResult.map((member) => ({
        ldap: member.ldap,
        jiraTicketsDone: member.jira_issue_done,
        mergedCls: member.cl_merged,
        mergedLoc: member.loc_merged,
        meetingCount: member.meeting_count,
        chatMessagesSent: member.chat_count,
      }));

      setTableData(newTableData);

      setSummaryData({
        ...accumulatedSummary,
        totalMembers: totalLdaps,
      });
    } catch (err) {
      console.log(err);
    } finally {
      console.log(summaryData);
    }
  };

  /**
   * Handler for the initial data fetch when the component mounts.
   */
  const handleInitialLoad = () => {
    fetchDataAndRender({
      startDate: defaultStart,
      endDate: defaultEnd,
      groups: [Group.Interns],
      includeTerminated: false,
    });
  };

  /**
   * Handler for the search button click.
   */
  const handleSearchClick = () => {
    fetchDataAndRender({
      startDate: selectedStartDate,
      endDate: selectedEndDate,
      groups: groups,
      includeTerminated: includeTerminated,
    });
  };

  /**
   * Toggles the sorting direction or sets a new column to sort by.
   * @param {string} columnAccessor - The key of the column to sort by.
   */
  const handleSort = (columnAccessor) => {
    if (sortColumn === columnAccessor) {
      setSortDirection((prevDir) => (prevDir === "asc" ? "desc" : "asc"));
    } else {
      setSortColumn(columnAccessor);
      setSortDirection("asc");
    }
  };

  /**
   * Memoized value for the sorted table data. Recalculates only when
   * `tableData`, `sortColumn`, or `sortDirection` changes.
   * @type {TableMemberData[]}
   */
  const sortedTableData = useMemo(() => {
    if (!sortColumn || tableData.length === 0) {
      return tableData;
    }
    const sortableData = [...tableData];
    sortableData.sort((a, b) => {
      const valA = a[sortColumn];
      const valB = b[sortColumn];
      let comparison = 0;
      if (sortColumn === "ldap") {
        comparison = String(valA).localeCompare(String(valB));
      } else {
        comparison = Number(valA) - Number(valB);
      }
      return sortDirection === "asc" ? comparison : -comparison;
    });
    return sortableData;
  }, [tableData, sortColumn, sortDirection]);

  /**
   * useEffect hook to trigger an initial data fetch when the component mounts.
   */
  useEffect(() => {
    handleInitialLoad();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="dashboard-page">
      <div className="welcome-header">
        <span role="img" aria-label="clapping hands">
          &#x1F44F;
        </span>
        <h2>Welcome</h2>
      </div>

      <div className="summary-cards">
        <Card title="Members" value={summaryData.totalMembers} />
        <Card
          title="Jira Tickets (Done)"
          value={summaryData.totalCompletedTickets}
        />
        <Card title="Merged CLs" value={summaryData.totalMergedCls} />
        <Card title="Merged LOC" value={summaryData.totalMergedLoc} />
        <Card title="Meeting Count" value={summaryData.totalMeetingCount} />
        <Card
          title="Chat Messages Sent"
          value={summaryData.totalMessagesSent}
        />
      </div>

      <div className="search-filter-row">
        <DateRangePicker
          defaultStartDate={defaultStart}
          defaultEndDate={defaultEnd}
          onChange={handleDateChange}
        />
        {groupsData.map((group) => (
          <label key={group} className="checkbox-item">
            <input
              type="checkbox"
              checked={groups.includes(group)}
              onChange={() => handleGroupChange(group)}
            />
            <span>{group}</span>
          </label>
        ))}

        <label className="checkbox-item">
          <input
            type="checkbox"
            checked={includeTerminated}
            onChange={(e) => setIncludeTerminated(e.target.checked)}
          />
          <span>Include Terminated Members</span>
        </label>

        <button className="search-button" onClick={handleSearchClick}>
          Search
        </button>
      </div>

      <Table
        className="table-container"
        columns={tableColumns}
        data={sortedTableData}
        onSort={handleSort}
        sortColumn={sortColumn}
        sortDirection={sortDirection}
      />
    </div>
  );
};

export default Dashboard;
