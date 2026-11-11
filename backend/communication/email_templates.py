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

OPT_HOURS_URL = (
    "https://www.uscis.gov/working-in-the-united-states/"
    "students-and-exchange-visitors/optional-practical-training-opt-for-f-1-students"
)

PLACEHOLDER_KEYS = frozenset({"candidate_name", "position_title", "sender_name"})

_PLACEHOLDER_RE = re.compile(r"\{\{(\w+)\}\}")

# No "--" opening line: the sig-delimiter convention is "-- " with a trailing
# space, so the bare version never read as one to any mail client and no client
# collapsed the block out of a quoted reply. All it added was a stray line.
_SIGNATURE = "<p>Best,<br><strong>{{sender_name}}</strong><br>Circle Cat Inc.</p>"

# The sender picks the window that suits the applicant's time zone.
_TIME_WINDOW = "[9 AM TO 4 PM BJT / 8 PM TO 3 AM ET / 5 PM TO 12 AM PT]"


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


_BACKGROUND_CHECK_REJECTION = EmailTemplate(
    key="background_check_rejection",
    label="Rejection after application review",
    subject="Your Application to Circle Cat",
    body_html=(
        "<p>Dear {{candidate_name}},</p>"
        "<p>Thank you for your interest in {{position_title}}. We have reviewed your application, "
        "and we regret to inform you that it has not been selected for further consideration.</p>"
        "<p>We wish you every success with your future endeavours and thank you for your interest in "
        "Circle Cat.</p>" + _SIGNATURE
    ),
)

_SCREENING_PASSED_CULTURAL_INVITE = EmailTemplate(
    key="screening_passed_cultural_invite",
    label="Screening passed - request behavioral interview availability",
    subject="Circle Cat Program - Interview Availability",
    body_html=(
        "<p>Dear {{candidate_name}},</p>"
        "<p>We received your application for {{position_title}}, and we'd love to speak with you! "
        "Our typical interview process consists of a round of cultural and values interviews and a "
        "round of technical interviews with individuals from different teams. Let me know if you have "
        "any questions in the meantime!</p>"
        "<p><strong>What's next?</strong></p>"
        "<p>Before we can schedule your interview, please provide your availability for a 45-minute "
        "cultural and values video interview. We can schedule the interview from "
        + _TIME_WINDOW
        + ". "
        "Please provide 5-6 dates/times over the next 1-2 weeks that will work for your schedule.</p>"
        "<p><strong>Accommodations</strong></p>"
        "<p>We want to create an accessible, inclusive workplace for everyone, so please contact me if "
        "you need any accommodations for your interviews, such as a sign language interpreter, "
        "specialized equipment, or a lactation break and room. Our candidate accommodations team will "
        "then connect with you to confidentially discuss your options.</p>"
        "<p><strong>What equipment will I need?</strong></p>"
        "<p>Your behavioral interview will take place via Google Meet. Please use a computer with a "
        "stable internet connection and a working camera and microphone. Choose a quiet, "
        "distraction-free space where you can focus on the conversation.</p>"
        "<p>No coding or Google Docs will be required for this interview.</p>"
        "<p>In the meantime, please let me know if you have any questions.</p>"
        + _SIGNATURE
    ),
)

_CULTURAL_PASSED_TECHNICAL_INVITE = EmailTemplate(
    key="cultural_passed_technical_invite",
    label="Behavioral passed - request technical interview availability",
    subject="Circle Cat — Technical Interview Availability",
    body_html=(
        "<p>Dear {{candidate_name}},</p>"
        "<p>Congratulations! You did a great job in your behavior interview, and we would like to move "
        "you to the next step in the interview process.</p>"
        "<p><strong>What's next?</strong></p>"
        "<p>The next steps will consist of scheduling and prepping for your interview. Please provide your "
        "availability for a 45-minute technical video interview. We can schedule the interview from "
        + _TIME_WINDOW
        + ". Please provide 5-6 dates/times over the next 1-2 weeks that will work for "
        "your schedule.</p>"
        "<p><strong>Prep materials</strong></p>"
        "<p>The most popular prep websites are below:</p>"
        "<ul>"
        '<li><a href="http://geeksforgeeks.org/">GeeksForGeeks.org</a></li>'
        '<li><a href="http://leetcode.com/">Leetcode.com</a></li>'
        '<li><a href="http://topcoder.com/">Topcoder.com</a></li>'
        '<li>"Cracking the Coding Interview" (a book that <em>every</em> engineer recommends on our '
        "teams!)</li>"
        '<li><a href="https://www.hiredintech.com/system-design">System Design Prep Site</a> '
        "(HiredInTech Site that delves into how to approach these types of problems!)</li>"
        "</ul>"
        "<p>I would work on problems that make you break down an issue, design the most efficient answer, "
        'code cleanly, then check your work—typically these are "parking lot" type problems and '
        '"lottery" problems. These problems will be designed to push you to the limit, so more than '
        "finding the perfect answer, you will need to produce the most efficient answer and be able to "
        "justify your method and explain it to the interviewer. <strong><em>It is the approach you take "
        "to solving a problem in our interviews that determines your performance, rather than what you "
        "do or do not know.</em></strong> Also, writing solutions out by hand would be beneficial "
        "because you will be expected to do so on a whiteboard during your onsite interview.</p>"
        "<p><strong>Accommodations</strong></p>"
        "<p>We want to create an accessible, inclusive workplace for everyone, so please contact us if "
        "you need any accommodations for your interviews, such as a sign language interpreter, "
        "specialized equipment, or a lactation break and room. Our candidate accommodations team will "
        "then connect with you to confidentially discuss your options.</p>"
        "<p><strong>What equipment will I need?</strong></p>"
        "<p>You'll need a computer with internet access for the interviews to use Google Docs — a "
        "web-based word processor which lets you share and collaborate on your work online. Note: You "
        "will not have access to an editor or compiler.</p>"
        "<p>This interview will take place over Google Meet. We recommend using a headset or hands-free "
        "device during the interview to allow for easier conversation while coding.</p>"
        "<p>If you have any questions or concerns, please don't hesitate to reach out. Best of luck during "
        "your interview.</p>"
        "<p>Thanks!</p>" + _SIGNATURE
    ),
)

_INTERVIEW_SCHEDULED = EmailTemplate(
    key="interview_scheduled",
    label="Interview scheduled (behavioral / technical)",
    subject="Your Circle Cat Interview is Scheduled",
    body_html=(
        "<p>Dear {{candidate_name}},</p>"
        "<p>We are looking forward to speaking with you! Your interview is scheduled for "
        "[INTERVIEW DATE/TIME AND TIME ZONE].</p>"
        "<p>You will receive a Google Meet invitation in a separate email shortly. <strong>Please accept "
        "that invite</strong> to confirm your attendance and to ensure the link is saved to your "
        "calendar.</p>"
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

_REJECTION = EmailTemplate(
    key="rejection",
    label="Rejection after interview",
    subject="Your Application to Circle Cat",
    body_html=(
        "<p>Dear {{candidate_name}},</p>"
        "<p>Thank you for taking the time to discuss your interest in the {{position_title}} with us. "
        "We regret to inform you that we have decided not to progress further with your "
        "application.</p>"
        "<p>We wish you every success with your future endeavors and thank you for your interest in "
        "Circle Cat.</p>" + _SIGNATURE
    ),
)

_WORK_AUTHORIZATION_CONFIRMATION = EmailTemplate(
    key="work_authorization_confirmation",
    label="Confirm OPT/CPT sponsorship (North America)",
    subject="Circle Cat — Work Authorization Confirmation",
    body_html=(
        "<p>Dear {{candidate_name}},</p>"
        "<p>Thank you for your interest in {{position_title}}. It was a pleasure speaking with you, and "
        "we received positive feedback from the interviewer. Before we proceed further, could you please "
        "verify the type of work authorization sponsorship you require?</p>"
        "<p>We can provide:</p>"
        "<ul>"
        "<li>OPT sponsorship (excluding STEM OPT)</li>"
        "<li>CPT sponsorship</li>"
        "</ul>"
        "<p>You do <strong>NOT</strong> need work authorization to participate in this program. However, "
        "if you require an employment verification letter in the future, you will need to obtain the "
        "appropriate work authorization. If not, you will receive a volunteer verification letter if "
        "requested.</p>" + _SIGNATURE
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
    label="Offer and onboarding (North America)",
    subject="Welcome to Circle Cat — Onboarding & Next Steps",
    body_html=(
        "<p>Dear {{candidate_name}},</p>"
        "<p>It was a pleasure speaking with you, and our team is excited to have you on board! If you "
        "wish to proceed with {{position_title}}, please fill out this "
        f'<a href="{ONBOARDING_FORM_URL}">form</a>'
        ", and we will grant you access to our corp resources.</p>"
        "<p>Your role is: [SOFTWARE ENGINEER VOLUNTEER / SOFTWARE ENGINEER INTERN]</p>"
        "<p>Your manager will be: [MANAGER NAME] [MANAGER EMAIL]</p>"
        "<p>Your start date: [START DATE]</p>"
        "<p>Once you have filled out the form, there will be a couple of things coming up:</p>"
        "<p><strong>Onboard to corp resources</strong></p>"
        "<p>You will be given credentials and instructions to onboard corp resources in 1-2 business "
        "days after you have filled out the form. Follow those instructions and make sure you have "
        "access to the accounts needed for work.</p>"
        "<p><strong>Employment verifications</strong></p>"
        "<p>Federal law requires us to verify your employment eligibility. You will need to complete an "
        "I-9 form in order to complete that verification. Further instructions will be sent out when "
        "you are onboarded.</p>"
        "<p><strong>Maintain F1-OPT status</strong></p>"
        "<p>Since you are an international student under F-1 status, you will need to log your work and "
        f'make sure it satisfies the <a href="{OPT_HOURS_URL}">20-hour working hours requirement</a>. '
        "If you work under 20 hours per week, you will lose your OPT. <em>USCIS and DSO at your "
        "university may request such records, so it is crucial that you make sure you have worked and "
        "documented 20 or more working hours per week</em>. If your assigned working hours are less "
        "than 20 hours per week, work with your manager to reach the 20-hour requirement. Further "
        "instructions will be provided for logging your work. The responsibility for maintaining status "
        "in the US is <strong>on you</strong>.</p>"
        "<p>If you need employer information for immigration purposes, you can visit "
        "circlecat.org/about or send me an Email directly so I can help you fill out forms required by "
        "the DSO or USCIS.</p>"
        "<p>Please let me know if you have any questions or if I can provide any additional "
        "information.</p>" + _SIGNATURE
    ),
)

EMAIL_TEMPLATES = (
    _BACKGROUND_CHECK_REJECTION,
    _SCREENING_PASSED_CULTURAL_INVITE,
    _CULTURAL_PASSED_TECHNICAL_INVITE,
    _INTERVIEW_SCHEDULED,
    _INTERVIEW_RESCHEDULED,
    _REJECTION,
    _WORK_AUTHORIZATION_CONFIRMATION,
    _FEEDBACK_COMPLETE_ASK_START_DATE,
    _OFFER_ONBOARDING,
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

    The compose dropdown fetches them all at once so switching templates
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
