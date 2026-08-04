import { useState, useEffect } from "react";
import { getJiraIssueDetails, getJiraIssueBrief } from "@/api/dataSearchApi";
import { JiraIssueStatus } from "@/constants/Groups";

/** Status indicator dot color, keyed by display status name. */
const STATUS_DOT_CLASS = {
  "To Do": "bg-[#f39c12]",
  "In Progress": "bg-primary",
  Done: "bg-[#27ae60]",
};

const LOADING_OR_EMPTY = "p-5 text-center text-[0.9rem] text-gray-400";

/**
 * @typedef {Object} StatusData
 * @property {string} status - The status name (e.g., "To Do", "In Progress", "Done").
 * @property {number} count - Number of issues in this status.
 * @property {string|number} storyPoints - Total story points for this status.
 * @property {Array<string>} issueIds - List of issue IDs.
 */

/**
 * @typedef {Object} User
 * @property {string} name - User display name.
 *   If `ldapsAndDisplayNames` has a mapping for the LDAP, format as "ldap (displayName)", otherwise just "ldap".
 * @property {Array<StatusData>} statusData - Array of status data for the user.
 */

/**
 * Mapping API status keys to user-friendly display names
 */
const statusDisplayNamesMap = {
  [JiraIssueStatus.TODO]: "To Do",
  [JiraIssueStatus.IN_PROGRESS]: "In Progress",
  [JiraIssueStatus.DONE]: "Done",
};

/**
 * Format Jira brief data into a structured format for rendering.
 *
 * For each user:
 * - "To Do" and "In Progress" will always have `storyPoints` set to "-"
 * - "Done" will include a numeric story points value formatted to one decimal place (e.g., "0.0")
 * - User name will use the LDAP displayName if provided, otherwise fallback to LDAP
 * - Displays only the statuses present in the `statusList` parameter.
 *
 * @param {Object} jiraBriefs - Raw Jira briefs data.
 * @param {Object} ldapsAndDisplayNames - Optional mapping from LDAP to display name.
 * @param {string[]} statusList - List of status keys (e.g., "todo", "in_progress", "done") to display.
 * @returns {Array<User>} - Formatted user data with status breakdown.
 */
const formatJiraBriefsData = (jiraBriefs, ldapsAndDisplayNames, statusList) => {
  if (!jiraBriefs || !statusList) {
    return [];
  }
  const users = [];
  for (const userLdap in jiraBriefs) {
    if (userLdap === "time_range") {
      continue;
    }
    const userData = jiraBriefs[userLdap];
    const displayName = ldapsAndDisplayNames?.[userLdap] ?? null;

    const userStatusData = [];
    statusList.forEach((statusKey) => {
      const displayStatusName = statusDisplayNamesMap[statusKey] || statusKey;
      const count = userData[statusKey]?.length ?? 0;
      const issueIds = userData[statusKey] ?? [];

      let storyPoints = "-";
      if (statusKey === JiraIssueStatus.DONE) {
        storyPoints = (userData.done_story_points_total ?? 0).toFixed(1);
      }

      userStatusData.push({
        status: displayStatusName,
        count: count,
        storyPoints: storyPoints,
        issueIds: issueIds,
      });
    });

    users.push({
      name: displayName ? `${userLdap} (${displayName})` : userLdap,
      statusData: userStatusData,
    });
  }
  return users;
};

/**
 * Render a single task detail row.
 *
 * @param {Object} props
 * @param {Object} props.task - Task object containing issue details.
 * @param {string} props.task.issue_key - Unique key of the issue.
 * @param {string} props.task.issue_title - Title/summary of the issue.
 * @param {number|string} props.task.story_point - Story point value of the issue.
 * @param {string} [props.task.finish_date] - Date string in `YYYYMMDD` format.
 *   If provided, it will be parsed into `YYYY/MM/DD`.
 *   If missing or invalid, a hyphen (`-`) will be displayed instead.
 * @returns {JSX.Element} Table row element representing task details.
 */
const TaskDetailRow = ({ task }) => {
  const formattedDate = task.finish_date
    ? `${task.finish_date.slice(0, 4)}/${task.finish_date.slice(4, 6)}/${task.finish_date.slice(6, 8)}`
    : "-";

  return (
    <tr className="even:bg-muted hover:bg-muted [&>td]:px-[15px] [&>td]:py-2 [&>td]:text-[0.8rem]">
      <td>{task.issue_key}</td>
      <td>{task.issue_title}</td>
      <td>{task.story_point}</td>
      <td>{formattedDate}</td>
    </tr>
  );
};

/**
 * Render a collapsible row for a Jira status (e.g., To Do, In Progress, Done).
 * Expands to show task details on click.
 *
 * @param {Object} props
 * @param {StatusData} props.statusItem - Status data including count, story points, and issue IDs.
 * @returns {JSX.Element}
 */
const StatusRow = ({ statusItem }) => {
  const [isCollapsed, setIsCollapsed] = useState(true);
  const [tasks, setTasks] = useState(null);
  const [isLoading, setIsLoading] = useState(false);

  const { status, count, storyPoints, issueIds } = statusItem;

  const handleRowClick = async () => {
    setIsCollapsed(!isCollapsed);

    if (isCollapsed && issueIds && issueIds.length > 0 && !tasks) {
      setIsLoading(true);
      try {
        const { data: fetchedTasks } = await getJiraIssueDetails({
          issueIds: issueIds,
        });
        setTasks(fetchedTasks);
      } catch (error) {
        console.error("Failed to fetch jira issue details:", error);
      } finally {
        setIsLoading(false);
      }
    }
  };

  return (
    <>
      <tr
        onClick={handleRowClick}
        className="cursor-pointer transition-colors hover:bg-muted [&>td]:px-[15px] [&>td]:py-3 [&>td]:align-middle [&>td]:text-[0.9rem]"
      >
        <td>
          <span className="flex items-center gap-2 font-medium">
            <span
              className={`inline-block size-2.5 shrink-0 rounded-full ${
                STATUS_DOT_CLASS[status] ?? "bg-gray-400"
              }`}
            />
            {status}
          </span>
        </td>
        <td>{count}</td>
        <td>{storyPoints || ""}</td>
        <td className="w-5 text-right font-bold text-gray-400">
          {isCollapsed ? ">" : "v"}
        </td>
      </tr>
      {!isCollapsed && (
        <tr>
          <td colSpan="4" className="p-0">
            {isLoading && <div className={LOADING_OR_EMPTY}>Loading...</div>}
            {!isLoading && tasks && (
              <table className="w-full table-fixed border-collapse [&_thead_th]:bg-muted [&_thead_th]:px-[15px] [&_thead_th]:py-2 [&_thead_th]:text-left [&_thead_th]:text-[0.8rem] [&_thead_th]:font-semibold [&_thead_th]:text-muted-foreground">
                <thead>
                  <tr>
                    <th className="w-[15%]">Key</th>
                    <th className="w-[45%]">Title</th>
                    <th className="w-[20%]">Story Points</th>
                    <th className="w-[20%]">Finished Date</th>
                  </tr>
                </thead>
                <tbody>
                  {tasks.map((task, index) => (
                    <TaskDetailRow key={index} task={task} />
                  ))}
                </tbody>
              </table>
            )}
            {!isLoading && (!tasks || tasks.length === 0) && (
              <div className={LOADING_OR_EMPTY}>N/A</div>
            )}
          </td>
        </tr>
      )}
    </>
  );
};

/**
 * Render a table for a single user's Jira data.
 *
 * @param {Object} props
 * @param {User} props.user - User object with name and statusData.
 * @returns {JSX.Element}
 */
const UserTable = ({ user }) => (
  <div
    className="mb-5 overflow-hidden rounded-lg border"
    data-testid="user-table"
  >
    <div className="bg-muted p-[15px]">
      <h4 className="m-0 text-[1.2rem] font-semibold text-foreground">
        {user.name}
      </h4>
    </div>
    <table className="w-full border-collapse [&_thead_th]:bg-muted [&_thead_th]:px-[15px] [&_thead_th]:py-3 [&_thead_th]:text-left [&_thead_th]:text-[0.9rem] [&_thead_th]:font-semibold [&_thead_th]:text-muted-foreground">
      <thead>
        <tr>
          <th>Status</th>
          <th>Count</th>
          <th>Story Points</th>
          <th></th>
        </tr>
      </thead>
      <tbody>
        {user.statusData.map((statusItem, index) => (
          <StatusRow key={index} statusItem={statusItem} />
        ))}
      </tbody>
    </table>
  </div>
);

/**
 * JiraReportTable component.
 *
 * Fetches Jira briefs based on the provided `jiraReportProps` and renders a table
 * showing Jira issue status breakdown for each user.
 *
 * @param {Object} props
 * @param {Object} props.jiraReportProps - Encapsulates all necessary props for the report.
 * @param {Object} props.jiraReportProps.searchParams - Parameters for fetching Jira issues.
 * @param {string} props.jiraReportProps.searchParams.startDate - Start date for filtering issues.
 * @param {string} props.jiraReportProps.searchParams.endDate - End date for filtering issues.
 * @param {string[]} props.jiraReportProps.searchParams.projectIds - List of project IDs to filter.
 * @param {string[]} props.jiraReportProps.searchParams.statusList - List of Jira statuses to filter.
 * @param {string[]} props.jiraReportProps.searchParams.ldaps - List of user LDAPs to include in the report.
 * @param {Object} [props.jiraReportProps.ldapsAndDisplayNames] - Optional mapping from LDAP to display name.
 *
 * @returns {JSX.Element} A table of users and their Jira issue status breakdown,
 * or a loading / "N/A" message if data is unavailable.
 *
 * @example
 * const jiraReportProps = {
 *   searchParams: {
 *     startDate: "2025-09-01",
 *     endDate: "2025-09-10",
 *     projectIds: ["PROJ1", "PROJ2"],
 *     statusList: [JiraIssueStatus.DONE],
 *     ldaps: ["alice", "bob"]
 *   },
 *   ldapsAndDisplayNames: {
 *     alice: "Alice Zhang",
 *     bob: "Bob Li"
 *   }
 * };
 *
 * <JiraReportTable jiraReportProps={jiraReportProps} />
 */

const JiraReportTable = ({ jiraReportProps }) => {
  const [jiraSummaryData, setJiraSummaryData] = useState(null);
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    if (jiraReportProps.searchParams) {
      const fetchJiraSummaryData = async () => {
        setIsLoading(true);
        try {
          const { data: summary } = await getJiraIssueBrief(
            jiraReportProps.searchParams,
          );
          setJiraSummaryData(summary);
        } catch (err) {
          console.error("Failed to fetch Jira summary data:", err);
          setJiraSummaryData(null);
        } finally {
          setIsLoading(false);
        }
      };

      fetchJiraSummaryData();
    }
  }, [jiraReportProps.searchParams]);

  if (isLoading) {
    return <div className={LOADING_OR_EMPTY}>Loading...</div>;
  }

  if (!jiraSummaryData) {
    return <div className={LOADING_OR_EMPTY}>N/A</div>;
  }

  const formattedData = formatJiraBriefsData(
    jiraSummaryData,
    jiraReportProps.ldapsAndDisplayNames,
    jiraReportProps.searchParams.statusList,
  );

  return (
    <div
      className="overflow-hidden rounded-lg text-foreground"
      data-testid="jira-table-container"
    >
      {formattedData.map((user, index) => (
        <UserTable key={index} user={user} />
      ))}
    </div>
  );
};

export default JiraReportTable;
