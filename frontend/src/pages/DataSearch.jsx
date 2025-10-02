import { useState, useEffect } from "react";
import "@/pages/DataSearch.css";
import MemberSelector from "@/components/common/MemberSelector";
import DateRangePicker from "@/components/common/DateRangePicker";
import { DataSourceSelector } from "@/components/common/DataSourceSelector";
import Tab from "@/components/common/Tab.jsx";

/**
 * DataSearch Page
 *
 * Main entry point for querying cross-source data (Chat, Jira, Gerrit, Calendar).
 * Combines:
 *  - A topbar LDAP chip that opens the MemberSelector modal.
 *  - A date range picker + Search button row.
 *  - A tabbed view for data sources.
 *
 * State
 * - ldapModalOpen {boolean}: whether the member selector modal is open.
 * - selectedIds {string[]}: currently selected member LDAPs.
 * - selectedStartDate {string}: ISO-ish date string (from DateRangePicker).
 * - selectedEndDate {string}: ISO-ish date string (from DateRangePicker).
 * - showSelector {boolean}: whether the DataSourceSelector modal is open.
 * - selectedData {any}: the current selected data source(s).
 *
 * Behavior
 * - Clicking the LDAP chip opens MemberSelector.
 * - Chip label shows `LDAP (N)` when members are selected.
 * - DateRangePicker calls `onChange` with { startDate, endDate }.
 * - Search button logs the effective filters (you can wire this to an API).
 *
 * @component
 * @returns {JSX.Element}
 */
export default function DataSearch() {
  const [showTab, setShowTab] = useState(false);
  // LDAP selection state
  const [ldapModalOpen, setLdapModalOpen] = useState(false);
  const [selectedIds, setSelectedIds] = useState([]);
  const selectedCount = selectedIds.length;

  // Data source selection state
  const [showSelector, setShowSelector] = useState(false);
  const [selectedData, setSelectedData] = useState(null);

  // Date range state
  const defaultStart = "";
  const defaultEnd = "";
  const [selectedStartDate, setSelectedStartDate] = useState(defaultStart);
  const [selectedEndDate, setSelectedEndDate] = useState(defaultEnd);

  const [committedSearchParams, setCommittedSearchParams] = useState(null);

  useEffect(() => {
    setShowTab(false);
    setCommittedSearchParams(null);
  }, [selectedIds, selectedStartDate, selectedEndDate, selectedData]);

  /**
   * Handle changes from DateRangePicker.
   * @param {{startDate: string, endDate: string}}
   */
  const handleDateChange = ({ startDate, endDate }) => {
    setSelectedStartDate(startDate);
    setSelectedEndDate(endDate);
  };

  /**
   * Confirm selected data sources from DataSourceSelector.
   * @param {any} selection - The confirmed data source selection.
   */
  const handleConfirmSelection = (selection) => {
    setSelectedData(selection);
    setShowSelector(false);
  };

  /** Cancel data source selection and reset state. */
  const handleCancelSelection = () => {
    setShowSelector(false);
    setSelectedData(null);
  };

  /** Submit handler */
  const handleSearchClick = () => {
    if (
      selectedIds.length === 0 ||
      !selectedStartDate ||
      !selectedEndDate ||
      !selectedData
    ) {
      return;
    }
    setCommittedSearchParams({
      ldaps: selectedIds,
      startDate: selectedStartDate,
      endDate: selectedEndDate,
      selectedDataSources: selectedData,
    });

    setShowTab(true);
  };
  return (
    <div className="datesearch-page ds-page" data-testid="data-search-page">
      <div className="ds-topbar-row">
        <div className="ds-left-group">
          <button
            type="button"
            className="ldap-chip"
            onClick={() => setLdapModalOpen(true)}
            title="Pick members"
          >
            {selectedCount ? `LDAP (${selectedCount})` : "LDAP"}
          </button>

          <button
            type="button"
            className="ldap-chip"
            onClick={() => setShowSelector(true)}
          >
            Data Source
          </button>

          <DateRangePicker
            defaultStartDate={defaultStart}
            defaultEndDate={defaultEnd}
            onChange={handleDateChange}
          />
        </div>
        <button className="datasearch-button" onClick={handleSearchClick}>
          Search
        </button>
      </div>

      {/* MemberSelector modal (controlled) */}
      <MemberSelector
        open={ldapModalOpen}
        onClose={() => setLdapModalOpen(false)}
        selectedIds={selectedIds}
        onSelectedChange={(ids /* , members */) => {
          setSelectedIds(ids);
        }}
        onConfirm={(ids /* , members */) => {
          setSelectedIds(ids);
          setLdapModalOpen(false);
        }}
        onCancel={() => {
          setLdapModalOpen(false);
        }}
      />

      {/* DataSourceSelector modal (controlled) */}
      <DataSourceSelector
        isOpen={showSelector}
        onConfirm={handleConfirmSelection}
        onCancel={handleCancelSelection}
      />

      {/* Tabbed view for data reports */}
      <div className="ds-content-area">
        {showTab && committedSearchParams && (
          <Tab committedSearchParams={committedSearchParams} />
        )}
      </div>
    </div>
  );
}
