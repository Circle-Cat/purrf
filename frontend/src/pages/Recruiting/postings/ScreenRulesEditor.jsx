import { Button } from "@/components/ui/button";
import TermHint from "@/pages/Recruiting/components/TermHint";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import FieldError from "@/components/common/FieldError";
import { errorBorder } from "@/components/common/fieldErrors";
import DomainsInput from "@/pages/Recruiting/postings/DomainsInput";
import { ruleKey } from "@/pages/Recruiting/postings/postingValidation";

const ACTIONS = ["reject", "qualify", "auto_hire"];
const EMAIL_MODES = [
  { value: "include", label: "Include" },
  { value: "exclude", label: "Exclude" },
];

/** Next unique rule id (r1, r2, …) given existing rules. */
const nextRuleId = (rules) => {
  const nums = rules
    .map((r) => /^r(\d+)$/.exec(r.id)?.[1])
    .filter(Boolean)
    .map(Number);
  return `r${(nums.length ? Math.max(...nums) : 0) + 1}`;
};

/**
 * Build an email_domain condition from the field's domain tags.
 *
 * A single domain is still emitted as a one-element `in` list rather than the
 * `equals` + string the editor used to produce: `screen_rules._email_domain_
 * matches` treats them identically, and one shape means the tag field's array
 * is the condition's value with no branch in between.
 */
const domainsToCondition = (domains, mode) => ({
  source: "email_domain",
  operator: mode === "exclude" ? "not_in" : "in",
  value: domains,
});

/**
 * A condition's domains as a list.
 *
 * Still reads the `equals` + string shape the editor no longer writes. The
 * backend contract is unchanged — `ScreenRuleConditionDto` accepts it and the
 * seed script produces it — so a rule in that shape must load as a tag rather
 * than render blank and be wiped by the next save.
 */
const conditionToDomains = (cond) =>
  Array.isArray(cond.value) ? cond.value : cond.value ? [cond.value] : [];

/** Whether a condition's operator represents "include" or "exclude". */
const conditionMode = (cond) =>
  cond.operator === "not_in" ? "exclude" : "include";

const ActionSelect = ({ label, value, onChange }) => (
  <Select value={value} onValueChange={onChange}>
    <SelectTrigger aria-label={label} className="w-32">
      <SelectValue />
    </SelectTrigger>
    <SelectContent>
      {ACTIONS.map((a) => (
        <SelectItem key={a} value={a}>
          {a}
        </SelectItem>
      ))}
    </SelectContent>
  </Select>
);

/**
 * Machine-screening rules editor: a list of email-domain rules plus a list
 * of single_choice answer rules. Produces backend-shaped screen_rules.
 *
 * @param {{value: {rules: object[]}, onChange: (next: object) => void,
 *          questions: object[]}} props
 */
const ScreenRulesEditor = ({
  value = { rules: [] },
  onChange,
  questions = [],
  errors = {},
}) => {
  // Fully controlled: derive from `value` so the editor always reflects the
  // loaded posting. (Holding a local copy in useState went stale when the
  // parent's value arrived after mount, silently wiping saved rules on edit.)
  const rules = value.rules ?? [];

  const emailRules = rules.filter((r) => r.condition.source === "email_domain");
  const answerRules = rules.filter((r) => r.condition.source === "answer");
  const singleChoice = questions.filter((q) => q.type === "single_choice");

  const emit = (nextRules) => onChange({ ...value, rules: nextRules });

  const addEmailRule = () =>
    emit([
      ...rules,
      {
        id: nextRuleId(rules),
        condition: { source: "email_domain", operator: "in", value: [] },
        action: "qualify",
      },
    ]);
  const patchEmailRule = (rule, fields) =>
    emit(rules.map((r) => (r === rule ? { ...r, ...fields } : r)));

  const addAnswerRule = () =>
    emit([
      ...rules,
      {
        id: nextRuleId(rules),
        condition: {
          source: "answer",
          operator: "equals",
          questionId: "",
          value: "",
        },
        action: "reject",
      },
    ]);
  const patchAnswer = (rule, fields) =>
    emit(rules.map((r) => (r === rule ? { ...r, ...fields } : r)));
  const removeRule = (rule) => emit(rules.filter((r) => r !== rule));

  return (
    <div className="space-y-3">
      <p className="text-sm font-medium text-slate-700">
        <TermHint id="editor.screening" />
      </p>

      <div className="space-y-2">
        {emailRules.map((rule) => (
          <div
            key={rule.id}
            className="flex flex-wrap items-center gap-3 rounded-md border border-slate-200 p-3"
          >
            <Select
              value={conditionMode(rule.condition)}
              onValueChange={(mode) =>
                patchEmailRule(rule, {
                  condition: domainsToCondition(
                    conditionToDomains(rule.condition),
                    mode,
                  ),
                })
              }
            >
              <SelectTrigger aria-label="Email domain mode" className="w-28">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {EMAIL_MODES.map((m) => (
                  <SelectItem key={m.value} value={m.value}>
                    {m.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <div className="flex items-start gap-2 text-sm">
              {/* Not a <Label>: the field is a tag list wrapping its own input,
                  which already carries the accessible name. */}
              <span className="pt-2">Domains</span>
              <DomainsInput
                value={conditionToDomains(rule.condition)}
                invalid={Boolean(errors?.[ruleKey(rule.id, "value")])}
                onChange={(domains) =>
                  patchEmailRule(rule, {
                    condition: domainsToCondition(
                      domains,
                      conditionMode(rule.condition),
                    ),
                  })
                }
              />
            </div>
            <ActionSelect
              label="Email domain action"
              value={rule.action}
              onChange={(action) => patchEmailRule(rule, { action })}
            />
            <Button
              type="button"
              variant="outline"
              size="sm"
              aria-label="Remove email domain rule"
              onClick={() => removeRule(rule)}
            >
              Remove
            </Button>
            {/* w-full so flex-wrap drops the message onto its own line under
                the controls rather than squeezing it in beside them. */}
            <div className="w-full">
              <FieldError
                errors={errors}
                errorKey={ruleKey(rule.id, "value")}
              />
            </div>
          </div>
        ))}
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={addEmailRule}
        >
          Add email domain rule
        </Button>
      </div>

      <div className="space-y-2">
        {answerRules.map((rule) => {
          const q = singleChoice.find(
            (x) => x.id === rule.condition.questionId,
          );
          return (
            <div
              key={rule.id}
              className="flex flex-wrap items-center gap-3 rounded-md border border-slate-200 p-3"
            >
              <Select
                value={rule.condition.questionId || undefined}
                onValueChange={(qid) =>
                  patchAnswer(rule, {
                    condition: {
                      ...rule.condition,
                      questionId: qid,
                      value: "",
                    },
                  })
                }
              >
                <SelectTrigger
                  aria-label="Answer rule question"
                  className={`max-w-xs${errorBorder(errors, ruleKey(rule.id, "questionId"))}`}
                >
                  <SelectValue placeholder="Question" />
                </SelectTrigger>
                <SelectContent>
                  {singleChoice.map((sc) => (
                    <SelectItem key={sc.id} value={sc.id}>
                      {sc.label || sc.id}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Select
                value={rule.condition.value || undefined}
                onValueChange={(val) =>
                  patchAnswer(rule, {
                    condition: { ...rule.condition, value: val },
                  })
                }
              >
                <SelectTrigger
                  aria-label="Answer rule value"
                  className={`max-w-xs${errorBorder(errors, ruleKey(rule.id, "value"))}`}
                >
                  <SelectValue placeholder="Value" />
                </SelectTrigger>
                <SelectContent>
                  {(q?.options ?? []).map((opt) => (
                    <SelectItem key={opt} value={opt}>
                      {opt}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <ActionSelect
                label="Answer rule action"
                value={rule.action}
                onChange={(action) => patchAnswer(rule, { action })}
              />
              <Button
                type="button"
                variant="outline"
                size="sm"
                aria-label="Remove answer rule"
                onClick={() => removeRule(rule)}
              >
                Remove
              </Button>
              <div className="w-full">
                <FieldError
                  errors={errors}
                  errorKey={ruleKey(rule.id, "questionId")}
                />
                <FieldError
                  errors={errors}
                  errorKey={ruleKey(rule.id, "value")}
                />
              </div>
            </div>
          );
        })}
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={addAnswerRule}
        >
          Add answer rule
        </Button>
      </div>
    </div>
  );
};

export default ScreenRulesEditor;
