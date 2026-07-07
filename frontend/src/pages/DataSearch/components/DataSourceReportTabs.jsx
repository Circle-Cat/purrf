import { useMemo, useState, useEffect, useCallback } from "react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { CalendarReportTable } from "@/pages/DataSearch/components/CalendarReportTable";
import { ChatReportTable } from "@/pages/DataSearch/components/ChatReportTable";
import JiraReportTable from "@/pages/DataSearch/components/JiraReportTable";
import GerritReportTable from "@/pages/DataSearch/components/GerritReportTable";
import {
  ChatProvider,
  DataSourceNames,
  JiraIssueStatus,
} from "@/constants/Groups";

/** Lightweight inline SVG icons */
const IconChat = (props) => (
  <svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true" {...props}>
    <path
      fill="currentColor"
      d="M20 2H4a2 2 0 0 0-2 2v13a1 1 0 0 0 1.6.8L7 15h13a2 2 0 0 0 2-2V4a2 2 0 0 0-2-2z"
    />
  </svg>
);
const IconJira = (props) => (
  <svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true" {...props}>
    <path
      fill="currentColor"
      d="M7 3h10a2 2 0 0 1 2 2v2H5V5a2 2 0 0 1 2-2zm-2 7h14v2H5v-2zm0 5h10v2H5v-2z"
    />
  </svg>
);
const IconGerrit = (props) => (
  <svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true" {...props}>
    <path
      fill="currentColor"
      d="M6 3v6h2V5h8v4h2V3H6zm12 12v4H10v-4H8v6h12v-6h-2zM7 13l5-5 1.5 1.5L9.5 14H13v2H5v-8h2v5z"
    />
  </svg>
);
const IconCalendar = (props) => (
  <svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true" {...props}>
    <path
      fill="currentColor"
      d="M7 2h2v2h6V2h2v2h3a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h3V2zm14 8H3v10h18V10z"
    />
  </svg>
);

/**
 * Utility function to check if the core query parameters
 * (ldaps, startDate, endDate, selectedDataSources) are complete.
 *
 * @param {object} params - The committed search params.
 * @returns {boolean} True if all core params are present, false otherwise.
 */
const areCoreSearchParamsValidStrict = (params) => {
  return (
    params &&
    Array.isArray(params.ldaps) &&
    params.ldaps.length > 0 &&
    !!params.startDate &&
    !!params.endDate &&
    params.selectedDataSources
  );
};

/**
 * Utility function to generate props for report components
 * based on data source name and committed search params.
 *
 * @param {string} sourceName - Name of the data source (e.g., DataSourceNames.CALENDAR).
 * @param {object} committedSearchParams - The committed search parameters.
 * @returns {object|null} Props object suitable for a report component, or null if invalid.
 */
const getReportTableProps = (sourceName, committedSearchParams) => {
  const { ldaps, startDate, endDate, selectedDataSources } =
    committedSearchParams || {};
  const commonParams = { ldaps, startDate, endDate };

  if (!ldaps?.length || !startDate || !endDate || !selectedDataSources) {
    return null;
  }

  switch (sourceName) {
    case DataSourceNames.CALENDAR: {
      const calendarConfig = selectedDataSources[sourceName];
      if (!calendarConfig?.length) return null;
      return {
        googleCalendarReportProps: {
          searchParams: {
            ...commonParams,
            calendarIds: calendarConfig,
          },
        },
      };
    }
    case DataSourceNames.CHAT: {
      const chatConfig = selectedDataSources[sourceName];
      if (!chatConfig?.length) return null;

      const chatProviderList = [];
      let googleChatSpaceMap = {};
      let microsoftChatSpaceName = "";
      const allGoogleChatSpaceIds = [];

      for (const item of chatConfig) {
        if (ChatProvider.Google === item.provider) {
          allGoogleChatSpaceIds.push(item.id);
          googleChatSpaceMap[item.id] = item.name;
        } else if (ChatProvider.Microsoft === item.provider) {
          chatProviderList.push({ provider: ChatProvider.Microsoft });
          microsoftChatSpaceName = item.name;
        }
      }

      if (allGoogleChatSpaceIds.length > 0) {
        chatProviderList.push({
          provider: ChatProvider.Google,
          googleChatSpaceIds: allGoogleChatSpaceIds,
        });
      }

      return {
        chatReportProps: {
          searchParams: { ...commonParams, chatProviderList },
          googleChatSpaceMap,
          microsoftChatSpaceName,
        },
      };
    }
    case DataSourceNames.JIRA: {
      const jiraConfig = selectedDataSources[sourceName];
      if (!jiraConfig?.length) return null;
      const today = new Date().toISOString().split("T")[0];
      const endDate = commonParams.endDate;
      const isPast = endDate < today;
      const statusList = isPast
        ? [JiraIssueStatus.DONE]
        : [
            JiraIssueStatus.DONE,
            JiraIssueStatus.IN_PROGRESS,
            JiraIssueStatus.TODO,
          ];
      return {
        jiraReportProps: {
          searchParams: {
            ...commonParams,
            projectIds: jiraConfig,
            statusList: statusList,
          },
        },
      };
    }
    case DataSourceNames.GERRIT: {
      const gerritConfig = selectedDataSources[sourceName];
      if (!gerritConfig) return null;
      const { projectList, includeAllProjects } = gerritConfig;

      return {
        gerritReportProps: {
          searchParams: {
            ...commonParams,
            project: projectList,
            includeAllProjects,
          },
        },
      };
    }
    default:
      return null;
  }
};

/**
 * Tabs configuration for rendering data source report components.
 *
 * Each object in the `tabs` array defines a single tab and its associated metadata:
 * - `id` {string}: Unique DOM identifier for the tab (used for aria attributes).
 * - `label` {string}: The display label for the tab (usually a data source name).
 * - `icon` {JSX.Element}: An inline SVG icon representing the data source.
 * - `component` {React.ComponentType<any>}: The React component to render inside the tab panel.
 * - `sourceName` {string}: The logical identifier for the data source
 *   (must match one of the `DataSourceNames` values).
 *
 * Notes:
 * - Tab components are dynamically mounted/unmounted based on the `active` state.
 * - Tabs are disabled if the corresponding data source configuration in
 * `committedSearchParams.selectedDataSources` is incomplete or missing.
 */
export default function DataSourceReportTabs({ committedSearchParams }) {
  // Default to empty object to avoid null errors
  committedSearchParams = committedSearchParams || {};

  const [active, setActive] = useState(DataSourceNames.CHAT);

  /** Define tabs */
  const tabs = useMemo(
    () => [
      {
        id: "tab-chat",
        label: DataSourceNames.CHAT,
        icon: <IconChat />,
        component: ChatReportTable,
        sourceName: DataSourceNames.CHAT,
      },
      {
        id: "tab-jira",
        label: DataSourceNames.JIRA,
        icon: <IconJira />,
        component: JiraReportTable,
        sourceName: DataSourceNames.JIRA,
      },
      {
        id: "tab-gerrit",
        label: DataSourceNames.GERRIT,
        icon: <IconGerrit />,
        component: GerritReportTable,
        sourceName: DataSourceNames.GERRIT,
      },
      {
        id: "tab-calendar",
        label: DataSourceNames.CALENDAR,
        icon: <IconCalendar />,
        component: CalendarReportTable,
        sourceName: DataSourceNames.CALENDAR,
      },
    ],
    [],
  );

  /** Check if a data source is selected and has valid data */
  const isDataSourceSelected = useCallback(
    (sourceName) => {
      const selectedSourceData =
        committedSearchParams?.selectedDataSources?.[sourceName];

      if (!selectedSourceData) return false;

      if (sourceName === DataSourceNames.GERRIT) {
        return (
          Array.isArray(selectedSourceData.projectList) &&
          selectedSourceData.projectList.length > 0
        );
      }

      return Array.isArray(selectedSourceData) && selectedSourceData.length > 0;
    },
    [committedSearchParams],
  );

  /** Adjust active tab if current becomes invalid */
  useEffect(() => {
    if (!isDataSourceSelected(active)) {
      const firstValidTab = tabs.find((t) =>
        isDataSourceSelected(t.sourceName),
      );
      setActive(firstValidTab ? firstValidTab.sourceName : tabs[0].sourceName);
    }
  }, [committedSearchParams, active, tabs, isDataSourceSelected]);

  /** Memoized props for active tab */
  const activeTabReportProps = useMemo(
    () => getReportTableProps(active, committedSearchParams),
    [active, committedSearchParams],
  );

  if (!areCoreSearchParamsValidStrict(committedSearchParams)) {
    return null;
  }

  return (
    <Tabs
      value={active}
      onValueChange={setActive}
      className="flex flex-1 flex-col"
      data-testid="tab-component"
    >
      <TabsList aria-label="Purrf Data Sources" className="gap-1">
        {tabs.map((t) => (
          <TabsTrigger
            key={t.id}
            id={t.id}
            value={t.sourceName}
            disabled={!isDataSourceSelected(t.sourceName)}
            data-testid={`tab-button-${t.sourceName}`}
            className="gap-1.5 px-4 data-[state=active]:shadow-sm"
          >
            <span className="inline-flex leading-none" aria-hidden="true">
              {t.icon}
            </span>
            {t.label}
          </TabsTrigger>
        ))}
      </TabsList>

      {tabs.map((t) => (
        <TabsContent
          key={t.id}
          value={t.sourceName}
          className="flex flex-1 flex-col overflow-auto"
        >
          {active === t.sourceName && activeTabReportProps && (
            <t.component {...activeTabReportProps} />
          )}
        </TabsContent>
      ))}
    </Tabs>
  );
}
