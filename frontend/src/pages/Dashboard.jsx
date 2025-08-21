import { useState } from "react";
import "@/pages/Dashboard.css";
import { Group } from "@/constants/Groups";
import DateRangePicker from "@/components/common/DateRangePicker";
import { getSummary } from "@/api/dashboardApi";

/**
 * Dashboard Component
 *
 * Provides an overview of team activities and metrics, with
 * interactive filtering options.
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
 * - `summaryData` (object|null): The fetched summary data from the API.
 *
 * Default Behavior:
 * - Date range defaults from the first day of the current month to today.
 * - Initial group selection defaults to `[Group.Interns]`.
 *
 * Handlers:
 * - `handleGroupChange(groupName: Group)`: Toggles selection of a group.
 * - `handleDateChange({ startDate, endDate }: { startDate: string; endDate: string })`: Updates selected date range.
 * - `handleSearch()`: Fetches summary data using current filters and updates state.
 *
 * Notes:
 * - The `getSummary` API is asynchronous and sets `summaryData` on success.
 * - Date values are managed in UTC to avoid timezone inconsistencies.
 *
 * @component
 * @example
 * <Dashboard />
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

  const [summaryData, setSummaryData] = useState(null);

  const handleGroupChange = (groupName) => {
    setGroups((prevGroups) => {
      if (prevGroups.includes(groupName)) {
        return prevGroups.filter((g) => g !== groupName);
      } else {
        return [...prevGroups, groupName];
      }
    });
  };

  const handleDateChange = ({ startDate, endDate }) => {
    setSelectedStartDate(startDate);
    setSelectedEndDate(endDate);
  };

  const handleSearch = async () => {
    try {
      const result = await getSummary({
        startDate: selectedStartDate,
        endDate: selectedEndDate,
        groups: groups,
        includeTerminated: includeTerminated,
      });

      setSummaryData(result);
    } catch (err) {
      console.log(err);
    } finally {
      console.log(summaryData);
    }
  };

  return (
    <div className="dashboard-page">
      <div className="welcome-header">
        <span role="img" aria-label="clapping hands">
          &#x1F44F;
        </span>
        <h2>Welcome</h2>
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

        <button className="search-button" onClick={handleSearch}>
          Search
        </button>
      </div>
    </div>
  );
};

export default Dashboard;
