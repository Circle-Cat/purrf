import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";

/**
 * Pick who a new email goes to from a fixed list; addresses cannot be typed.
 * What is ticked is reported in the order of `options`.
 *
 * @param {{options: {address: string, label: string|null}[],
 *          selected: string[], onChange: (next: string[]) => void,
 *          idPrefix?: string}} props
 */
const RecipientPicker = ({
  options,
  selected,
  onChange,
  idPrefix = "email-to",
}) => {
  const toggle = (address, checked) =>
    onChange(
      options
        .map((option) => option.address)
        .filter((a) => (a === address ? checked : selected.includes(a))),
    );
  return (
    <fieldset className="space-y-1">
      <legend className="text-sm font-medium">To</legend>
      {options.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          No email address on file.
        </p>
      ) : (
        options.map((option, index) => {
          const id = `${idPrefix}-${index}`;
          return (
            <div key={option.address} className="flex items-center gap-2">
              <Checkbox
                id={id}
                checked={selected.includes(option.address)}
                onCheckedChange={(checked) =>
                  toggle(option.address, checked === true)
                }
              />
              <Label htmlFor={id} className="font-normal">
                {option.address}
                {option.label ? (
                  <span className="text-muted-foreground">
                    ({option.label})
                  </span>
                ) : null}
              </Label>
            </div>
          );
        })
      )}
    </fieldset>
  );
};

export default RecipientPicker;
