from sample_common import error, parse_body, put, response


def lambda_handler(event, context):
    try:
        item_id = event["pathParameters"]["itemId"]
        return response(200, put(item_id, parse_body(event)))
    except (KeyError, ValueError) as exc:
        return error(400, "ValidationError", str(exc))
    except Exception:
        return error(500, "InternalError", "An internal error occurred")
