"""Code-preset outbound email templates (no UI CRUD).

Domain-agnostic: this module owns the template *text* and a pure renderer.
Resolving placeholder *values* (who the candidate is, which posting they
applied to) is the caller's job — see
``BoardService.list_application_email_templates`` for the recruiting caller.

Placeholder model (three classes, per the templates spec):
  1. ``{{candidate_name}}`` / ``{{position_title}}`` — scenario data, auto-filled.
  2. ``{{sender_name}}`` — the sending advancer, auto-filled.
  3. ``[UPPERCASE]`` — free text the sender fills in before sending. This
     module never touches bracket markers; they survive rendering verbatim.
"""

import html
import re
from dataclasses import dataclass
from typing import Mapping

ONBOARDING_FORM_URL = (
    "https://docs.google.com/forms/d/e/"
    "1FAIpQLSdlc-oaOg6I2Cj3jDgV66qeHzEcy0_AmWT8n_-urAucFV3hvA/viewform"
)

PLACEHOLDER_KEYS = frozenset({"candidate_name", "position_title", "sender_name"})

_PLACEHOLDER_RE = re.compile(r"\{\{(\w+)\}\}")

# No "--" opening line: the sig-delimiter convention is "-- " with a trailing
# space, so the bare version never read as one to any mail client and no client
# collapsed the block out of a quoted reply. All it added was a stray line.
_SIGNATURE = (
    "<p>Best,<br><strong>{{sender_name}}</strong><br>"
    "Director of People Operations<br>Circle Cat Inc</p>"
)


@dataclass(frozen=True)
class EmailTemplate:
    """One preset template.

    Attributes:
        key (str): Stable identifier, also the API/UI value.
        label (str): English label for the compose dropdown.
        subject (str): Subject line, placeholder-free so thread titles stay
            stable. Taken from the spec's catalog table verbatim.
        body_html (str): Body as restricted HTML (``<p> <br> <ul> <li> <a>``).
    """

    key: str
    label: str
    subject: str
    body_html: str


_SCREENING_PASSED_CULTURAL_INVITE = EmailTemplate(
    key="screening_passed_cultural_invite",
    label="Screening passed - request behavioral interview availability",
    subject="Circle Cat Program - Interview Availability",
    body_html=(
        "<p>Dear {{candidate_name}},</p>"
        "<p>I received your application from a colleague for {{position_title}} and we're "
        "definitely interested in speaking with you! Our typical interview process consists of a round "
        "of cultural and value interview and a round of technical interview (if you are applying for "
        "Software or Course design role) with individuals from different teams. Let me know if you have "
        "any questions in the meantime!</p>"
        "<p><strong>What's next?</strong></p>"
        "<p>Before we can schedule your interview, please provide your availability for a 45-minute "
        "cultural and value phone interview. We can schedule the interview from 9PM to 4AM ET. Please "
        "provide 5-6 dates/times over the next 1-2 weeks that will work for your schedule.</p>"
        "<p><strong>Accommodations</strong></p>"
        "<p>It's important to us to create an accessible, inclusive workplace for everyone, so please do "
        "not hesitate to contact me if you need any accommodations for your interviews. We will then "
        "connect with you to confidentially discuss your options.</p>"
        "<p><strong>What equipment will I need?</strong></p>"
        "<p>You'll need a computer with internet access.<br>"
        "This interview will take place over the Google Meet.</p>"
        "<p>In the meantime, please let me know if you have any questions.</p>"
        + _SIGNATURE
    ),
)

_CULTURAL_INTERVIEW_SCHEDULED = EmailTemplate(
    key="cultural_interview_scheduled",
    label="Behavioral interview scheduled",
    subject="Your Circle Cat Behavioral Interview is Scheduled",
    body_html=(
        "<p>Dear {{candidate_name}},</p>"
        "<p>Thank you for your patience while we sort things out. We are looking forward to speaking with "
        "you! Your interview has been scheduled for [INTERVIEW DATE/TIME].</p>"
        "<p>You will receive a Google Meet invitation in a separate email shortly. Please accept that "
        "invite to confirm your attendance and to ensure the link is saved to your calendar.</p>"
        "<p>This round of interview is similar to a traditional behavioral round interview, where you can "
        "expect questions about your past experiences, work style, etc.</p>"
        "<p>If you need any accommodations or a schedule adjustment, please reply to this email and let us "
        "know. We're happy to help.</p>" + _SIGNATURE
    ),
)

_INTERVIEW_RESCHEDULED = EmailTemplate(
    key="interview_rescheduled",
    label="Interview rescheduled",
    subject="Your Circle Cat Interview — Updated Time",
    body_html=(
        "<p>Dear {{candidate_name}},</p>"
        "<p>Your interview has been rescheduled to [INTERVIEW DATE/TIME].</p>"
        + _SIGNATURE
    ),
)

_CULTURAL_PASSED_TECHNICAL_INVITE = EmailTemplate(
    key="cultural_passed_technical_invite",
    label="Behavioral passed - request technical interview availability",
    subject="Circle Cat — Technical Interview Availability",
    body_html=(
        "<p>Dear {{candidate_name}},</p>"
        "<p>Congratulations! You did a great job on your behavioral interview and we would like to move "
        "you to the next step in the interview process.</p>"
        "<p><strong>What's next?</strong></p>"
        "<p>The next steps will consist of scheduling and prepping for your interview. Please provide your "
        "availability for a 45-minute technical phone interview. We can schedule the interview from 9PM "
        "to 4AM ET. Please provide 5-6 dates/times over the next 1-2 weeks that will work for your "
        "schedule.</p>"
        "<p><strong>Prep materials</strong></p>"
        "<p>The most popular prep websites are below:</p>"
        "<ul>"
        "<li>GeeksForGeeks.org</li>"
        "<li>Leetcode.com</li>"
        "<li>Topcoder.com</li>"
        '<li>"Cracking the Coding Interview" (a book that every engineer recommends on our teams!)</li>'
        "</ul>"
        "<p>I would work on problems that make you break down an issue, design the most efficient answer, "
        'code cleanly, then check your work - typically these are "parking lot" type problems and '
        '"lottery" problems. These problems will be designed to push you to the limit, so more than '
        "finding the perfect answer, you will need to produce the most efficient answer and be able to "
        "justify your method and explain it to the interviewer. It is the approach you take to solving a "
        "problem in our interviews that determines your performance, rather than what you do or do not "
        "know. Also, writing solutions out by hand would be beneficial because you will be expected to "
        "do so on a google doc during yourinterview.</p>"
        "<p><strong>Accommodations</strong></p>"
        "<p>It's important to us to create an accessible, inclusive workplace for everyone, so please do "
        "not hesitate to contact me if you need any accommodations for your interviews. We will then "
        "connect with you to confidentially discuss your options.</p>"
        "<p><strong>What equipment will I need?</strong></p>"
        "<p>You'll need a computer with internet access for the interviews to use Google Docs — a "
        "web-based word processor which lets you share and collaborate your work online. Note: You will "
        "not have access to an editor or compiler.<br>"
        "This interview will take place over Google Meet. We recommend using a headset or hands-free "
        "device during the interview, to allow for easier conversation while coding.</p>"
        "<p>If you have any questions or concerns, please don't hesitate to reach out. Best of luck during "
        "your interview.<br>"
        "Thanks!</p>" + _SIGNATURE
    ),
)

_TECHNICAL_INTERVIEW_SCHEDULED = EmailTemplate(
    key="technical_interview_scheduled",
    label="Technical interview scheduled",
    subject="Your Circle Cat Technical Interview is Scheduled",
    body_html=(
        "<p>Dear {{candidate_name}},</p>"
        "<p>We are looking forward to speaking with you! Your technical interview has been scheduled for "
        "[INTERVIEW DATE/TIME].</p>"
        "<p>You will receive a Google Meet invitation in a separate email shortly. Please accept that "
        "invite to confirm your attendance and to ensure the link is saved to your calendar.</p>"
        "<p>If you need any accommodations or a schedule adjustment, please reply to this email and let us "
        "know. We're happy to help.</p>" + _SIGNATURE
    ),
)

_FEEDBACK_COMPLETE_ASK_START_DATE = EmailTemplate(
    key="feedback_complete_ask_start_date",
    label="Feedback complete - ask for start date",
    subject="Circle Cat — Next Steps",
    body_html=(
        "<p>Dear {{candidate_name}},</p>"
        "<p>We have received all feedback from your interview. Can you let us know when you want your "
        "start date to be?</p>" + _SIGNATURE
    ),
)

_OFFER_ONBOARDING = EmailTemplate(
    key="offer_onboarding",
    label="Offer and onboarding",
    subject="Welcome to Circle Cat — Onboarding & Next Steps",
    body_html=(
        "<p>Dear {{candidate_name}},</p>"
        "<p>It is a pleasure talking to you and our team is excited to have you "
        "onboard! If you wish to proceed with "
        "循环猫实习计划志愿者/实习生"
        "(Residency Program Volunteer/Trainee), please fill out "
        f'<a href="{ONBOARDING_FORM_URL}">this form</a>'
        " and we will grant you access to our corp resources.</p>"
        "<p>Your role is: [SOFTWARE ENGINEER VOLUNTEER / SOFTWARE ENGINEER INTERN]<br>"
        "Your manager will be: [MANAGER NAME] [MANAGER EMAIL]<br>"
        "Your start date: [START DATE]</p>"
        "<p>Once you have filled out the form, there will be a couple of things "
        "coming up:</p>"
        "<p><strong>Onboard to corp resources</strong></p>"
        "<p>You will be given credentials and instructions to onboard corp "
        "resources in 1-2 business days after you have filled out the form. "
        "Follow those instructions and make sure you have access to accounts "
        "needed for work.</p>"
        "<p>If you need employer information for immigration purposes, you can "
        "visit circlecat.org/about or send me an email directly so I can help "
        "you fill out forms required by the DSO or the USCIS.</p>"
        "<p>Please let me know if you have any questions or if I can provide any "
        "additional information.</p>" + _SIGNATURE
    ),
)

_REJECTION = EmailTemplate(
    key="rejection",
    label="Rejection",
    subject="Your Application to Circle Cat",
    body_html=(
        "<p>Dear {{candidate_name}},</p>"
        "<p>I would like to thank you for taking the time to discuss your interests with "
        "{{position_title}} with us. I regret to inform you that we have decided not to "
        "progress further with your application.</p>"
        "<p>We wish you every success with your future endeavor and thank you for your interest in "
        "Circle Cat.</p>" + _SIGNATURE
    ),
)

EMAIL_TEMPLATES = (
    _SCREENING_PASSED_CULTURAL_INVITE,
    _CULTURAL_INTERVIEW_SCHEDULED,
    _INTERVIEW_RESCHEDULED,
    _CULTURAL_PASSED_TECHNICAL_INVITE,
    _TECHNICAL_INTERVIEW_SCHEDULED,
    _FEEDBACK_COMPLETE_ASK_START_DATE,
    _OFFER_ONBOARDING,
    _REJECTION,
)

_BY_KEY = {template.key: template for template in EMAIL_TEMPLATES}


def _substitute(text: str, values: Mapping[str, str], what: str) -> str:
    """Replace every ``{{placeholder}}`` in ``text``, HTML-escaping each value.

    Args:
        text (str): Restricted HTML carrying ``{{...}}`` placeholders.
        values (Mapping[str, str]): Value per placeholder appearing in ``text``.
        what (str): Name of what is being rendered, for the error message.

    Returns:
        str: ``text`` with placeholders substituted.

    Raises:
        ValueError: If a placeholder used by ``text`` has no entry in ``values``.
    """

    def substitute(match: re.Match) -> str:
        name = match.group(1)
        if name not in values:
            raise ValueError(f"{what} needs a value for {{{{{name}}}}}")
        return html.escape(values[name])

    return _PLACEHOLDER_RE.sub(substitute, text)


def render_signature(values: Mapping[str, str]) -> str:
    """Render the signature block on its own.

    Every template already ends with this block, but the composer also prefills
    it into an otherwise empty body — a message written from scratch, or a
    reply, would otherwise go out unsigned.

    Args:
        values (Mapping[str, str]): Must carry ``sender_name``. Other entries
            are ignored; the signature uses no other placeholder.

    Returns:
        str: The signature as restricted HTML.

    Raises:
        ValueError: If ``sender_name`` is missing from ``values``.
    """
    return _substitute(_SIGNATURE, values, "Signature")


def render_template(key: str, values: Mapping[str, str]) -> tuple[str, str]:
    """Render one template, substituting ``{{...}}`` placeholders.

    Substituted values are HTML-escaped (the body is HTML). ``[UPPERCASE]``
    bracket markers are left untouched for the sender to fill in.

    Args:
        key (str): Template key from ``EMAIL_TEMPLATES``.
        values (Mapping[str, str]): Value per placeholder appearing in the
            template. Empty strings are allowed (an applicant with a blank
            first name renders ``Dear ,``, which the sender edits before send).

    Returns:
        tuple[str, str]: ``(subject, body_html)``.

    Raises:
        ValueError: If ``key`` is unknown, or a placeholder used by the
            template has no entry in ``values``.
    """
    template = _BY_KEY.get(key)
    if template is None:
        raise ValueError(f"Unknown email template: {key}")
    return template.subject, _substitute(template.body_html, values, f"Template {key}")


def render_all_templates(
    values: Mapping[str, str],
) -> list[tuple[EmailTemplate, str, str]]:
    """Render every template in catalog order.

    The compose dropdown fetches all eight at once so switching templates
    needs no extra round trip.

    Args:
        values (Mapping[str, str]): See ``render_template``.

    Returns:
        list[tuple[EmailTemplate, str, str]]: ``(template, subject, body_html)``
            per template, in ``EMAIL_TEMPLATES`` order.

    Raises:
        ValueError: If any template has a placeholder missing from ``values``.
    """
    return [
        (template, *render_template(template.key, values))
        for template in EMAIL_TEMPLATES
    ]
