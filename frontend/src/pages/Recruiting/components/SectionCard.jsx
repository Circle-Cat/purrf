/**
 * A titled card: a header bar with the title on the left and anything the
 * section needs (a count, a filter, a button) on the right. The body is
 * unpadded so a list inside it can run its row dividers edge to edge; rows
 * pad themselves with px-5 to line up with the title.
 *
 * @param {{title: string, right?: import("react").ReactNode,
 *          children: import("react").ReactNode}} props
 */
const SectionCard = ({ title, right, children }) => (
  <section className="rounded-lg border border-slate-200 bg-white">
    <header className="flex items-center gap-3 border-b border-slate-200 px-5 py-3">
      <h2 className="text-sm font-semibold">{title}</h2>
      {right && <div className="ml-auto flex items-center gap-3">{right}</div>}
    </header>
    {children}
  </section>
);

export default SectionCard;
