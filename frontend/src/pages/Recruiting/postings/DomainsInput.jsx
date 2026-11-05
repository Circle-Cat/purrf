import { useRef, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

/**
 * A hostname: at least two dot-separated labels, each of which may contain
 * hyphens but may not start or end with one. Deliberately loose — it exists to
 * catch `localhost`, `@google.com` and `https://google.com/`, not to police
 * TLDs.
 */
const DOMAIN_PATTERN =
  /^[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)+$/;

const INVALID_MESSAGE = "Enter a domain like google.com";
const DUPLICATE_MESSAGE = "Already added";

/** Commas and any run of whitespace both separate domains in pasted text. */
const PASTE_SEPARATORS = /[,\s]+/;

/**
 * Normalize one typed/pasted domain and say whether it can be added.
 *
 * Lowercasing is not cosmetic: `screen_rules.py` lowercases the candidate's
 * email domain before comparing, so a stored `Google.COM` would never match
 * anything — a rule that looks configured but silently does nothing.
 *
 * @param {string} raw The text as typed or pasted.
 * @param {string[]} existing Domains already held, used for the duplicate check.
 * @returns {{domain: string|null, error: string|null}} The normalized domain
 *   when it can be added, otherwise the message explaining why it cannot.
 */
const normalizeDomain = (raw, existing) => {
  const domain = raw.trim().toLowerCase();
  if (!domain) return { domain: null, error: null };
  if (!DOMAIN_PATTERN.test(domain)) {
    return { domain: null, error: INVALID_MESSAGE };
  }
  if (existing.includes(domain)) {
    return { domain: null, error: DUPLICATE_MESSAGE };
  }
  return { domain, error: null };
};

/**
 * The email-domain field of a machine-screening rule, as removable tags.
 *
 * Replaces a single comma-separated text input whose value was re-derived from
 * the parsed domains on every keystroke, which made a trailing comma vanish in
 * the same frame and left pasting as the only way to enter a second domain.
 * Here the typed text lives in local state and nothing rewrites it, so the
 * separator is a key the component acts on rather than a character the model
 * has to survive.
 *
 * Five things commit the pending text: Enter, a typed comma, the Add button,
 * blur, and a paste (split on commas and whitespace). Blur is what covers a
 * recruiter who types a domain and clicks Save without pressing Enter — the
 * browser blurs the focused input before the click lands, so the tag exists by
 * the time the form reads its value. Pending text that is *not* a valid domain
 * stays in the box with its error and is lost if the posting is saved anyway;
 * catching that would mean plumbing this component's draft up to the form, for
 * a string the backend would reject regardless.
 *
 * @param {{value: string[],
 *          onChange: (next: string[]) => void,
 *          invalid?: boolean}} props `value` is the rule's domains, in order;
 *   `invalid` draws the error border for a rule-level validation failure
 *   reported by the parent (this component reports its own errors separately).
 */
const DomainsInput = ({ value = [], onChange, invalid = false }) => {
  const [draft, setDraft] = useState("");
  const [error, setError] = useState(null);
  const inputRef = useRef(null);

  /**
   * Commit the pending text as a tag, or leave it in place with an error.
   * Blank text is a silent no-op so blur and the Add button can both fire
   * against an already-empty box.
   */
  const commitDraft = () => {
    const { domain, error: why } = normalizeDomain(draft, value);
    if (why) {
      setError(why);
      return;
    }
    if (!domain) return;
    setError(null);
    setDraft("");
    onChange([...value, domain]);
  };

  const handleKeyDown = (event) => {
    if (event.key !== "Enter" && event.key !== ",") return;
    // Enter would submit the surrounding form; a comma would land in the box
    // as a character. Both mean "that's one domain" here.
    event.preventDefault();
    commitDraft();
  };

  /**
   * Take every separable segment of the pasted text. Valid segments all become
   * tags rather than stopping at the first bad one, and the first bad segment
   * is left in the box so it can be corrected in place.
   */
  const handlePaste = (event) => {
    const text = event.clipboardData?.getData("text") ?? "";
    if (!text.trim()) return;
    event.preventDefault();
    const added = [];
    let rejected = null;
    let rejectedError = null;
    text
      .split(PASTE_SEPARATORS)
      .filter(Boolean)
      .forEach((segment) => {
        const { domain, error: why } = normalizeDomain(segment, [
          ...value,
          ...added,
        ]);
        if (domain) {
          added.push(domain);
        } else if (why && rejected === null) {
          rejected = segment;
          rejectedError = why;
        }
      });
    setDraft(rejected ?? "");
    setError(rejectedError);
    if (added.length) onChange([...value, ...added]);
  };

  // Keyed on the domain, never on the index: clicking a tag's × first blurs
  // the input, which may commit a pending domain and shift every later index
  // before the click is delivered.
  const removeDomain = (domain) => onChange(value.filter((d) => d !== domain));

  return (
    <div className="w-64">
      <div className="flex items-start gap-1">
        <div
          className={cn(
            "flex min-h-9 flex-1 flex-wrap items-center gap-1 rounded-md border border-input bg-transparent px-2 py-1 shadow-xs",
            invalid && "border-destructive",
          )}
          onClick={() => inputRef.current?.focus()}
          role="presentation"
        >
          {value.map((domain) => (
            <Badge key={domain} variant="secondary" className="gap-1">
              {domain}
              <button
                type="button"
                aria-label={`Remove ${domain}`}
                className="text-muted-foreground hover:text-foreground"
                onClick={() => removeDomain(domain)}
              >
                ×
              </button>
            </Badge>
          ))}
          <input
            ref={inputRef}
            aria-label="Email domains"
            className="min-w-24 flex-1 bg-transparent text-sm outline-none placeholder:text-muted-foreground"
            placeholder={value.length ? "" : "google.com"}
            value={draft}
            onChange={(e) => {
              setDraft(e.target.value);
              setError(null);
            }}
            onKeyDown={handleKeyDown}
            onBlur={commitDraft}
            onPaste={handlePaste}
          />
        </div>
        <Button
          type="button"
          variant="outline"
          size="sm"
          aria-label="Add domain"
          onClick={commitDraft}
        >
          Add
        </Button>
      </div>
      {error && (
        <span role="alert" className="mt-1 block text-xs text-destructive">
          {error}
        </span>
      )}
    </div>
  );
};

export default DomainsInput;
