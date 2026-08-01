import { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { searchBoardApplicants } from "@/api/recruitingApi";
import { stageLabel } from "@/pages/Recruiting/board/stageFormat";

/**
 * Applicant search for the board header: type a name or email, press Search,
 * pick someone, land on their application.
 *
 * Deliberately explicit-trigger — no search-as-you-type. Every request is one
 * the owner asked for, which also means there are no in-flight races to
 * reconcile and no debounce to tune.
 *
 * The panel navigates to the application detail page rather than scrolling to
 * the applicant's card: a card sitting in an unloaded terminal-lane page
 * cannot be located reliably (BoardPage's `?focus=` hunt is bounded and is
 * allowed to fail), and an explicit request must not have a "might not find
 * it" outcome. PR #320's BackToBoardLink covers the trip back.
 *
 * All state lives here. BoardPage already juggles the jobId param, the focus
 * param, terminal-lane paging and the focus hunt; none of this belongs there.
 *
 * @param {{
 *   selectedJobId: number|null,
 *   onSelect: (applicationId: number) => void,
 * }} props
 */
const ApplicantSearch = ({ selectedJobId, onSelect }) => {
  const [term, setTerm] = useState("");
  const [allPostings, setAllPostings] = useState(false);
  /** null = never searched (panel closed); otherwise the last response. */
  const [result, setResult] = useState(null);
  const [searching, setSearching] = useState(false);
  const inputRef = useRef(null);

  const canSearch = term.trim().length > 0 && !searching;

  // A result set is only meaningful against the board it was searched from.
  useEffect(() => {
    setTerm("");
    setResult(null);
  }, [selectedJobId]);

  const runSearch = useCallback(async () => {
    if (!canSearch) return;
    setSearching(true);
    try {
      const { data } = await searchBoardApplicants(term.trim(), {
        jobId: allPostings ? null : selectedJobId,
        currentJobId: selectedJobId,
      });
      setResult({ hits: data?.hits ?? [], truncated: !!data?.truncated });
    } catch (e) {
      toast.error(e.message);
    } finally {
      setSearching(false);
    }
  }, [canSearch, term, allPostings, selectedJobId]);

  const handleKeyDown = useCallback(
    (e) => {
      if (e.key === "Enter") {
        e.preventDefault();
        runSearch();
      }
    },
    [runSearch],
  );

  return (
    // The key handler sits on the container, not the input: after clicking
    // Search the focus is on the button, and Enter/arrows/Escape must keep
    // working from there. Events from every control bubble up to here.
    <div className="relative" onKeyDown={handleKeyDown}>
      <div className="flex items-center gap-2">
        <input
          ref={inputRef}
          type="text"
          value={term}
          placeholder="Search by name or email"
          onChange={(e) => setTerm(e.target.value)}
          className="h-9 w-64 rounded-md border border-border px-3 text-sm"
        />
        <button
          type="button"
          onClick={runSearch}
          disabled={!canSearch}
          className="h-9 rounded-md border border-border px-3 text-sm font-medium hover:bg-muted disabled:cursor-not-allowed disabled:opacity-50"
        >
          Search
        </button>
        <label className="flex items-center gap-1.5 text-sm text-muted-foreground">
          <input
            type="checkbox"
            checked={allPostings}
            onChange={(e) => setAllPostings(e.target.checked)}
            className="h-4 w-4"
          />
          All postings
        </label>
      </div>

      {result && (
        <div className="absolute left-0 top-11 z-20 w-96 rounded-lg border border-border bg-white shadow-lg">
          {result.hits.length === 0 ? (
            <p className="px-3 py-2 text-sm text-muted-foreground">No matches</p>
          ) : (
            // No <ul>/<li> wrappers: an element with role="option" must be a
            // direct child of the role="listbox", and a <li> in between
            // breaks that relationship.
            <div role="listbox" className="max-h-80 overflow-y-auto py-1">
              {result.hits.map((h) => (
                <button
                  key={h.applicationId}
                  type="button"
                  role="option"
                  aria-selected="false"
                  data-application-id={String(h.applicationId)}
                  onClick={() => onSelect(h.applicationId)}
                  className="w-full px-3 py-2 text-left hover:bg-slate-50"
                >
                  <p className="text-sm font-medium text-slate-900">
                    {h.applicantName}
                  </p>
                  <p className="text-xs text-slate-500">
                    {[
                      h.applicantEmail,
                      allPostings ? h.jobTitle : null,
                      stageLabel(h.stage, h.jobKind),
                    ]
                      .filter(Boolean)
                      .join(" · ")}
                  </p>
                </button>
              ))}
            </div>
          )}
          {result.truncated && (
            <p className="border-t border-border px-3 py-2 text-xs text-muted-foreground">
              Showing first 20 matches — refine your search
            </p>
          )}
        </div>
      )}
    </div>
  );
};

export default ApplicantSearch;
