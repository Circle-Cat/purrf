from unittest import TestCase, main

from backend.common.constants import ldap_from_addresses


class TestLdapFromAddresses(TestCase):
    def test_reads_the_local_part_of_the_company_address(self):
        self.assertEqual(
            ldap_from_addresses(["a.person@gmail.com", "alice@circlecat.org"]),
            "alice",
        )

    def test_none_without_a_company_address(self):
        self.assertIsNone(ldap_from_addresses(["alice@gmail.com"]))
        self.assertIsNone(ldap_from_addresses([]))

    def test_ignores_the_microsoft_domain(self):
        self.assertIsNone(ldap_from_addresses(["alice@u.circlecat.org"]))

    def test_same_answer_whatever_the_order(self):
        addresses = ["bob@circlecat.org", "alice@circlecat.org"]
        self.assertEqual(ldap_from_addresses(addresses), "alice")
        self.assertEqual(ldap_from_addresses(addresses[::-1]), "alice")


if __name__ == "__main__":
    main()
