"""Chat protocol message handler."""

import asyncio

from datetime import datetime, timezone

from uagents import Context
from uagents_core.contrib.protocols.chat import (
    ChatAcknowledgement,
    ChatMessage,
    TextContent,
)

from tripmate.cards import (
    booking_redirect_card,
    booking_review_card,
    card_message,
    error_card,
    passenger_details_form_card,
    search_form_card,
)
from tripmate.graph import run_graph
from tripmate.mcp_args import prepare_mcp_args
from tripmate.mcp_client import mcp_client
from tripmate.results import (
    extract_book_url,
    extract_booking_from_hotel_detail,
    index_search_results,
    results_to_carousel,
    summary_rows_from_item,
)
from tripmate.session import SessionStore
from tripmate.utils import (
    extract_selection,
    format_mcp_error,
    is_card_action,
    needs_passenger_form,
    parse_mcp_json,
    parse_package_intent,
    strip_agent_mention,
)


def review_summary_rows(item: dict, last_args: dict | None = None) -> list[dict]:
    """Build clean review rows for the booking confirmation card."""
    rows: list[dict] = []
    last_args = last_args or {}
    name = item.get("name") or item.get("airline") or item.get("hotel_name")
    if name:
        label = "Hotel" if item.get("name") or item.get("hotel_name") else "Flight"
        rows.append({"label": label, "value": str(name)})

    date_from = last_args.get("date_from") or last_args.get("start_date")
    date_to = last_args.get("date_to") or last_args.get("end_date")
    if date_from:
        dates = date_from if not date_to else f"{date_from} → {date_to}"
        rows.append({"label": "Dates", "value": dates})

    outbound = item.get("outbound")
    if outbound:
        rows.append({"label": "Outbound", "value": str(outbound)})
    ret = item.get("return")
    if ret:
        rows.append({"label": "Return", "value": str(ret)})

    carrier = item.get("carrier") or item.get("airline")
    if carrier and not name:
        rows.append({"label": "Carrier", "value": str(carrier)})

    price = (
        item.get("price")
        or item.get("price_format")
        or (
            f"{item.get('currency', '')} {item.get('price_total', '')}".strip()
            if item.get("price_total")
            else ""
        )
    )
    if price:
        rows.append({"label": "Total", "value": str(price)})

    if rows:
        return rows[:8]
    return summary_rows_from_item(item)[:8]


async def send_booking_link(
    ctx: Context,
    sender: str,
    session: SessionStore,
    book_url: str,
    title: str,
) -> None:
    session.update(book_url=book_url)
    session.save()
    await ctx.send(
        sender,
        card_message("custom", booking_redirect_card(title, book_url)),
    )
    ctx.logger.info(f"🔗 Sent booking link: {book_url[:80]}...")


async def run_mcp(tool_name: str, args: dict) -> str:
    prepared = prepare_mcp_args(tool_name, args)
    return await asyncio.to_thread(mcp_client.call_tool, tool_name, prepared)


async def search_and_reply(
    ctx: Context,
    sender: str,
    session: SessionStore,
    tool_name: str,
    args: dict,
) -> bool:
    prepared = prepare_mcp_args(tool_name, args)
    ctx.logger.info(f"🔍 MCP {tool_name}: {prepared}")
    try:
        mcp_text = await run_mcp(tool_name, prepared)
    except Exception as exc:
        ctx.logger.exception("MCP failed")
        await ctx.send(
            sender, card_message("custom", error_card(f"Search failed: {exc}"))
        )
        return False

    index = index_search_results(mcp_text)
    session.remember_search(tool_name, prepared, mcp_text, index)
    if tool_name == "search_only_hotel":
        subtitle = prepared.get("destination", "")
    else:
        subtitle = (
            f"{prepared.get('origin', prepared.get('departure', ''))} → "
            f"{prepared.get('destination', prepared.get('arrival', ''))}"
        )
    parsed = results_to_carousel(tool_name, mcp_text, subtitle)
    if parsed:
        kind, payload = parsed
        await ctx.send(sender, card_message(kind, payload))
        ctx.logger.info(f"✅ Sent {kind} card")
        return True
    await ctx.send(
        sender, card_message("custom", error_card(format_mcp_error(mcp_text)))
    )
    return False


async def handle_pick_package(
    ctx: Context,
    sender: str,
    session: SessionStore,
    selection: dict,
) -> None:
    item = session.lookup_item(selection.get("package_id", ""))
    search_id = selection.get("search_id") or session.get("last_search", {}).get(
        "search_id"
    )
    hotel_id = selection.get("hotel_internal_id") or item.get("internal_id_hotel")
    last_args = session.get("last_search", {}).get("args", {})

    book_url = extract_book_url(item)
    rows = review_summary_rows(item, last_args)

    if search_id and hotel_id:
        try:
            detail_text = await run_mcp(
                "select_hotel_options",
                {
                    "search_id": search_id,
                    "hotel_internal_id": hotel_id,
                    "date_from": last_args.get("date_from", ""),
                    "date_to": last_args.get("date_to", ""),
                },
            )
            detail = parse_mcp_json(detail_text) or {}
            _, url = extract_booking_from_hotel_detail(detail)
            if url:
                book_url = url
            if detail:
                rows = review_summary_rows(detail, last_args) or rows
            session.set("hotel_detail", detail_text)
        except Exception as exc:
            ctx.logger.warning(f"select_hotel_options failed: {exc}")

    if not book_url:
        await ctx.send(
            sender,
            card_message(
                "custom",
                error_card("Could not get a booking link. Please try another option."),
            ),
        )
        return

    session.update(selected=selection, book_url=book_url)
    session.save()
    await ctx.send(
        sender,
        card_message(
            "review",
            booking_review_card("Confirm your booking", rows, book_url),
        ),
    )


async def handle_pick_flight(
    ctx: Context,
    sender: str,
    session: SessionStore,
    selection: dict,
) -> None:
    item = session.lookup_item(selection.get("offer_id", ""))
    book_url = extract_book_url(item)
    last_args = session.get("last_search", {}).get("args", {})
    rows = review_summary_rows(item, last_args)

    if not book_url:
        await ctx.send(
            sender,
            card_message(
                "custom", error_card("Could not get a booking link for this flight.")
            ),
        )
        return

    session.update(selected=selection, book_url=book_url)
    session.save()
    await ctx.send(
        sender,
        card_message(
            "review",
            booking_review_card("Confirm your booking", rows, book_url),
        ),
    )


async def handle_pick_hotel(
    ctx: Context,
    sender: str,
    session: SessionStore,
    selection: dict,
) -> None:
    item = session.lookup_item(selection.get("hotel_id", ""))
    search_id = selection.get("search_id") or session.get("last_search", {}).get(
        "search_id"
    )
    hotel_id = selection.get("hotel_internal_id") or item.get("internal_id_hotel")
    last_args = session.get("last_search", {}).get("args", {})

    book_url = extract_book_url(item)
    rows = review_summary_rows(item, last_args)

    if search_id and hotel_id:
        try:
            detail_text = await run_mcp(
                "select_hotel_options",
                {
                    "search_id": search_id,
                    "hotel_internal_id": hotel_id,
                    "date_from": last_args.get("date_from", ""),
                    "date_to": last_args.get("date_to", ""),
                },
            )
            detail = parse_mcp_json(detail_text) or {}
            t, url = extract_booking_from_hotel_detail(detail)
            if url:
                book_url = url
            if detail:
                rows = review_summary_rows(detail, last_args) or rows
            session.set("hotel_detail", detail_text)
        except Exception as exc:
            ctx.logger.warning(f"select_hotel_options failed: {exc}")

    if not book_url:
        await ctx.send(
            sender,
            card_message(
                "custom",
                error_card("Could not get a booking link. Please try another hotel."),
            ),
        )
        return

    session.update(selected=selection, book_url=book_url)
    session.save()
    await ctx.send(
        sender,
        card_message(
            "review",
            booking_review_card("Confirm your booking", rows, book_url),
        ),
    )


async def handle_open_book(
    ctx: Context,
    sender: str,
    session: SessionStore,
    selection: dict,
) -> None:
    book_url = selection.get("book_url") or session.get("book_url", "")
    if not book_url:
        await ctx.send(
            sender,
            card_message(
                "custom", error_card("No booking link found. Please search again.")
            ),
        )
        return
    title = _booking_title(session)
    await send_booking_link(ctx, sender, session, book_url, title)


def _booking_title(session: SessionStore) -> str:
    selected = session.get("selected", {})
    item = session.lookup_item(
        selected.get("package_id")
        or selected.get("offer_id")
        or selected.get("hotel_id", "")
    )
    if item.get("name"):
        return item["name"]
    if item.get("hotel_name"):
        return item["hotel_name"]
    if item.get("airline"):
        return item["airline"]
    return "Your trip"


def _carousel_subtitle(tool: str, args: dict) -> str:
    if tool == "search_only_hotel":
        return args.get("destination", "")
    return (
        f"{args.get('origin', args.get('departure', ''))} → "
        f"{args.get('destination', args.get('arrival', ''))}"
    )


async def handle_card_action(
    ctx: Context,
    sender: str,
    session: SessionStore,
    selection: dict,
) -> bool:
    action = selection.get("action") or selection.get("step")

    if selection.get("offer_id") and not action:
        selection = {**selection, "action": "pick_flight"}
        action = "pick_flight"

    if selection.get("package_id") and not action:
        selection = {**selection, "action": "pick_package"}
        action = "pick_package"

    if selection.get("hotel_id") and not action:
        selection = {**selection, "action": "pick_hotel"}
        action = "pick_hotel"

    if action == "submit_search":
        from tripmate.forms import build_search_args

        tool_name, args = build_search_args(selection)
        await search_and_reply(ctx, sender, session, tool_name, args)
        return True

    if action == "pick_package":
        await handle_pick_package(ctx, sender, session, selection)
        return True

    if action == "pick_flight":
        await handle_pick_flight(ctx, sender, session, selection)
        return True

    if action == "pick_hotel":
        await handle_pick_hotel(ctx, sender, session, selection)
        return True

    if action in ("open_book", "confirm", "approve"):
        await handle_open_book(ctx, sender, session, selection)
        return True

    if action in ("submit_passenger", "submit"):
        session.update(passenger=selection)
        session.save()
        await ctx.send(sender, card_message("form", search_form_card()))
        return True

    if action == "more_options":
        last = session.get("last_results", "")
        tool = session.get("last_search", {}).get("tool", "search_flights")
        args = session.get("last_search", {}).get("args", {})
        parsed = results_to_carousel(tool, last, _carousel_subtitle(tool, args))
        if parsed:
            kind, payload = parsed
            await ctx.send(sender, card_message(kind, payload))
        else:
            await ctx.send(sender, card_message("form", search_form_card()))
        return True

    if action == "book_opened":
        ctx.logger.info("Booking page opened in new tab")
        return True

    if action == "back":
        last = session.get("last_results", "")
        tool = session.get("last_search", {}).get("tool", "search_flights")
        args = session.get("last_search", {}).get("args", {})
        parsed = results_to_carousel(tool, last, _carousel_subtitle(tool, args))
        if parsed:
            kind, payload = parsed
            await ctx.send(sender, card_message(kind, payload))
        else:
            await ctx.send(sender, card_message("form", search_form_card()))
        return True

    if action == "cancel":
        session.clear()
        await ctx.send(sender, card_message("form", search_form_card()))
        return True

    return False


async def on_chat_message(ctx: Context, sender: str, msg: ChatMessage) -> None:
    user_text = "".join(
        c.text for c in msg.content if isinstance(c, TextContent)
    ).strip()
    ctx.logger.info(f"📩 From {sender[:16]}...: {user_text[:100]}")

    await ctx.send(
        sender,
        ChatAcknowledgement(
            timestamp=datetime.now(timezone.utc),
            acknowledged_msg_id=msg.msg_id,
        ),
    )

    session = SessionStore(ctx.storage, sender)
    clean_text = strip_agent_mention(user_text)
    selection = extract_selection(user_text)

    try:
        if is_card_action(selection):
            handled = await handle_card_action(ctx, sender, session, selection)
            if handled:
                return

        direct = parse_package_intent(clean_text)
        if direct:
            tool_name, args = direct
            await search_and_reply(ctx, sender, session, tool_name, args)
            return

        if not clean_text or clean_text.lower() in {"hi", "hello", "start", "help"}:
            await ctx.send(sender, card_message("form", search_form_card()))
            return

        if needs_passenger_form(clean_text):
            await ctx.send(
                sender, card_message("custom", passenger_details_form_card())
            )
            return

        session.add_history("user", clean_text)
        reply = await run_graph(clean_text, thread_id=sender)

        from tripmate.tool_results import pop_tool_result

        tool_result = pop_tool_result(sender)
        if tool_result:
            session.remember_search(
                tool_result["tool"],
                tool_result["args"],
                tool_result["raw"],
                tool_result["index"],
            )
            parsed = results_to_carousel(
                tool_result["tool"],
                tool_result["raw"],
                _carousel_subtitle(tool_result["tool"], tool_result["args"]),
            )
            if parsed:
                kind, payload = parsed
                await ctx.send(sender, card_message(kind, payload))
                return

        session.add_history("assistant", reply)
        await ctx.send(sender, card_message("form", search_form_card()))

    except Exception as exc:
        ctx.logger.exception("Handler error")
        await ctx.send(
            sender, card_message("custom", error_card(f"Something went wrong: {exc}"))
        )
