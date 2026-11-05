/**
 * Occupies the place a control would be, saying why it is not there and who
 * holds the next move. It renders in the control's own position rather than as
 * a banner at the top of the page: a reader who thinks the buttons vanished is
 * looking at that spot, not at the page heading.
 *
 * @param {object} props
 * @param {string} props.headline The state the subject is in.
 * @param {string} [props.waitingOn] Name of the person the next move belongs to.
 * @param {string} [props.detail] What that means for the reader meanwhile.
 * @returns {JSX.Element}
 */
const PendingNotice = ({ headline, waitingOn, detail }) => (
  <div className="flex flex-wrap items-center gap-x-2 gap-y-1 rounded border border-slate-200 bg-slate-50 px-3 py-2">
    <span className="text-sm font-medium text-slate-700">{headline}</span>
    {waitingOn && (
      <span className="text-sm text-slate-600">{`Waiting on ${waitingOn}.`}</span>
    )}
    {detail && <span className="text-sm text-slate-500">{detail}</span>}
  </div>
);

export default PendingNotice;
