import { useCallback, useEffect, useId, useRef, useState } from "react";
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
  const containerRef = useRef(null);
  /** Index into `result.hits`, or -1 when nothing is highlighted. */
  const [activeIndex, setActiveIndex] = useState(-1);
  /** Unique per mount (not a hardcoded string), so the combobox wiring below
   * stays correct even if this component is ever mounted twice on one page. */
  const baseId = useId();
  const listboxId = `${baseId}-listbox`;
  const optionId = (applicationId) => `${baseId}-option-${applicationId}`;
  const activeHit =
    activeIndex >= 0 ? (result?.hits?.[activeIndex] ?? null) : null;

  const canSearch = term.trim().length > 0 && !searching;

  // A result set is only meaningful against the board it was searched from.
  useEffect(() => {
    setTerm("");
    setResult(null);
  }, [selectedJobId]);

  const closePanel = useCallback(() => {
    setResult(null);
    setActiveIndex(-1);
  }, []);

  const runSearch = useCallback(async () => {
    if (!canSearch) return;
    setSearching(true);
    try {
      const { data } = await searchBoardApplicants(term.trim(), {
        jobId: allPostings ? null : selectedJobId,
        currentJobId: selectedJobId,
      });
      setResult({ hits: data?.hits ?? [], truncated: !!data?.truncated });
      setActiveIndex(-1);
    } catch (e) {
      // A failed search must never leave a previous term's results on
      // screen behind the error toast — that reads as a match for the
      // term just submitted and invites clicking the wrong person.
      closePanel();
      toast.error(e.message);
    } finally {
      setSearching(false);
    }
  }, [canSearch, term, allPostings, selectedJobId, closePanel]);

  const handleKeyDown = useCallback(
    (e) => {
      const hits = result?.hits ?? [];
      if (e.key === "ArrowDown" && hits.length) {
        e.preventDefault();
        setActiveIndex((i) => (i + 1) % hits.length);
      } else if (e.key === "ArrowUp" && hits.length) {
        e.preventDefault();
        setActiveIndex((i) => (i <= 0 ? hits.length - 1 : i - 1));
      } else if (e.key === "Escape") {
        e.preventDefault();
        closePanel();
        inputRef.current?.focus();
      } else if (e.key === "Enter") {
        // preventDefault also suppresses the native activation of whichever
        // button currently has focus, so Enter can't both open a row and
        // re-trigger Search.
        e.preventDefault();
        // Enter means "open the row I'm on" only while a row is highlighted;
        // otherwise it still means "search".
        if (activeIndex >= 0 && hits[activeIndex]) {
          onSelect(hits[activeIndex].applicationId);
        } else {
          runSearch();
        }
      }
    },
    [result, activeIndex, closePanel, onSelect, runSearch],
  );

  // mousedown, not blur: blur fires before a result row's click and would
  // unmount the row out from under the pointer, swallowing the selection.
  useEffect(() => {
    if (!result) return;
    const onMouseDown = (e) => {
      if (!containerRef.current?.contains(e.target)) closePanel();
    };
    document.addEventListener("mousedown", onMouseDown);
    return () => document.removeEventListener("mousedown", onMouseDown);
  }, [result, closePanel]);

  return (
    // The key handler sits on the container, not the input: after clicking
    // Search the focus is on the button, and Enter/arrows/Escape must keep
    // working from there. Events from every control bubble up to here.
    <div className="relative" ref={containerRef} onKeyDown={handleKeyDown}>
      <div className="flex items-center gap-2">
        <input
          ref={inputRef}
          type="text"
          role="combobox"
          aria-autocomplete="list"
          aria-expanded={!!result}
          aria-controls={listboxId}
          aria-activedescendant={
            activeHit ? optionId(activeHit.applicationId) : undefined
          }
          value={term}
          placeholder="Search by name or email"
          onChange={(e) => {
            setTerm(e.target.value);
            // Clearing the box is a dismissal, not an edit.
            if (e.target.value.trim() === "") closePanel();
          }}
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
          {/* Rendered whenever the panel is open, hits or not, so
              aria-controls on the input always names an element that
              actually exists in the DOM. "No matches" is a sibling, never a
              child: role="listbox" children must be options, and arbitrary
              text in there would trade one ARIA problem for another. When
              empty, py-1 is dropped so the listbox contributes no height —
              otherwise it would render as blank space above "No matches". */}
          {/* No <ul>/<li> wrappers: an element with role="option" must be a
              direct child of the role="listbox", and a <li> in between
              breaks that relationship. */}
          <div
            role="listbox"
            id={listboxId}
            className={`max-h-80 overflow-y-auto ${
              result.hits.length > 0 ? "py-1" : ""
            }`}
          >
            {result.hits.map((h, index) => (
              <button
                key={h.applicationId}
                id={optionId(h.applicationId)}
                type="button"
                role="option"
                aria-selected={index === activeIndex}
                data-application-id={String(h.applicationId)}
                onClick={() => onSelect(h.applicationId)}
                className={`w-full px-3 py-2 text-left hover:bg-slate-50 ${
                  index === activeIndex ? "bg-slate-100" : ""
                }`}
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
          {result.hits.length === 0 && (
            <p
              role="status"
              className="px-3 py-2 text-sm text-muted-foreground"
            >
              No matches
            </p>
          )}
          {result.truncated && (
            <p className="border-t border-border px-3 py-2 text-xs text-muted-foreground">
              Showing first {result.hits.length} matches — refine your search
            </p>
          )}
        </div>
      )}
    </div>
  );
};

export default ApplicantSearch;
