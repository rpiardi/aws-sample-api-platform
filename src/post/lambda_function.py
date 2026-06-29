from sample_common import create, error, parse_body, response, with_partner_context


@with_partner_context
def lambda_handler(event, context, partner):
    try:
        return response(201, create(parse_body(event)))
    except ValueError as exc:
        return error(400, "ValidationError", str(exc))
    except Exception:
        return error(500, "InternalError", "An internal error occurred")
