import unittest

from backend.common.permissions import (
    INTERNAL_EMPLOYEE_PERMISSIONS,
    Permission,
    SERVICE_ACCOUNT_PERMISSIONS,
    SUPER_ADMIN_PERMISSIONS,
)


class TestPermissions(unittest.TestCase):
    def test_catalog_has_twenty_unique_dotted_values(self):
        self.assertEqual(len(Permission), 20)
        values = [p.value for p in Permission]
        self.assertEqual(len(values), len(set(values)))
        for value in values:
            self.assertRegex(value, r"^[a-z0-9_]+(\.[a-z0-9_]+)+$")

    def test_str_enum_value_equals_string(self):
        # StrEnum members compare/serialize as their dotted string.
        self.assertEqual(Permission.SYSTEM_BACKFILL, "system.backfill")
        self.assertEqual(f"{Permission.PERMISSION_MANAGE}", "permission.manage")

    def test_super_admin_is_the_full_catalog(self):
        self.assertEqual(SUPER_ADMIN_PERMISSIONS, frozenset(Permission))

    def test_bundles_are_subsets_of_the_catalog(self):
        self.assertTrue(INTERNAL_EMPLOYEE_PERMISSIONS <= set(Permission))
        self.assertTrue(SERVICE_ACCOUNT_PERMISSIONS <= set(Permission))

    def test_internal_employee_bundle_contents(self):
        self.assertEqual(
            INTERNAL_EMPLOYEE_PERMISSIONS,
            frozenset({
                Permission.DIRECTORY_MICROSOFT_LDAP_READ,
                Permission.DASHBOARD_ACTIVITY_SUMMARY_READ,
            }),
        )

    def test_service_account_bundle_contents(self):
        self.assertEqual(
            SERVICE_ACCOUNT_PERMISSIONS,
            frozenset({
                Permission.SYSTEM_BACKFILL_SCHEDULED,
                Permission.SYSTEM_SYNC,
            }),
        )


if __name__ == "__main__":
    unittest.main()
