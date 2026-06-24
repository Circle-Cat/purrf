import { useState, useEffect } from "react";
import { getGoogleCalendarEvents } from "@/api/dataSearchApi";
import Table from "@/components/common/Table";
import { flattenGoogleCalendarScheduleData } from "@/utils/flattenScheduleData";

/**
 * React component to display a report table of Google Calendar events for given Google Calendar search parameters.
 *
 * @param {Object} props
 * @param {Object} props.googleCalendarReportProps - Props containing search parameters.
 * @param {Object} props.googleCalendarReportProps.searchParams - Search parameters object with:
 *   - startDate: string
 *   - endDate: string
 *   - calendarIds: Array<string>
 *   - ldaps: Array<string>
 * @returns {JSX.Element} Rendered calendar report table with sorting capability.
 */
export const CalendarReportTable = ({ googleCalendarReportProps }) => {
  const [flatEvents, setFlatEvents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [sortConfig, setSortConfig] = useState({ key: null, direction: "asc" });

  const columns = [
    { header: "LDAP", accessor: "ldap", sortable: true },
    { header: "CALENDAR", accessor: "calendarName", sortable: true },
    { header: "EVENTS", accessor: "summary", sortable: true },
    { header: "DATE", accessor: "date", sortable: true },
    { header: "START TIME", accessor: "joinTime", sortable: false },
    { header: "END TIME", accessor: "leaveTime", sortable: false },
  ];

  useEffect(() => {
    /**
     * Fetches Google Calendar events from backend and flattens them for table display.
     */
    const fetchScheduleData = async () => {
      setLoading(true);
      setError(null);
      try {
        const { data: eventDetails } = await getGoogleCalendarEvents({
          startDate: googleCalendarReportProps.searchParams.startDate,
          endDate: googleCalendarReportProps.searchParams.endDate,
          calendarIds: googleCalendarReportProps.searchParams.calendarIds,
          ldaps: googleCalendarReportProps.searchParams.ldaps,
        });
        const flattened = flattenGoogleCalendarScheduleData(eventDetails);
        setFlatEvents(flattened);
      } catch (err) {
        setError("Failed to fetch data. Please check the provided parameters.");
        console.error(err);
      } finally {
        setLoading(false);
      }
    };
    fetchScheduleData();
  }, [googleCalendarReportProps.searchParams]);

  /**
   * Handles sorting of table columns.
   * @param {string} key - Column key to sort by.
   */
  const handleSort = (key) => {
    let direction = "asc";
    if (sortConfig.key === key && sortConfig.direction === "asc") {
      direction = "desc";
    }
    setSortConfig({ key, direction });
  };

  /**
   * Sorts a flat array of event objects based on the current sort configuration.
   *
   * @param {Array<Object>} flatEvents - Array of flattened event objects.
   *   Each object should have fields like 'ldap', 'calendarName', 'summary', 'date', etc.
   * @param {Object} sortConfig - Current sorting configuration.
   * @param {string|null} sortConfig.key - Field name to sort by. If null, no sorting is applied.
   * @param {'asc'|'desc'} sortConfig.direction - Sorting direction: 'asc' for ascending, 'desc' for descending.
   * @returns {Array<Object>} A new array sorted according to the specified key and direction.
   */
  const sortedEvents = [...flatEvents].sort((a, b) => {
    if (!sortConfig.key) return 0;
    const { key, direction } = sortConfig;
    const isDate = key === "date";

    let aValue = isDate ? new Date(a[key]) : a[key];
    let bValue = isDate ? new Date(b[key]) : b[key];

    const isString = typeof aValue === "string";

    const comparisonResult = isString
      ? aValue.localeCompare(bValue)
      : aValue - bValue;

    return direction === "asc" ? comparisonResult : -comparisonResult;
  });

  if (loading) {
    return <div className="loading">Loading schedule data...</div>;
  }

  if (error) {
    return <div className="error">{error}</div>;
  }

  if (flatEvents.length === 0) {
    return (
      <div className="no-data">No events found for the given parameters.</div>
    );
  }

  return (
    <div className="schedule-container">
      <Table
        columns={columns}
        data={sortedEvents}
        onSort={handleSort}
        sortColumn={sortConfig.key}
        sortDirection={sortConfig.direction}
      />
    </div>
  );
};
