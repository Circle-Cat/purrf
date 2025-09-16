import { useState } from "react";
import MemberSelector from "@/components/common/MemberSelector";
import DateRangePicker from "@/components/common/DateRangePicker";
import "@/pages/DataSearch.css";

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
  // LDAP selection state
  const [ldapModalOpen, setLdapModalOpen] = useState(false);
  const [selectedIds, setSelectedIds] = useState([]);
  const selectedCount = selectedIds.length;

  // Date range state
  const defaultStart = "";
  const defaultEnd = "";
  const [selectedStartDate, setSelectedStartDate] = useState(defaultStart);
  const [selectedEndDate, setSelectedEndDate] = useState(defaultEnd);

  /** Update selected date range from DateRangePicker. */
  const handleDateChange = ({ startDate, endDate }) => {
    setSelectedStartDate(startDate);
    setSelectedEndDate(endDate);
  };

  /** Submit handler (wire this to your fetch once endpoints are ready). */
  const handleSearchClick = () => {
    // Replace these logs with your actual query/invoke to backend.
    console.log("[DataSearch] Search clicked");
    console.log("Selected LDAP IDs:", selectedIds);
    console.log("Selected Start Date:", selectedStartDate);
    console.log("Selected End Date:", selectedEndDate);
  };
  return (
    <div className="datesearch-page ds-page" data-testid="data-search-page">
      <div className="ds-topbar-row">
        <button
          type="button"
          className="ldap-chip"
          onClick={() => setLdapModalOpen(true)}
          title="Pick members"
        >
          {selectedCount ? `LDAP (${selectedCount})` : "LDAP"}
        </button>

        <div className="DateRangePicker-search-row ds-search-row">
          <DateRangePicker
            defaultStartDate={defaultStart}
            defaultEndDate={defaultEnd}
            onChange={handleDateChange}
          />
          <button className="datasearch-button" onClick={handleSearchClick}>
            Search
          </button>
        </div>
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
    </div>
  );
}
