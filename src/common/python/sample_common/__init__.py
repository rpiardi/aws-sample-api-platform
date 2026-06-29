import base64
import functools
import json
import logging
import os
import uuid
from decimal import Decimal

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

_table = boto3.resource("dynamodb").Table(os.environ["TABLE_NAME"])

# Tracks the first invocation of each warm execution environment for logging.
_cold_start = True


def response(status, body=None):
    result = {"statusCode": status, "headers": {"Content-Type": "application/json"}}
    if body is not None:
        result["body"] = json.dumps(body, separators=(",", ":"), default=_json_default)
    return result


def error(status, code, message):
    return response(status, {"error": code, "message": message})


# --- Partner identity (Approach A) ---
#
# Identity is resolved at token issuance by the auth-platform Pre Token
# Generation trigger and arrives as signed access-token claims, exposed by the
# native Cognito authorizer under requestContext.authorizer.claims. Handlers
# never look identity up and never read it from headers, query, or body. This
# adapter only reads and validates presence (defense in depth) and fails closed.


class PartnerAccessDenied(Exception):
    """Raised when partner identity claims are absent or empty."""


class PartnerContext:
    __slots__ = ("partner_id", "tenant", "client_id", "approach")

    def __init__(self, partner_id, tenant, client_id=None, approach="A"):
        self.partner_id = partner_id
        self.tenant = tenant
        self.client_id = client_id
        self.approach = approach


def resolve_partner_context(event):
    claims = (((event or {}).get("requestContext") or {}).get("authorizer") or {}).get("claims") or {}
    partner_id = claims.get("partner_id")
    tenant = claims.get("tenant")
    if not partner_id or not tenant:
        raise PartnerAccessDenied()
    return PartnerContext(partner_id, tenant, claims.get("client_id"))


def log_request_context(event, context, partner):
    global _cold_start
    logger.info(
        json.dumps(
            {
                "event": "partner_context_resolved",
                "approach": "A",
                "request_id": getattr(context, "aws_request_id", None),
                "http_method": event.get("httpMethod"),
                "resource_path": event.get("resource") or event.get("path"),
                "partner_id": partner.partner_id,
                "tenant": partner.tenant,
                "cold_start": _cold_start,
            }
        )
    )
    _cold_start = False


def log_partner_rejected(event, context, reason="missing_claims"):
    logger.info(
        json.dumps(
            {
                "event": "partner_context_rejected",
                "approach": "A",
                "reason": reason,
                "request_id": getattr(context, "aws_request_id", None),
            }
        )
    )


def with_partner_context(handler):
    """Resolve and log partner identity before the business handler runs.

    Fails closed with 403 when identity claims are missing. The wrapped handler
    receives the resolved PartnerContext as a third argument.
    """

    @functools.wraps(handler)
    def wrapper(event, context):
        try:
            partner = resolve_partner_context(event)
        except PartnerAccessDenied:
            log_partner_rejected(event, context)
            return error(403, "Forbidden", "Access denied")
        log_request_context(event, context, partner)
        return handler(event, context, partner)

    return wrapper


def parse_body(event):
    try:
        body = json.loads(event.get("body") or "")
    except (TypeError, json.JSONDecodeError):
        raise ValueError("Request body must be valid JSON")
    if not isinstance(body, dict):
        raise ValueError("Request body must be a JSON object")
    return body


def validate_item(body, partial=False):
    allowed = {"description", "status"}
    if set(body) - allowed:
        raise ValueError("Request contains unsupported fields")
    if partial and not body:
        raise ValueError("At least one supported field is required")
    if not partial and set(body) != allowed:
        raise ValueError("description and status are required")
    if "description" in body:
        if not isinstance(body["description"], str) or not body["description"].strip():
            raise ValueError("description must be a non-empty string")
        body["description"] = body["description"].strip()
    if "status" in body and not isinstance(body["status"], bool):
        raise ValueError("status must be a boolean")
    return body


def create(body):
    item = {"id": str(uuid.uuid4()), **validate_item(body)}
    _table.put_item(Item=item)
    return item


def get(item_id):
    return _table.get_item(Key={"id": item_id}, ConsistentRead=True).get("Item")


def list_items(limit, cursor=None):
    kwargs = {"Limit": limit}
    if cursor:
        kwargs["ExclusiveStartKey"] = decode_cursor(cursor)
    result = _table.scan(**kwargs)
    return result.get("Items", []), encode_cursor(result.get("LastEvaluatedKey"))


def put(item_id, body):
    item = {"id": item_id, **validate_item(body)}
    _table.put_item(Item=item)
    return item


def patch(item_id, body):
    values = validate_item(body, partial=True)
    names = {f"#{key}": key for key in values}
    attrs = {f":{key}": value for key, value in values.items()}
    expression = "SET " + ", ".join(f"#{key} = :{key}" for key in values)
    try:
        result = _table.update_item(
            Key={"id": item_id},
            UpdateExpression=expression,
            ConditionExpression="attribute_exists(id)",
            ExpressionAttributeNames=names,
            ExpressionAttributeValues=attrs,
            ReturnValues="ALL_NEW",
        )
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
            return None
        raise
    return result["Attributes"]


def delete(item_id):
    _table.delete_item(Key={"id": item_id})


def parse_pagination(event):
    query = event.get("queryStringParameters") or {}
    try:
        limit = int(query.get("limit", "50"))
    except (TypeError, ValueError):
        raise ValueError("limit must be an integer")
    if not 1 <= limit <= 100:
        raise ValueError("limit must be between 1 and 100")
    cursor = query.get("cursor")
    if cursor:
        decode_cursor(cursor)
    return limit, cursor


def encode_cursor(key):
    if not key:
        return None
    raw = json.dumps(key, separators=(",", ":"), default=_json_default).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def decode_cursor(cursor):
    try:
        raw = base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4))
        key = json.loads(raw)
        if not isinstance(key, dict) or set(key) != {"id"} or not isinstance(key["id"], str):
            raise ValueError
        return key
    except (ValueError, TypeError, json.JSONDecodeError):
        raise ValueError("cursor is malformed")


def _json_default(value):
    if isinstance(value, Decimal):
        return int(value) if value % 1 == 0 else float(value)
    raise TypeError
