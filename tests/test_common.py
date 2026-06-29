import json
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


class PartnerContextTests(unittest.TestCase):
    @staticmethod
    def _event(claims):
        return {"requestContext": {"authorizer": {"claims": claims}}}

    def test_resolves_identity_from_claims(self):
        partner = sample_common.resolve_partner_context(
            self._event({"partner_id": "PARTNER-001", "tenant": "acme", "client_id": "abc"})
        )
        self.assertEqual(partner.partner_id, "PARTNER-001")
        self.assertEqual(partner.tenant, "acme")
        self.assertEqual(partner.client_id, "abc")
        self.assertEqual(partner.approach, "A")

    def test_missing_or_empty_claims_fail_closed(self):
        for claims in ({}, {"partner_id": "PARTNER-001"}, {"tenant": "acme"}, {"partner_id": "", "tenant": "acme"}):
            with self.assertRaises(sample_common.PartnerAccessDenied):
                sample_common.resolve_partner_context(self._event(claims))

    def test_missing_authorizer_fails_closed(self):
        with self.assertRaises(sample_common.PartnerAccessDenied):
            sample_common.resolve_partner_context({})

    def test_decorator_passes_partner_and_blocks_on_missing_claims(self):
        seen = {}

        @sample_common.with_partner_context
        def handler(event, context, partner):
            seen["partner"] = partner
            return sample_common.response(200)

        ok = handler(self._event({"partner_id": "P", "tenant": "t"}), None)
        self.assertEqual(ok["statusCode"], 200)
        self.assertEqual(seen["partner"].partner_id, "P")

        denied = handler({}, None)
        self.assertEqual(denied["statusCode"], 403)
        self.assertEqual(json.loads(denied["body"])["error"], "Forbidden")

    def test_resolved_log_excludes_secrets(self):
        partner = sample_common.PartnerContext("PARTNER-001", "acme", "abc")
        with self.assertLogs(sample_common.logger, level="INFO") as captured:
            sample_common.log_request_context(
                {"httpMethod": "GET", "resource": "/v1/items"}, None, partner
            )
        line = captured.output[0]
        self.assertIn("partner_context_resolved", line)
        self.assertIn("PARTNER-001", line)
        for secret in ("client_secret", "Authorization", "Bearer"):
            self.assertNotIn(secret, line)


if __name__ == "__main__":
    unittest.main()
