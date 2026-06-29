from sample_common import error, get, list_items, parse_pagination, response, with_partner_context


@with_partner_context
def lambda_handler(event, context, partner):
    try:
        item_id = (event.get("pathParameters") or {}).get("itemId")
        if item_id:
            item = get(item_id)
            return response(200, item) if item else error(404, "NotFound", "Item not found")
        limit, cursor = parse_pagination(event)
        items, next_cursor = list_items(limit, cursor)
        return response(200, {"items": items, "cursor": next_cursor})
    except ValueError as exc:
        return error(400, "ValidationError", str(exc))
    except Exception:
        return error(500, "InternalError", "An internal error occurred")
