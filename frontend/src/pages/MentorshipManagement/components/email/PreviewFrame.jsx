export default function PreviewFrame({ html }) {
  // No scripts and no same-origin: the HTML comes from Kit and is shown as-is,
  // Liquid tags included, exactly as it will be sent.
  return (
    <iframe
      title="Email preview"
      sandbox=""
      srcDoc={html}
      className="h-[900px] w-full max-w-[680px] rounded border bg-white"
    />
  );
}
