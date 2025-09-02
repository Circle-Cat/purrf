import { useMemo, useState } from "react";
import "./Tab.css";

/** Lightweight inline SVG icons (no deps) */
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

export default function Tab() {
  const [active, setActive] = useState(0);

  const tabs = useMemo(
    () => [
      {
        id: "tab-chat",
        label: "Chat",
        headers: ["LDAP", "CHAT SPACE", "COUNT"],
        icon: <IconChat />,
      },
      {
        id: "tab-jira",
        label: "Jira",
        headers: ["LDAP", "PROJECT", "STATUS"],
        icon: <IconJira />,
      },
      {
        id: "tab-gerrit",
        label: "Gerrit",
        headers: ["LDAP", "PROJECT", "CL COUNT"],
        icon: <IconGerrit />,
      },
      {
        id: "tab-calendar",
        label: "Calendar",
        headers: ["LDAP", "CALENDAR", "ATTENDANCE"],
        icon: <IconCalendar />,
      },
    ],
    [],
  );

  const emptyRowCount = 8;

  return (
    <div className="purrf-tabs" data-testid="tab-component">
      <div className="tablist" role="tablist" aria-label="Purrf Data Sources">
        {tabs.map((t, idx) => (
          <button
            key={t.id}
            id={t.id}
            role="tab"
            className={`tab-pill ${active === idx ? "active" : ""}`}
            aria-selected={active === idx}
            aria-controls={`panel-${idx}`}
            tabIndex={active === idx ? 0 : -1}
            onClick={() => setActive(idx)}
            data-testid={`tab-button-${idx}`}
            type="button"
          >
            <span className="tab-icon" aria-hidden="true">
              {t.icon}
            </span>
            {t.label}
            {active === idx && (
              <span className="active-underline" aria-hidden="true" />
            )}
          </button>
        ))}
      </div>

      {tabs.map((t, idx) => (
        <div
          key={`panel-${idx}`}
          id={`panel-${idx}`}
          role="tabpanel"
          aria-labelledby={t.id}
          hidden={active !== idx}
          className="tabpanel"
          data-testid={`tab-panel-${idx}`}
        >
          <div className="table-wrap">
            <table className="tab-table" data-testid={`tab-table-${idx}`}>
              <thead>
                <tr>
                  {t.headers.map((h) => (
                    <th key={h} scope="col">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {Array.from({ length: emptyRowCount }).map((_, rIdx) => (
                  <tr key={`empty-${idx}-${rIdx}`} className="empty-row">
                    {t.headers.map((_, cIdx) => (
                      <td
                        key={`cell-${idx}-${rIdx}-${cIdx}`}
                        aria-label="empty-cell"
                      >
                        &nbsp;
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ))}
    </div>
  );
}
