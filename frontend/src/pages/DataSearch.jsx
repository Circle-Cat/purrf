import "@/pages/DataSearch.css";

const DataSearch = () => {
  /**
   * Handler for the search button click.
   */
  const handleSearchClick = () => {
    console.log("Searchbutton clicked!");
  };

  return (
    <div className="datesearch-page">
      <div className="page-title">Data Search Page</div>
      <button className="datasearch-button" onClick={handleSearchClick}>
        Search
      </button>
    </div>
  );
};

export default DataSearch;
