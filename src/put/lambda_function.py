from sample_common import error, parse_body, put, response, with_partner_context


@with_partner_context
def lambda_handler(event, context, partner):
    try:
        item_id = event["pathParameters"]["itemId"]
        return response(200, put(item_id, parse_body(event)))
    except (KeyError, ValueError) as exc:
        return error(400, "ValidationError", str(exc))
    except Exception:
        return error(500, "InternalError", "An internal error occurred")
