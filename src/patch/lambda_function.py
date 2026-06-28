from sample_common import error, parse_body, patch, response


def lambda_handler(event, context):
    try:
        item_id = event["pathParameters"]["itemId"]
        item = patch(item_id, parse_body(event))
        return response(200, item) if item else error(404, "NotFound", "Item not found")
    except (KeyError, ValueError) as exc:
        return error(400, "ValidationError", str(exc))
    except Exception:
        return error(500, "InternalError", "An internal error occurred")
