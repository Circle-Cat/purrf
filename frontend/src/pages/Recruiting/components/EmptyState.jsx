/**
 * The explanation shown where a list has nothing in it, in three parts: what
 * appears here, how it gets here, and who makes that happen. All three are
 * required, and that is the component's value — an author who cannot answer
 * all three has not worked out why the page is empty, and a reader told only
 * "no results" learns nothing they can act on.
 *
 * @param {object} props
 * @param {string} props.what What will appear in this space.
 * @param {string} props.how The action that puts something here.
 * @param {string} props.who Who performs that action.
 * @param {import("react").ReactNode} [props.action] A control for a reader who
 *          can advance things themselves.
 * @returns {JSX.Element}
 */
const EmptyState = ({ what, how, who, action }) => (
  <div className="space-y-2 rounded-lg border border-dashed border-slate-200 p-6">
    <p className="text-sm font-medium text-slate-900">{what}</p>
    <p className="text-sm text-slate-600">{how}</p>
    <p className="text-sm text-slate-500">{who}</p>
    {action && <div className="pt-2">{action}</div>}
  </div>
);

export default EmptyState;
