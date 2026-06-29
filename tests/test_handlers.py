import importlib.util
import json
import unittest
from pathlib import Path
from unittest.mock import patch

# Importing test_common first installs the boto3 mock and puts the common layer
# on sys.path, so the handler modules can `from sample_common import ...`.
import test_common  # noqa: F401  (side effects: mocked boto3 + sys.path)


def load_handler(name):
    spec = importlib.util.spec_from_file_location(f"{name}_handler", Path("src") / name / "lambda_function.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def authorized(event=None, partner_id="PARTNER-001", tenant="acme", client_id="1example23clientid"):
    """Wrap an event with the claims a native Cognito authorizer would expose."""
    event = dict(event or {})
    claims = {}
    if partner_id is not None:
        claims["partner_id"] = partner_id
    if tenant is not None:
        claims["tenant"] = tenant
    if client_id is not None:
        claims["client_id"] = client_id
    event["requestContext"] = {"authorizer": {"claims": claims}}
    return event


class HandlerTests(unittest.TestCase):
    def test_post_success(self):
        module = load_handler("post")
        with patch.object(module, "create", return_value={"id": "1", "description": "x", "status": True}):
            result = module.lambda_handler(authorized({"body": '{"description":"x","status":true}'}), None)
        self.assertEqual(result["statusCode"], 201)

    def test_post_validation_error(self):
        module = load_handler("post")
        result = module.lambda_handler(authorized({"body": "not-json"}), None)
        self.assertEqual(result["statusCode"], 400)
        self.assertEqual(json.loads(result["body"])["error"], "ValidationError")

    def test_post_hides_downstream_error(self):
        module = load_handler("post")
        with patch.object(module, "create", side_effect=RuntimeError("secret detail")):
            result = module.lambda_handler(authorized({"body": '{"description":"x","status":true}'}), None)
        self.assertEqual(result["statusCode"], 500)
        self.assertNotIn("secret detail", result["body"])

    def test_get_not_found(self):
        module = load_handler("get")
        with patch.object(module, "get", return_value=None):
            result = module.lambda_handler(authorized({"pathParameters": {"itemId": "missing"}}), None)
        self.assertEqual(result["statusCode"], 404)
        self.assertEqual(json.loads(result["body"])["error"], "NotFound")

    def test_delete_is_no_content(self):
        module = load_handler("delete")
        with patch.object(module, "delete"):
            result = module.lambda_handler(authorized({"pathParameters": {"itemId": "1"}}), None)
        self.assertEqual(result, {"statusCode": 204, "headers": {"Content-Type": "application/json"}})

    def test_patch_not_found(self):
        module = load_handler("patch")
        with patch.object(module, "patch", return_value=None):
            result = module.lambda_handler(
                authorized({"pathParameters": {"itemId": "missing"}, "body": '{"status":false}'}), None
            )
        self.assertEqual(result["statusCode"], 404)

    # --- Approach A: partner identity (fail-closed, anti-forge, no leakage) ---

    def test_missing_claims_is_forbidden(self):
        module = load_handler("post")
        result = module.lambda_handler({"body": '{"description":"x","status":true}'}, None)
        self.assertEqual(result["statusCode"], 403)
        self.assertEqual(json.loads(result["body"])["error"], "Forbidden")

    def test_empty_claims_is_forbidden(self):
        module = load_handler("get")
        event = authorized({"pathParameters": {"itemId": "1"}}, partner_id=None, tenant=None, client_id=None)
        result = module.lambda_handler(event, None)
        self.assertEqual(result["statusCode"], 403)

    def test_dynamodb_not_called_when_identity_missing(self):
        module = load_handler("post")
        with patch.object(module, "create") as create:
            result = module.lambda_handler({"body": '{"description":"x","status":true}'}, None)
        self.assertEqual(result["statusCode"], 403)
        create.assert_not_called()

    def test_forged_partner_headers_are_ignored(self):
        # Forged headers present, but no signed claims -> still fail closed.
        module = load_handler("post")
        event = {
            "body": '{"description":"x","status":true}',
            "headers": {"X-Partner-Id": "ATTACKER", "X-Tenant-Id": "evil"},
        }
        with patch.object(module, "create") as create:
            result = module.lambda_handler(event, None)
        self.assertEqual(result["statusCode"], 403)
        create.assert_not_called()

    def test_identity_comes_from_claims_not_headers(self):
        # Claims are authoritative; forged headers do not change behavior.
        module = load_handler("post")
        captured = {}

        def fake_create(body):
            captured["body"] = body
            return {"id": "1", "description": body["description"], "status": body["status"]}

        event = authorized(
            {
                "body": '{"description":"x","status":true}',
                "headers": {"X-Partner-Id": "ATTACKER", "X-Tenant-Id": "evil"},
            }
        )
        with patch.object(module, "create", side_effect=fake_create):
            result = module.lambda_handler(event, None)
        self.assertEqual(result["statusCode"], 201)
        # Identity never enters the persisted item.
        self.assertEqual(set(captured["body"]), {"description", "status"})

    def test_identity_not_in_response(self):
        module = load_handler("post")
        with patch.object(module, "create", return_value={"id": "1", "description": "x", "status": True}):
            result = module.lambda_handler(authorized({"body": '{"description":"x","status":true}'}), None)
        body = json.loads(result["body"])
        self.assertNotIn("partner_id", body)
        self.assertNotIn("tenant", body)


if __name__ == "__main__":
    unittest.main()
