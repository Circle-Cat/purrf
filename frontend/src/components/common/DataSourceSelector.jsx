import { useState, useEffect, useMemo, useCallback } from "react";
import "@/components/common/DataSourceSelector.css";
import {
  getMicrosoftChatTopics,
  getGoogleChatSpaces,
  getGoogleCalendars,
  getJiraProjects,
  getGerritProjects,
} from "@/api/dataSearchApi";
import { ChatProvider, DataSourceNames } from "@/constants/Groups";
import handleMultiplePromises from "@/utils/promiseUtils";
import Modal from "@/components/common/Modal";
/**
 * DataSourceSelector Component
 *
 * A UI component that allows users to select items from multiple data sources
 * (e.g., Microsoft Chat, Google Chat, Jira, Gerrit, Calendar). Supports per-source
 * selection, global selection, and final confirmation.
 *
 * @component
 * @param {Object} props
 * @param {boolean} props.isOpen - Controls whether the DataSourceSelector shows
 * @param {Function} props.onConfirm - Callback invoked with the final selection object
 *                                     when the "OK" button is clicked. The object structure
 *                                     is { DataSourceNames.CHAT: Array<{provider: string, id: string, name: string}>,
 *                                           DataSourceNames.JIRA: Array<string>,
 *                                           DataSourceNames.GERRIT: Array<string>,
 *                                           DataSourceNames.CALENDAR?: Array<{provider: string, id: string, name: string}>,
 *                                         }
 * @param {Function} props.onCancel - Callback invoked when the "Cancel" button is clicked or modal is closed.
 *
 * @example
 * ```jsx
 *   const [showSelector, setShowSelector] = useState(false);
 *   const [selectedData, setSelectedData] = useState(null);
 *
 *   const handleConfirmSelection = (selection) => {
 *     console.log("Confirmed selection:", selection);
 *     setSelectedData(selection);
 *     setShowSelector(false); // Close the selector
 *   };
 *
 *   const handleCancelSelection = () => {
 *     console.log("Selection cancelled.");
 *     setShowSelector(false); // Close the selector
 *   };
 *
 *   return (
 *     <div>
 *       <button onClick={() => setShowSelector(true)}>Open Data Selector</button>
 *       <DataSourceSelector
 *               isOpen={showSelector} // Pass isOpen prop
 *               onConfirm={handleConfirmSelection}
 *               onCancel={handleCancelSelection}
 *             />
 *     </div>
 *   );
 *
 * ```
 */
export const DataSourceSelector = ({ isOpen, onConfirm, onCancel }) => {
  const [activeSource, setActiveSource] = useState("");
  const [selectedItems, setSelectedItems] = useState({});
  const [dataSources, setDataSources] = useState({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  /**
   * Fetch data from multiple APIs and process it into a unified structure.
   * Runs only once on component mount.
   */
  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      setError(null);

      try {
        const promises = [
          getMicrosoftChatTopics().then((response) => ({
            key: DataSourceNames.CHAT,
            items: Object.entries(response.data || {}).map(([id, name]) => ({
              id,
              name,
              provider: ChatProvider.Microsoft,
            })),
          })),
          getGoogleChatSpaces().then((response) => ({
            key: DataSourceNames.CHAT,
            items: Object.entries(response.data || {}).map(([id, name]) => ({
              id,
              name,
              provider: ChatProvider.Google,
            })),
          })),
          getJiraProjects().then((response) => ({
            key: DataSourceNames.JIRA,
            items: Object.entries(response.data || {}).map(([id, name]) => ({
              id,
              name,
            })),
          })),
          getGerritProjects().then((response) => ({
            key: DataSourceNames.GERRIT,
            items: (response.data || []).map((name) => ({
              id: name,
              name,
            })),
          })),
          getGoogleCalendars().then((response) => ({
            key: DataSourceNames.CALENDAR,
            items: (response.data || []).map((item) => ({
              id: item.id,
              name: item.name,
            })),
          })),
        ];

        const providerNames = [
          "Microsoft Chat Topics",
          "Google Chat Spaces",
          "Jira Projects",
          "Gerrit Projects",
          "Google Calendars",
        ];

        const results = await handleMultiplePromises(
          promises,
          providerNames,
          "Data Source fetching:",
        );

        const initialDataSources = {
          [DataSourceNames.CHAT]: [],
          [DataSourceNames.JIRA]: [],
          [DataSourceNames.GERRIT]: [],
          [DataSourceNames.CALENDAR]: [],
        };

        const processedData = results.reduce((acc, result) => {
          if (result?.key && result?.items) {
            if (result.key === DataSourceNames.CHAT) {
              acc[result.key] = [...acc[result.key], ...result.items];
            } else {
              acc[result.key] = result.items;
            }
          }
          return acc;
        }, initialDataSources);

        setDataSources(processedData);
      } catch (e) {
        console.error("Error fetching or processing data:", e);
        setError("Failed to load data. Please try again.");
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, []);

  /**
   * Ensure `activeSource` is valid after data is loaded.
   */
  useEffect(() => {
    if (
      Object.keys(dataSources).length > 0 &&
      (!activeSource || !dataSources[activeSource])
    ) {
      setActiveSource(Object.keys(dataSources)[0]);
    }
  }, [dataSources, activeSource]);

  /** Get items for the currently active source. */
  const currentActiveSourceItems = useMemo(() => {
    return dataSources[activeSource] || [];
  }, [dataSources, activeSource]);

  /** Get selected items for the currently active source. */
  const currentActiveSourceSelectedItems = useMemo(() => {
    return selectedItems[activeSource] || [];
  }, [selectedItems, activeSource]);

  /** Compute global "Select All" state across all sources. */
  const globalAllChecked = useMemo(() => {
    if (Object.keys(dataSources).length === 0) return false;
    let totalSelectableItems = 0;
    let totalSelectedItems = 0;
    for (const sourceName in dataSources) {
      const sourceItems = dataSources[sourceName] || [];
      totalSelectableItems += sourceItems.length;
      const currentSelected = selectedItems[sourceName] || [];
      totalSelectedItems += currentSelected.length;
    }
    return (
      totalSelectableItems > 0 && totalSelectableItems === totalSelectedItems
    );
  }, [dataSources, selectedItems]);

  /**
   * Toggle global "Select All" across all data sources.
   * If all are selected → deselect all, otherwise select all.
   */
  const handleToggleGlobalAll = useCallback(() => {
    setSelectedItems((prevSelectedItems) => {
      const newSelectedItems = {};
      let currentlyGlobalAllSelected = true;
      let hasAnySelectableItems = false;
      for (const sourceName in dataSources) {
        const all = dataSources[sourceName] || [];
        if (all.length > 0) hasAnySelectableItems = true;
        const chosen = prevSelectedItems[sourceName] || [];
        if (chosen.length !== all.length) {
          currentlyGlobalAllSelected = false;
          break;
        }
      }
      if (currentlyGlobalAllSelected && hasAnySelectableItems) {
        Object.keys(dataSources).forEach((source) => {
          newSelectedItems[source] = [];
        });
      } else {
        Object.keys(dataSources).forEach((source) => {
          newSelectedItems[source] = [...(dataSources[source] || [])];
        });
      }
      return newSelectedItems;
    });
  }, [dataSources]);

  /**
   * Toggle selection of a single item within the active source.
   *
   * @param {Object} item - Item object with `id` and `name`.
   */
  const handleToggleItem = useCallback(
    (item) => {
      setSelectedItems((prev) => {
        const prevSourceItems = prev[activeSource] || [];
        const isSelected = prevSourceItems.some(
          (selectedItem) => selectedItem.id === item.id,
        );
        let newSelectedItems;
        if (isSelected) {
          newSelectedItems = prevSourceItems.filter(
            (selectedItem) => selectedItem.id !== item.id,
          );
        } else {
          newSelectedItems = [...prevSourceItems, item];
        }
        return {
          ...prev,
          [activeSource]: newSelectedItems,
        };
      });
    },
    [activeSource],
  );

  /**
   * Toggle "Select All" for a specific data source.
   *
   * @param {string} source - The name of the data source.
   */
  const handleToggleSourceAll = useCallback(
    (source) => {
      setSelectedItems((prev) => {
        const all = dataSources[source] || [];
        const currentSelected = prev[source] || [];
        const isAllSelected =
          all.length > 0 && currentSelected.length === all.length;
        const next = isAllSelected ? [] : [...all];
        return { ...prev, [source]: next };
      });
    },
    [dataSources],
  );

  /**
   * Confirm selection and transform the selected items
   * into the final structured payload.
   */
  const handleConfirm = useCallback(() => {
    const finalSelection = {};
    if (selectedItems[DataSourceNames.CHAT]) {
      const chatSelection = selectedItems[DataSourceNames.CHAT].map((item) => ({
        provider: item.provider,
        id: item.id,
        name: item.name,
      }));
      finalSelection[DataSourceNames.CHAT] = chatSelection;
    }
    if (selectedItems[DataSourceNames.JIRA]) {
      finalSelection[DataSourceNames.JIRA] = selectedItems[
        DataSourceNames.JIRA
      ].map((item) => item.id);
    }
    if (selectedItems[DataSourceNames.GERRIT]) {
      finalSelection[DataSourceNames.GERRIT] = selectedItems[
        DataSourceNames.GERRIT
      ].map((item) => item.name);
    }
    if (selectedItems[DataSourceNames.CALENDAR]) {
      finalSelection[DataSourceNames.CALENDAR] = selectedItems[
        DataSourceNames.CALENDAR
      ].map((item) => item.id);
    }
    onConfirm(finalSelection);
  }, [selectedItems, onConfirm]);

  const content = (
    <>
      {loading && <div>Loading...</div>}
      {error && <div>{error}</div>}
      {!loading && !error && (
        <>
          <div className="dss-global-header">
            <label className="dss-global-select-all">
              <input
                type="checkbox"
                checked={globalAllChecked}
                onChange={handleToggleGlobalAll}
                aria-label="Select all items across all sources"
              />{" "}
              Select All
            </label>
          </div>

          <div className="dss-body">
            <aside className="dss-sidebar">
              {Object.keys(dataSources).map((source) => {
                const allSourceItems = dataSources[source] || [];
                const currentSourceSelected = selectedItems[source] || [];
                const sourceAllChecked =
                  allSourceItems.length > 0 &&
                  currentSourceSelected.length === allSourceItems.length;
                return (
                  <div
                    key={source}
                    className={`dss-sidebar-item ${activeSource === source ? "active" : ""}`}
                    onClick={() => setActiveSource(source)}
                    role="button"
                    tabIndex={0}
                  >
                    <input
                      type="checkbox"
                      checked={sourceAllChecked}
                      onChange={(e) => {
                        e.stopPropagation();
                        handleToggleSourceAll(source);
                      }}
                      aria-label={`Select all ${source}`}
                    />
                    <span>{source}</span>
                  </div>
                );
              })}
            </aside>

            <main className="dss-main">
              {currentActiveSourceItems.map((item) => (
                <div key={item.id} className={`dss-item`}>
                  <label>
                    <input
                      type="checkbox"
                      checked={currentActiveSourceSelectedItems.some(
                        (selected) => selected.id === item.id,
                      )}
                      onChange={() => handleToggleItem(item)}
                    />{" "}
                    {item.name}
                  </label>
                </div>
              ))}
            </main>
          </div>

          <footer className="dss-footer">
            <button className="cancel-button" onClick={onCancel}>
              Cancel
            </button>
            <button className="ok-button" onClick={handleConfirm}>
              OK
            </button>
          </footer>
        </>
      )}
    </>
  );

  return (
    <Modal isOpen={isOpen} onClose={onCancel} title="Select Data Sources">
      <div className="dss-container">{content}</div>
    </Modal>
  );
};
