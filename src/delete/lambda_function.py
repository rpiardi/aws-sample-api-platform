from sample_common import delete, error, response, with_partner_context


@with_partner_context
def lambda_handler(event, context, partner):
    try:
        delete(event["pathParameters"]["itemId"])
        return response(204)
    except KeyError as exc:
        return error(400, "ValidationError", str(exc))
    except Exception:
        return error(500, "InternalError", "An internal error occurred")
