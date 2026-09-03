"""What an uploaded SCORM zip has to survive before we host it."""

import io
import unittest
import zipfile

from backend.common.mentorship_enums import ScormVersion
from backend.training.scorm_manifest import MANIFEST_NAME
from backend.training.scorm_package import (
    MAX_COMPRESSION_RATIO,
    MAX_ENTRY_COUNT,
    MAX_FILE_BYTES,
    MAX_TOTAL_UNCOMPRESSED_BYTES,
    PackageRejected,
    read_package,
)

_ENTRY_PATH = "scormdriver/indexAPI.html"
_DRIVER_CONFIG = (
    '<script id="__DRIVER_CONFIG__" type="application/json">'
    '{"coursePackageVersion": "2026.08.29.1", "reporting": "passed",'
    ' "storylineId": null, "quizId": null}'
    "</script>"
)


def _manifest(entry_href: str = _ENTRY_PATH, declared: tuple[str, ...] = ()) -> bytes:
    files = "\n".join(
        f'      <file href="{href}"/>' for href in (declared or (entry_href,))
    )
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<manifest identifier="cat_course" version="1.2">
  <metadata>
    <schema>ADL SCORM</schema>
    <schemaversion>1.2</schemaversion>
  </metadata>
  <organizations default="org_1">
    <organization identifier="org_1">
      <title>Cat Care Fundamentals</title>
      <item identifier="item_1" identifierref="res_1">
        <title>Module One</title>
      </item>
    </organization>
  </organizations>
  <resources>
    <resource identifier="res_1" type="webcontent" href="{entry_href}">
{files}
    </resource>
  </resources>
</manifest>"""
    return xml.encode("utf-8")


def _entry_page(script: str = _DRIVER_CONFIG) -> bytes:
    html = f"""<!DOCTYPE html>
<html>
<head><title>Cat Care Fundamentals</title>{script}</head>
<body><div id="course"></div></body>
</html>"""
    return html.encode("utf-8")


def _build_zip(entries: dict) -> zipfile.ZipFile:
    """Keys are archive names, or ZipInfo objects when the test needs raw attributes."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as writer:
        for name, payload in entries.items():
            writer.writestr(name, payload)
    buffer.seek(0)
    return zipfile.ZipFile(buffer)


def _valid_entries(**extra: bytes) -> dict:
    entries = {MANIFEST_NAME: _manifest(), _ENTRY_PATH: _entry_page()}
    entries.update(extra)
    return entries


class TestReadPackageRejections(unittest.TestCase):
    def test_a_traversing_entry_name_is_rejected(self):
        entries = _valid_entries()
        entries["../../etc/passwd"] = b"root:x:0:0:"

        with self.assertRaises(PackageRejected):
            read_package(_build_zip(entries))

    def test_traversal_that_only_shows_up_after_normalisation_is_rejected(self):
        entries = _valid_entries()
        entries["course/../../etc/passwd"] = b"root:x:0:0:"

        with self.assertRaises(PackageRejected):
            read_package(_build_zip(entries))

    def test_an_absolute_path_entry_is_rejected(self):
        entries = _valid_entries()
        entries["/etc/passwd"] = b"root:x:0:0:"

        with self.assertRaises(PackageRejected):
            read_package(_build_zip(entries))

    def test_a_symlink_entry_is_rejected(self):
        symlink = zipfile.ZipInfo("assets/logo.png")
        symlink.external_attr = (0xA000 | 0o777) << 16
        entries = _valid_entries()
        entries[symlink] = b"../../../etc/passwd"

        with self.assertRaises(PackageRejected):
            read_package(_build_zip(entries))

    def test_too_many_entries_is_rejected(self):
        entries = _valid_entries()
        for index in range(MAX_ENTRY_COUNT + 1):
            entries[f"assets/f{index}.txt"] = b"x"

        with self.assertRaises(PackageRejected):
            read_package(_build_zip(entries))

    def test_a_single_oversized_file_is_rejected(self):
        archive = _build_zip(_valid_entries(**{"assets/lecture.mp4": b"x" * 1024}))
        # Declaring the size is enough; writing 200MB would only slow the suite down.
        info = archive.getinfo("assets/lecture.mp4")
        info.file_size = MAX_FILE_BYTES + 1
        info.compress_size = info.file_size // 2

        with self.assertRaises(PackageRejected):
            read_package(archive)

    def test_too_much_total_uncompressed_content_is_rejected(self):
        entries = _valid_entries()
        for index in range(3):
            entries[f"assets/lecture{index}.mp4"] = b"x" * 1024
        archive = _build_zip(entries)
        for index in range(3):
            info = archive.getinfo(f"assets/lecture{index}.mp4")
            # Each file stays within the per-file cap; only the sum is over.
            info.file_size = MAX_FILE_BYTES
            info.compress_size = info.file_size // 2
        self.assertGreater(3 * MAX_FILE_BYTES, MAX_TOTAL_UNCOMPRESSED_BYTES)

        with self.assertRaises(PackageRejected):
            read_package(archive)

    def test_a_zip_bomb_compression_ratio_is_rejected(self):
        entries = _valid_entries(**{"assets/bomb.bin": b"\0" * (4 * 1024 * 1024)})
        archive = _build_zip(entries)
        info = archive.getinfo("assets/bomb.bin")
        self.assertGreater(info.file_size / info.compress_size, MAX_COMPRESSION_RATIO)

        with self.assertRaises(PackageRejected):
            read_package(archive)

    def test_an_archive_without_a_manifest_is_rejected(self):
        with self.assertRaises(PackageRejected):
            read_package(_build_zip({_ENTRY_PATH: _entry_page()}))

    def test_a_package_shadowing_the_shim_host_page_is_rejected(self):
        entries = _valid_entries()
        entries["__player.html"] = b"<html>not ours</html>"

        with self.assertRaises(PackageRejected):
            read_package(_build_zip(entries))

    def test_any_other_reserved_prefixed_entry_is_rejected(self):
        entries = _valid_entries()
        entries["__internal/shim.js"] = b"// nope"

        with self.assertRaises(PackageRejected):
            read_package(_build_zip(entries))

    def test_a_mac_zipped_metadata_directory_is_rejected(self):
        """Zipping on a Mac adds this, and it lands in the reserved space."""
        entries = _valid_entries()
        entries["__MACOSX/._indexAPI.html"] = b"\x00\x05\x16\x07"

        with self.assertRaises(PackageRejected):
            read_package(_build_zip(entries))

    def test_a_scorm_2004_package_is_refused_at_upload(self):
        """Nothing here runs 2004, so it is named and refused, never stored."""
        entries = _valid_entries()
        entries[MANIFEST_NAME] = _manifest().replace(
            b"<schemaversion>1.2</schemaversion>",
            b"<schemaversion>2004 3rd Edition</schemaversion>",
        )

        with self.assertRaises(PackageRejected):
            read_package(_build_zip(entries))


class TestReadPackageAcceptance(unittest.TestCase):
    def test_a_reserved_prefix_deeper_in_the_tree_collides_with_nothing(self):
        """Bundlers emit these constantly; only the root is ours to reserve."""
        entries = _valid_entries(**{"assets/__chunk.js": b"// bundler output"})

        contents = read_package(_build_zip(entries))

        self.assertIn("assets/__chunk.js", contents.file_names)

    def test_a_well_formed_package_reports_its_contents(self):
        entries = _valid_entries(**{"assets/cat.jpg": b"jpegbytes"})
        archive = _build_zip(entries)

        contents = read_package(archive)

        self.assertEqual(set(contents.file_names), set(entries))
        self.assertEqual(
            contents.total_uncompressed_bytes,
            sum(len(payload) for payload in entries.values()),
        )
        self.assertEqual(contents.manifest.scorm_version, ScormVersion.SCORM_12)
        self.assertEqual(contents.manifest.entry_path, _ENTRY_PATH)
        self.assertIsNotNone(contents.driver_config)
        self.assertEqual(contents.driver_config.course_package_version, "2026.08.29.1")
        self.assertEqual(contents.driver_config.reporting, "passed")
        self.assertIsNone(contents.driver_config.storyline_id)
        self.assertIsNone(contents.driver_config.quiz_id)

    def test_a_percent_encoded_declared_href_matches_the_archive_entry(self):
        entries = _valid_entries(**{"assets/cute cat.jpg": b"jpegbytes"})
        entries[MANIFEST_NAME] = _manifest(
            declared=(_ENTRY_PATH, "assets/cute%20cat.jpg")
        )

        contents = read_package(_build_zip(entries))

        self.assertEqual(contents.missing_declared_files, [])

    def test_a_genuinely_missing_declared_file_is_a_warning_not_a_rejection(self):
        entries = _valid_entries()
        entries[MANIFEST_NAME] = _manifest(
            declared=(_ENTRY_PATH, "assets/absent-cat.jpg")
        )

        contents = read_package(_build_zip(entries))

        self.assertEqual(contents.missing_declared_files, ["assets/absent-cat.jpg"])
        self.assertEqual(contents.manifest.entry_path, _ENTRY_PATH)

    def test_an_entry_page_without_a_driver_config_is_still_accepted(self):
        entries = _valid_entries(**{_ENTRY_PATH: _entry_page(script="")})

        contents = read_package(_build_zip(entries))

        self.assertIsNone(contents.driver_config)
        self.assertEqual(contents.manifest.entry_path, _ENTRY_PATH)


if __name__ == "__main__":
    unittest.main()
