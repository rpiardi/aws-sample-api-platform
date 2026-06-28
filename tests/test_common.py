import os
import sys
import types
import unittest
from unittest.mock import MagicMock

os.environ["TABLE_NAME"] = "test"
table = MagicMock()
boto3 = types.ModuleType("boto3")
boto3.resource = MagicMock(return_value=MagicMock(Table=MagicMock(return_value=table)))
botocore = types.ModuleType("botocore")
exceptions = types.ModuleType("botocore.exceptions")


class ClientError(Exception):
    def __init__(self, response, operation_name):
        self.response = response


exceptions.ClientError = ClientError
sys.modules.update({"boto3": boto3, "botocore": botocore, "botocore.exceptions": exceptions})
sys.path.insert(0, "src/common/python")

import sample_common


class CommonTests(unittest.TestCase):
    def setUp(self):
        table.reset_mock()

    def test_validation_trims_description(self):
        self.assertEqual(
            sample_common.validate_item({"description": " x ", "status": True}),
            {"description": "x", "status": True},
        )

    def test_validation_rejects_unknown_and_empty_fields(self):
        with self.assertRaises(ValueError):
            sample_common.validate_item({"description": " ", "status": True})
        with self.assertRaises(ValueError):
            sample_common.validate_item({"description": "x", "status": True, "extra": 1})
        with self.assertRaises(ValueError):
            sample_common.validate_item({}, partial=True)

    def test_cursor_round_trip_and_rejects_malformed_cursor(self):
        cursor = sample_common.encode_cursor({"id": "abc"})
        self.assertEqual(sample_common.decode_cursor(cursor), {"id": "abc"})
        with self.assertRaises(ValueError):
            sample_common.decode_cursor("not-json")

    def test_patch_missing_item(self):
        table.update_item.side_effect = ClientError(
            {"Error": {"Code": "ConditionalCheckFailedException"}}, "UpdateItem"
        )
        self.assertIsNone(sample_common.patch("id", {"status": False}))

    def test_parse_pagination_bounds(self):
        self.assertEqual(sample_common.parse_pagination({}), (50, None))
        with self.assertRaises(ValueError):
            sample_common.parse_pagination({"queryStringParameters": {"limit": "101"}})
        with self.assertRaises(ValueError):
            sample_common.parse_pagination({"queryStringParameters": {"limit": "invalid"}})

    def test_list_items_passes_cursor_to_dynamodb(self):
        table.scan.return_value = {"Items": [{"id": "2"}], "LastEvaluatedKey": {"id": "2"}}
        cursor = sample_common.encode_cursor({"id": "1"})
        items, next_cursor = sample_common.list_items(10, cursor)
        self.assertEqual(items, [{"id": "2"}])
        self.assertEqual(sample_common.decode_cursor(next_cursor), {"id": "2"})
        table.scan.assert_called_once_with(Limit=10, ExclusiveStartKey={"id": "1"})

    def test_delete_is_idempotent(self):
        sample_common.delete("missing")
        table.delete_item.assert_called_once_with(Key={"id": "missing"})


if __name__ == "__main__":
    unittest.main()
