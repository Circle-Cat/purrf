# Email Templates Prototype

A read-only catalog of every email Purrf sends from content written in code,
with a rendered preview of each one. It is meant for system admins who hold a
new `ops.alert` permission. Everything is mock data, and refreshing resets the
page.

Open it at `#email-templates`.

## What's in it

28 templates in two kinds, plus 2 greyed **Planned** entries that show the list
will grow.

| Kind      | Count | Source                                                                                                                                          |
| --------- | ----: | ----------------------------------------------------------------------------------------------------------------------------------------------- |
| Manual    |     8 | `backend/communication/email_templates.py`, copied verbatim. Staff pick these in the compose box.                                               |
| Automatic |    20 | Every notification renderer in `backend/{recruiting,mentorship,user_identity}/notification_renderers.py`: 15 recruiting, 2 mentorship, 3 users. |

Automatic templates are counted per renderer function, not per event type.
`_render_assigned_to_evaluate` serves two events (`recruiting.reassigned` and
`recruiting.auto_assigned`). It is registered by a plain call rather than the
`@register_render` decorator, which is why a count of decorators finds 19.

Where a renderer picks between different bodies (submitted vs. auto-hired,
approved vs. rejected, round open vs. not, run finished vs. failed), the preview
shows each one as a variant.

Each entry shows:

- name and key
- service
- send mode
- trigger and recipients (automatic only)
- sender alias
- subject and body preview
- placeholders (manual only)

Recipients come from the `@register_recipients` resolvers in each domain. The
person who caused an event is never among them, because the pipeline removes
the actor before sending. A small **?** marks a reading that hasn't been
checked against the write site.

## Previews

- **Manual** templates fill `{{candidate_name}}`, `{{position_title}}` and
  `{{sender_name}}` with sample values. _Show placeholders_ shows them raw
  instead. `[UPPERCASE]` markers are free text the sender writes before
  sending, and they are highlighted in yellow.
- **Automatic** previews are what each renderer would produce for one made-up
  event. Every name uses invented people and example.com addresses.
- Bodies are sanitized with DOMPurify before they are rendered.

## Fixed vs. draft

| Decision                                                        | Status                      |
| --------------------------------------------------------------- | --------------------------- |
| Catalog is read-only and generated from code, not editable      | Proposal                    |
| Gated on a new `ops.alert` permission                           | Proposal                    |
| Sender per service: `recruiting@` / `mentorship@`               | Proposal                    |
| Users (block-request) mail sender `notifications@circlecat.org` | **Draft**: alias TBD        |
| The two planned inbox reminders, and who they go to             | **Draft**: not designed yet |

Not listed: Auth0 sign-in codes and email verification. Those are configured in
the Auth0 dashboard, not in Purrf code.

## Structure

| File                  | Responsibility                                             |
| --------------------- | ---------------------------------------------------------- |
| `index.jsx`           | Header, count, filters, search, layout                     |
| `TemplateList.jsx`    | Rows grouped by service                                    |
| `TemplatePreview.jsx` | Metadata, variants, placeholder toggle, email-like preview |
| `templateView.js`     | Search, placeholder discovery, preview HTML and sanitizing |
| `mockData.js`         | The templates, sample values and sender aliases            |
