import { useState } from "react";
import "@/pages/DataSearch.css";
import DateRangePicker from "@/components/common/DateRangePicker";

const DataSearch = () => {
  const defaultStart = "";
  const defaultEnd = "";

  const [selectedStartDate, setSelectedStartDate] = useState(defaultStart);
  const [selectedEndDate, setSelectedEndDate] = useState(defaultEnd);

  /**
   * Updates the state with the new selected date range.
   * @param {{ startDate: string; endDate: string }} newDates
   */
  const handleDateChange = ({ startDate, endDate }) => {
    setSelectedStartDate(startDate);
    setSelectedEndDate(endDate);
  };

  /**
   * Handler for the search button click.
   */
  const handleSearchClick = () => {
    console.log("Searchbutton clicked!");
    console.log("Selected Start Date:", selectedStartDate);
    console.log("Selected End Date:", selectedEndDate);
  };

  return (
    <div className="datesearch-page">
      <div className="page-title">Data Search Page</div>
      <div className="DateRangePicker-search-row">
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
  );
};

export default DataSearch;
