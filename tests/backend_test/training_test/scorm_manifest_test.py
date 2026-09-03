"""What a SCORM manifest and its entry page are allowed to tell us."""

import unittest

from backend.common.mentorship_enums import ScormVersion
from backend.training.scorm_manifest import (
    ManifestRejected,
    parse_driver_config,
    parse_manifest,
)

_ENTRY_PATH = "scormdriver/indexAPI.html"


def _manifest(
    *,
    schemaversion: str = "1.2",
    organizations: str | None = None,
    resources: str | None = None,
    namespaced: bool = False,
    doctype: str = "",
) -> bytes:
    """A SCORM manifest shaped like the ones the real packages ship."""
    if organizations is None:
        organizations = """
  <organizations default="org_1">
    <organization identifier="org_1">
      <title>Cat Care Fundamentals</title>
      <item identifier="item_1" identifierref="res_1">
        <title>Module One</title>
      </item>
    </organization>
  </organizations>"""
    if resources is None:
        resources = f"""
  <resources>
    <resource identifier="res_1" type="webcontent" href="{_ENTRY_PATH}">
      <file href="{_ENTRY_PATH}"/>
    </resource>
  </resources>"""
    attributes = ' identifier="cat_course" version="1.2"'
    if namespaced:
        attributes = (
            ' xmlns="http://www.imsproject.org/xsd/imscp_rootv1p1p2"'
            ' xmlns:adlcp="http://www.adlnet.org/xsd/adlcp_rootv1p2"'
            ' xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"'
            ' identifier="cat_course" version="1.2"'
        )
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
{doctype}<manifest{attributes}>
  <metadata>
    <schema>ADL SCORM</schema>
    <schemaversion>{schemaversion}</schemaversion>
  </metadata>{organizations}{resources}
</manifest>"""
    return xml.encode("utf-8")


def _entry_page(script: str = "") -> bytes:
    html = f"""<!DOCTYPE html>
<html>
<head><title>Cat Care Fundamentals</title>{script}</head>
<body><div id="course"></div></body>
</html>"""
    return html.encode("utf-8")


def _driver_config_script(json_text: str) -> str:
    return (
        f'<script id="__DRIVER_CONFIG__" type="application/json">{json_text}</script>'
    )


class TestParseManifest(unittest.TestCase):
    def test_a_scorm_12_manifest_yields_its_version_and_entry_path(self):
        info = parse_manifest(_manifest())

        self.assertEqual(info.scorm_version, ScormVersion.SCORM_12)
        self.assertEqual(info.entry_path, _ENTRY_PATH)

    def test_xml_namespaces_do_not_defeat_the_lookup(self):
        """Real packages namespace every tag, including schemaversion."""
        info = parse_manifest(_manifest(namespaced=True))

        self.assertEqual(info.scorm_version, ScormVersion.SCORM_12)
        self.assertEqual(info.entry_path, _ENTRY_PATH)

    def test_scorm_2004_third_edition_is_named_rather_than_guessed_at(self):
        """Refusing 2004 is read_package's job; naming it is this one's."""
        info = parse_manifest(_manifest(schemaversion="2004 3rd Edition"))

        self.assertEqual(info.scorm_version, ScormVersion.SCORM_2004)

    def test_a_bare_2004_schemaversion_is_recognised_too(self):
        info = parse_manifest(_manifest(schemaversion="2004"))

        self.assertEqual(info.scorm_version, ScormVersion.SCORM_2004)

    def test_a_schemaversion_of_neither_version_is_rejected(self):
        with self.assertRaises(ManifestRejected):
            parse_manifest(_manifest(schemaversion="1.1"))

    def test_a_manifest_without_an_organization_is_rejected(self):
        """One resource is not permission to guess which page starts a course."""
        with self.assertRaises(ManifestRejected):
            parse_manifest(_manifest(organizations="\n  <organizations/>"))

    def test_an_identifierref_matching_no_resource_is_rejected(self):
        organizations = """
  <organizations default="org_1">
    <organization identifier="org_1">
      <title>Cat Care Fundamentals</title>
      <item identifier="item_1" identifierref="res_missing">
        <title>Module One</title>
      </item>
    </organization>
  </organizations>"""

        with self.assertRaises(ManifestRejected):
            parse_manifest(_manifest(organizations=organizations))

    def test_the_rejection_says_what_to_re_export(self):
        """The admin has to forward this to whoever built the package."""
        with self.assertRaises(ManifestRejected) as raised:
            parse_manifest(_manifest(organizations="\n  <organizations/>"))

        self.assertIn("identifierref", str(raised.exception))

    def test_a_manifest_with_no_resource_href_at_all_is_rejected(self):
        resources = """
  <resources>
    <resource identifier="res_1" type="webcontent"/>
  </resources>"""

        with self.assertRaises(ManifestRejected):
            parse_manifest(_manifest(resources=resources))

    def test_a_query_string_on_the_href_is_stripped_from_the_entry_path(self):
        """No zip entry ever carries a query string on its name."""
        resources = """
  <resources>
    <resource identifier="res_1" type="webcontent" href="indexAPI.html?redirect=1">
      <file href="indexAPI.html"/>
    </resource>
  </resources>"""

        info = parse_manifest(_manifest(resources=resources))

        self.assertEqual(info.entry_path, "indexAPI.html")

    def test_declared_hrefs_are_kept_as_the_manifest_wrote_them(self):
        """Decoding belongs to the comparison against the archive, not here.

        scorm_package_test pins that rule; keeping the raw form means the
        rejection message can quote what the author actually wrote.
        """
        resources = f"""
  <resources>
    <resource identifier="res_1" type="webcontent" href="{_ENTRY_PATH}">
      <file href="{_ENTRY_PATH}"/>
      <file href="assets/cute%20cat.jpg"/>
    </resource>
  </resources>"""

        info = parse_manifest(_manifest(resources=resources))

        self.assertIn("assets/cute%20cat.jpg", info.declared_hrefs)

    def test_an_external_entity_is_rejected_and_never_expanded(self):
        doctype = '<!DOCTYPE manifest [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>\n'
        organizations = """
  <organizations default="org_1">
    <organization identifier="org_1">
      <title>&xxe;</title>
      <item identifier="item_1" identifierref="res_1">
        <title>Module One</title>
      </item>
    </organization>
  </organizations>"""

        with self.assertRaises(ManifestRejected) as raised:
            parse_manifest(_manifest(doctype=doctype, organizations=organizations))

        self.assertNotIn("root:", str(raised.exception))

    def test_nested_entity_expansion_is_rejected_rather_than_expanded(self):
        doctype = """<!DOCTYPE manifest [
  <!ENTITY lol "lol">
  <!ENTITY lol1 "&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;">
  <!ENTITY lol2 "&lol1;&lol1;&lol1;&lol1;&lol1;&lol1;&lol1;&lol1;&lol1;&lol1;">
  <!ENTITY lol3 "&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;">
  <!ENTITY lol4 "&lol3;&lol3;&lol3;&lol3;&lol3;&lol3;&lol3;&lol3;&lol3;&lol3;">
]>
"""
        organizations = """
  <organizations default="org_1">
    <organization identifier="org_1">
      <title>&lol4;</title>
      <item identifier="item_1" identifierref="res_1">
        <title>Module One</title>
      </item>
    </organization>
  </organizations>"""

        with self.assertRaises(ManifestRejected):
            parse_manifest(_manifest(doctype=doctype, organizations=organizations))

    def test_the_entry_path_carries_no_course_name_wrapper_directory(self):
        """imsmanifest.xml sits at the archive root; nothing is prepended to href."""
        info = parse_manifest(_manifest())

        self.assertEqual(info.entry_path, _ENTRY_PATH)
        self.assertFalse(info.entry_path.startswith("/"))
        self.assertFalse(info.entry_path.startswith("Cat Care Fundamentals"))
        self.assertFalse(info.entry_path.startswith("cat_course"))

    def test_truncated_xml_is_rejected_not_raised_as_a_parser_error(self):
        truncated = _manifest()[:120]

        with self.assertRaises(ManifestRejected):
            parse_manifest(truncated)

    def test_bytes_that_are_not_xml_at_all_are_rejected(self):
        with self.assertRaises(ManifestRejected):
            parse_manifest(b"this is not a manifest, it is a cat photo")


class TestParseDriverConfig(unittest.TestCase):
    def test_the_driver_config_script_is_read_off_the_entry_page(self):
        page = _entry_page(
            _driver_config_script(
                '{"coursePackageVersion": "2026.08.29.1",'
                ' "reporting": "completed",'
                ' "storylineId": "story_7",'
                ' "quizId": "quiz_3"}'
            )
        )

        config = parse_driver_config(page)

        self.assertIsNotNone(config)
        self.assertEqual(config.course_package_version, "2026.08.29.1")
        self.assertEqual(config.reporting, "completed")
        self.assertEqual(config.storyline_id, "story_7")
        self.assertEqual(config.quiz_id, "quiz_3")

    def test_null_storyline_and_quiz_ids_stay_none(self):
        """A stringified null here is what kept a real course from completing."""
        page = _entry_page(
            _driver_config_script(
                '{"coursePackageVersion": "2026.08.29.1",'
                ' "reporting": "passed",'
                ' "storylineId": null,'
                ' "quizId": null}'
            )
        )

        config = parse_driver_config(page)

        self.assertIsNotNone(config)
        self.assertIsNone(config.storyline_id)
        self.assertIsNone(config.quiz_id)

    def test_an_entry_page_without_the_script_returns_none(self):
        config = parse_driver_config(_entry_page())

        self.assertIsNone(config)

    def test_malformed_driver_config_json_returns_none_without_raising(self):
        page = _entry_page(_driver_config_script('{"reporting": "passed",,,'))

        self.assertIsNone(parse_driver_config(page))


if __name__ == "__main__":
    unittest.main()
