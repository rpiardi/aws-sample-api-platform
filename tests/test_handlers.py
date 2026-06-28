import importlib.util
import json
import unittest
from pathlib import Path
from unittest.mock import patch


def load_handler(name):
    spec = importlib.util.spec_from_file_location(f"{name}_handler", Path("src") / name / "lambda_function.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class HandlerTests(unittest.TestCase):
    def test_post_success(self):
        module = load_handler("post")
        with patch.object(module, "create", return_value={"id": "1", "description": "x", "status": True}):
            result = module.lambda_handler({"body": '{"description":"x","status":true}'}, None)
        self.assertEqual(result["statusCode"], 201)

    def test_post_validation_error(self):
        module = load_handler("post")
        result = module.lambda_handler({"body": "not-json"}, None)
        self.assertEqual(result["statusCode"], 400)
        self.assertEqual(json.loads(result["body"])["error"], "ValidationError")

    def test_post_hides_downstream_error(self):
        module = load_handler("post")
        with patch.object(module, "create", side_effect=RuntimeError("secret detail")):
            result = module.lambda_handler({"body": '{"description":"x","status":true}'}, None)
        self.assertEqual(result["statusCode"], 500)
        self.assertNotIn("secret detail", result["body"])

    def test_get_not_found(self):
        module = load_handler("get")
        with patch.object(module, "get", return_value=None):
            result = module.lambda_handler({"pathParameters": {"itemId": "missing"}}, None)
        self.assertEqual(result["statusCode"], 404)
        self.assertEqual(json.loads(result["body"])["error"], "NotFound")

    def test_delete_is_no_content(self):
        module = load_handler("delete")
        with patch.object(module, "delete"):
            result = module.lambda_handler({"pathParameters": {"itemId": "1"}}, None)
        self.assertEqual(result, {"statusCode": 204, "headers": {"Content-Type": "application/json"}})

    def test_patch_not_found(self):
        module = load_handler("patch")
        with patch.object(module, "patch", return_value=None):
            result = module.lambda_handler(
                {"pathParameters": {"itemId": "missing"}, "body": '{"status":false}'}, None
            )
        self.assertEqual(result["statusCode"], 404)


if __name__ == "__main__":
    unittest.main()
