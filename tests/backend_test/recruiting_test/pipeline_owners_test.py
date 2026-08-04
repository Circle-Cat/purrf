import unittest

from backend.recruiting.pipeline_owners import normalized_owner_ids


class NormalizedOwnerIdsTest(unittest.TestCase):
    def test_none_config(self):
        self.assertEqual(normalized_owner_ids(None), [])

    def test_new_shape(self):
        self.assertEqual(normalized_owner_ids({"ownerIds": [3, 4]}), [3, 4])

    def test_legacy_shape(self):
        self.assertEqual(normalized_owner_ids({"ownerId": 5}), [5])

    def test_legacy_none(self):
        self.assertEqual(normalized_owner_ids({"ownerId": None}), [])


if __name__ == "__main__":
    unittest.main()
