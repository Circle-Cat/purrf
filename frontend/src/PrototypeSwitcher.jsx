import { useEffect, useState } from "react";
import RecruitingPrototype from "@/pages/RecruitingPrototype";
import LeavePrototype from "@/pages/LeavePrototype";

/** The prototypes the static Pages bundle serves, in tab order. */
const PROTOTYPES = [
  {
    hash: "recruiting",
    label: "Recruiting v2",
    Component: RecruitingPrototype,
  },
  { hash: "leave", label: "Leave & PTO", Component: LeavePrototype },
];

/** Which prototype the current URL hash selects, defaulting to the first. */
const fromHash = () => {
  const key = window.location.hash.replace("#", "");
  return PROTOTYPES.some((p) => p.hash === key) ? key : PROTOTYPES[0].hash;
};

/**
 * PrototypeSwitcher
 *
 * Top-level chrome for the static GitHub Pages build, which serves more than
 * one prototype from a single deploy.
 *
 * There is no router in that bundle, so the hash is the only thing that can
 * carry a deep link — which matters, because the point of the Pages build is
 * handing someone a URL that opens on the prototype you meant.
 *
 * @returns {JSX.Element}
 */
const PrototypeSwitcher = () => {
  const [current, setCurrent] = useState(fromHash);

  useEffect(() => {
    const sync = () => setCurrent(fromHash());
    window.addEventListener("hashchange", sync);
    return () => window.removeEventListener("hashchange", sync);
  }, []);

  const { Component } = PROTOTYPES.find((p) => p.hash === current);

  return (
    <div className="min-h-screen flex flex-col">
      <div className="flex items-center gap-1 px-4 py-2 bg-slate-900 text-slate-300 text-sm">
        <span className="mr-3 text-xs uppercase tracking-wide text-slate-500">
          Prototype
        </span>
        {PROTOTYPES.map((p) => (
          <a
            key={p.hash}
            href={`#${p.hash}`}
            className={`px-3 py-1 rounded-md transition-colors ${
              p.hash === current
                ? "bg-slate-700 text-white"
                : "hover:bg-slate-800"
            }`}
          >
            {p.label}
          </a>
        ))}
        <span className="ml-auto text-xs text-slate-500">
          Mock data · refreshing resets everything
        </span>
      </div>
      <div className="flex-1 min-h-0">
        <Component />
      </div>
    </div>
  );
};

export default PrototypeSwitcher;
