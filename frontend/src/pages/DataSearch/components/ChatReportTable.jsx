import { useState, useEffect } from "react";
import {
  getMicrosoftChatMessagesCount,
  getGoogleChatMessagesCount,
} from "@/api/dataSearchApi";
import Table from "@/components/common/Table";
import { ChatProvider } from "@/constants/Groups";
import {
  flattenMicrosoftChatData,
  flattenGoogleChatData,
} from "@/utils/flattenScheduleData";
import handleMultiplePromises from "@/utils/promiseUtils";

/**
 * ChatReportTable
 *
 * React component to display a report table of chat messages for given search parameters.
 *
 * @param {Object} props - Component props
 * @param {Object} props.chatReportProps - Props containing search parameters
 * @param {Object} props.chatReportProps.searchParams - Search parameters object
 * @param {string} props.chatReportProps.searchParams.startDate - Start date of the search range (YYYY-MM-DD)
 * @param {string} props.chatReportProps.searchParams.endDate - End date of the search range (YYYY-MM-DD)
 * @param {Array<string>} props.chatReportProps.searchParams.ldaps - Array of LDAP user identifiers
 * @param {Array<Object>} props.chatReportProps.searchParams.chatProviderList - Array of chat provider configurations
 *   @param {string} provider - Chat provider type, should be one of ChatProvider.Microsoft or ChatProvider.Google
 *   @param {Array<string>} [googleChatSpaceIds] - Optional, array of Google chat space IDs (used when provider is Google)
 * @param {Object} props.chatReportProps.googleChatSpaceMap - Mapping of Google Chat space IDs to names
 * @param {string} props.chatReportProps.microsoftChatSpaceName - Selected Microsoft Chat Space Name.
 *   Note: Due to the current Microsoft backend API design, only one chat space exists and is returned,
 *   so this parameter is provided to simplify table rendering. In the future, if multiple chat spaces
 *   are supported, the handling can be updated to follow the same logic as Google Chat.

 * @returns {JSX.Element} Rendered chat report table with sorting capability.
 */
export const ChatReportTable = ({ chatReportProps }) => {
  const [flatEvents, setFlatEvents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [sortConfig, setSortConfig] = useState({ key: null, direction: "asc" });

  const columns = [
    { header: "LDAP", accessor: "ldap", sortable: true },
    { header: "CHAT SPACE", accessor: "chatSpace", sortable: true },
    { header: "COUNTS", accessor: "counts", sortable: true },
  ];

  useEffect(() => {
    /**
     * Fetch chat data from backend for all configured providers,
     * flatten it, and set it to state for table display.
     *
     * @async
     */
    const fetchChatData = async () => {
      setLoading(true);
      setError(null);

      try {
        const promises = chatReportProps.searchParams.chatProviderList.map(
          (providerConfig) => {
            if (ChatProvider.Microsoft === providerConfig.provider) {
              return getMicrosoftChatMessagesCount({
                startDate: chatReportProps.searchParams.startDate,
                endDate: chatReportProps.searchParams.endDate,
                ldaps: chatReportProps.searchParams.ldaps,
              }).then((response) => {
                const flattenedData = flattenMicrosoftChatData({
                  data: response.data.result,
                  defaultChatSpace: chatReportProps.microsoftChatSpaceName,
                });
                return flattenedData;
              });
            } else if (ChatProvider.Google === providerConfig.provider) {
              return getGoogleChatMessagesCount({
                startDate: chatReportProps.searchParams.startDate,
                endDate: chatReportProps.searchParams.endDate,
                ldaps: chatReportProps.searchParams.ldaps,
                spaceIds: providerConfig.googleChatSpaceIds,
              }).then((response) => {
                const flattenedData = flattenGoogleChatData({
                  data: response.data.result,
                  spaceMap: chatReportProps.googleChatSpaceMap,
                });
                return flattenedData;
              });
            }
            return Promise.reject(
              new Error(`Unknown chat provider: ${providerConfig.provider}`),
            );
          },
        );

        const providerNames = chatReportProps.searchParams.chatProviderList.map(
          (p) => p.provider,
        );

        const successfulData = await handleMultiplePromises(
          promises,
          providerNames,
          "Chat count API:",
        );
        setFlatEvents(successfulData);
      } catch (err) {
        setError("An unexpected error occurred while fetching data.");
        console.error("Unexpected error:", err);
      } finally {
        setLoading(false);
      }
    };
    fetchChatData();
  }, [chatReportProps]);

  /**
   * Handles sorting of table columns.
   * This function is triggered when a user clicks on a sortable column header.
   * It determines the next sorting direction (ascending or descending)
   * for the clicked column and updates the sorting configuration state.
   *
   * @param {string} key - Column key to sort by
   */
  const handleSort = (key) => {
    let direction = "asc";

    // If BOTH conditions are true, it implies:
    // 1. The user clicked the 'name' column.
    // 2. The 'name' column was already sorted in 'ascending' order.
    // Therefore, the user's intent is to reverse the sort order to 'descending'.
    if (sortConfig.key === key && sortConfig.direction === "asc") {
      direction = "desc";
    }
    setSortConfig({ key, direction });
  };

  /**
   * Sorts a flat array of event objects based on the current sort configuration.
   *
   * @type {Array<Object>}
   */
  const sortedEvents = [...flatEvents].sort((a, b) => {
    if (!sortConfig.key) return 0;
    const { key, direction } = sortConfig;

    let aValue = a[key];
    let bValue = b[key];

    const isString = typeof aValue === "string";

    const comparisonResult = isString
      ? aValue.localeCompare(bValue)
      : aValue - bValue;

    return direction === "asc" ? comparisonResult : -comparisonResult;
  });

  if (loading) {
    return <div className="loading">Loading chat data...</div>;
  }

  if (error) {
    return <div className="error">{error}</div>;
  }

  if (flatEvents.length === 0) {
    return (
      <div className="no-data">
        No chat messages found for the given parameters.
      </div>
    );
  }

  return (
    <div className="chat-report-container">
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
