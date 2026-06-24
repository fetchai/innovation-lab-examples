"""
Expense split logic for group receipt calculator.
Each item is split only among members who marked they brought that item.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional


@dataclass
class ReceiptItem:
    """Single line item on the receipt."""

    index: int
    name: str
    price: Decimal

    def __str__(self) -> str:
        return f"{self.index}. {self.name} — ${self.price:.2f}"


class Receipt:
    """Receipt with items."""

    def __init__(self) -> None:
        self.items: list[ReceiptItem] = []

    def add_item(self, name: str, price: Decimal | float | str) -> ReceiptItem:
        idx = len(self.items) + 1
        item = ReceiptItem(index=idx, name=name.strip(), price=Decimal(str(price)))
        self.items.append(item)
        return item

    def total(self) -> Decimal:
        return sum(i.price for i in self.items)

    def format_items(self) -> str:
        if not self.items:
            return "No items yet."
        return "\n".join(str(i) for i in self.items)


def parse_item_selection(text: str, max_index: int) -> list[int]:
    """Parse reply like '1,2,3' or '1 2 3' into list of 1-based indices."""
    indices: list[int] = []
    normalized = text.replace(",", " ").replace(";", " ").replace(" and ", " ")
    for part in normalized.split():
        part = part.strip()
        if not part:
            continue
        if part.lower().startswith("item"):
            part = part[4:].strip()
        try:
            n = int(part)
            if 1 <= n <= max_index and n not in indices:
                indices.append(n)
        except ValueError:
            continue
    return sorted(indices)


def compute_splits(
    receipt: Receipt,
    selections: dict[str, list[int]],
    all_participants: Optional[list[str]] = None,
) -> dict:
    """
    Per item, split cost among everyone who brought that item.

    UX rules:
    - If no one mentioned an item, split it among all participants and add a note.
    - Tax-like items are always split among all participants and add a note.
    """
    per_person: dict[str, dict] = {}
    per_item: dict[int, dict] = {}
    participants = list(dict.fromkeys(all_participants or list(selections.keys())))
    tax_keywords = ("tax", "gst", "vat", "cgst", "sgst", "service charge")

    for item in receipt.items:
        item_name_lower = item.name.lower()
        is_tax_item = any(k in item_name_lower for k in tax_keywords)
        who_brought = [
            sid for sid, indices in selections.items() if item.index in indices
        ]

        note = None
        share_group = who_brought
        if is_tax_item and participants:
            share_group = participants
            note = "tax shared among all"
        elif not who_brought and participants:
            share_group = participants
            note = "no one mentioned it; shared among all"

        if not share_group:
            per_item[item.index] = {
                "name": item.name,
                "price": item.price,
                "shared_by": [],
                "share_each": Decimal("0"),
                "note": note,
            }
            continue
        share_each = item.price / len(share_group)
        per_item[item.index] = {
            "name": item.name,
            "price": item.price,
            "shared_by": share_group,
            "share_each": share_each,
            "note": note,
        }
        for sid in share_group:
            if sid not in per_person:
                per_person[sid] = {
                    "total": Decimal("0"),
                    "breakdown": [],
                    "item_indices": [],
                }
            per_person[sid]["total"] += share_each
            per_person[sid]["breakdown"].append((item.name, share_each))
            per_person[sid]["item_indices"].append(item.index)

    return {"per_person": per_person, "per_item": per_item}


def format_split_result(
    receipt: Receipt,
    selections: dict[str, list[int]],
    sender_display_names: Optional[dict[str, str]] = None,
    all_participants: Optional[list[str]] = None,
    payer_sender_id: Optional[str] = None,
    payer_display_name: Optional[str] = None,
) -> str:
    """Human-readable summary of who pays what. Uses display names only (no agent IDs)."""
    result = compute_splits(receipt, selections, all_participants=all_participants)
    per_person = result["per_person"]
    per_item = result["per_item"]

    def name(sid: str) -> str:
        return (sender_display_names or {}).get(sid) or "Unknown"

    # 1) Total expense per person (summary first)
    lines = [
        "📊 **Expense split**",
        "",
        "**Total per person:**",
        "",
    ]
    for sid, data in sorted(per_person.items(), key=lambda x: -x[1]["total"]):
        lines.append(f"• **{name(sid)}**: ${data['total']:.2f}")
    lines.append("")
    lines.append(f"**Receipt total:** ${receipt.total():.2f}")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("**Per item:**")
    lines.append("")
    for item in receipt.items:
        info = per_item.get(item.index, {})
        shared_by = info.get("shared_by", [])
        share_each = info.get("share_each", Decimal("0"))
        note = info.get("note")
        if shared_by:
            shared_names = ", ".join(name(sid) for sid in shared_by)
            line = (
                f"• {item.index}. {item.name} — ${item.price:.2f}\n"
                f"  Shared by ({len(shared_by)}): {shared_names}\n"
                f"  Split: ${share_each:.2f} each"
            )
            if note:
                line += f" [{note}]"
            lines.append(line)
        else:
            lines.append(
                f"• {item.index}. {item.name} — ${item.price:.2f}\n  No one claimed"
            )
        lines.append("")

    lines.append("**Breakdown per person:**")
    lines.append("")
    for sid, data in sorted(per_person.items(), key=lambda x: -x[1]["total"]):
        total = data["total"]
        breakdown = data["breakdown"]
        lines.append(f"**{name(sid)}**")
        lines.append(f"Total: ${total:.2f}")
        lines.append("")
        for item_name, share in breakdown:
            lines.append(f"- {item_name}: ${share:.2f}")
        lines.append("")

    # Settlement section: who should send money to payer
    effective_payer_sid = payer_sender_id
    if not effective_payer_sid and payer_display_name and sender_display_names:
        for sid, nm in sender_display_names.items():
            if (nm or "").strip().lower() == payer_display_name.strip().lower():
                effective_payer_sid = sid
                break

    if effective_payer_sid or payer_display_name:
        payer_name = payer_display_name or name(effective_payer_sid)
        lines.append("**Settlement:**")
        lines.append("")
        transfers = []
        for sid, data in sorted(per_person.items(), key=lambda x: -x[1]["total"]):
            if effective_payer_sid and sid == effective_payer_sid:
                continue
            amt = data["total"]
            if amt > 0:
                transfers.append((name(sid), amt))
        if transfers:
            for person_name, amt in transfers:
                lines.append(f"- {person_name} sends ${amt:.2f} to {payer_name}")
        else:
            lines.append("- No transfers needed.")
        lines.append("")

    return "\n".join(lines)


def format_split_summary(
    receipt: Receipt,
    selections: dict[str, list[int]],
    sender_display_names: Optional[dict[str, str]] = None,
    all_participants: Optional[list[str]] = None,
    payer_sender_id: Optional[str] = None,
    payer_display_name: Optional[str] = None,
) -> str:
    """Short summary: total per person only."""
    result = compute_splits(receipt, selections, all_participants=all_participants)
    per_person = result["per_person"]

    def name(sid: str) -> str:
        return (sender_display_names or {}).get(sid) or "Unknown"

    lines = [
        "📊 **Expense split (summary)**",
        "",
        "**Total per person:**",
        "",
    ]
    for sid, data in sorted(per_person.items(), key=lambda x: -x[1]["total"]):
        lines.append(f"• **{name(sid)}**: ${data['total']:.2f}")
    lines.append("")
    lines.append(f"**Receipt total:** ${receipt.total():.2f}")

    effective_payer_sid = payer_sender_id
    if not effective_payer_sid and payer_display_name and sender_display_names:
        for sid, nm in sender_display_names.items():
            if (nm or "").strip().lower() == payer_display_name.strip().lower():
                effective_payer_sid = sid
                break

    if effective_payer_sid or payer_display_name:
        payer_name = payer_display_name or name(effective_payer_sid)
        lines.append("")
        lines.append("**Settlement:**")
        lines.append("")
        transfers = []
        for sid, data in sorted(per_person.items(), key=lambda x: -x[1]["total"]):
            if effective_payer_sid and sid == effective_payer_sid:
                continue
            amt = data["total"]
            if amt > 0:
                transfers.append((name(sid), amt))
        if transfers:
            for person_name, amt in transfers:
                lines.append(f"- {person_name} sends ${amt:.2f} to {payer_name}")
        else:
            lines.append("- No transfers needed.")
    return "\n".join(lines)


def format_split_summary_table(
    receipt: Receipt,
    selections: dict[str, list[int]],
    sender_display_names: Optional[dict[str, str]] = None,
    all_participants: Optional[list[str]] = None,
    payer_sender_id: Optional[str] = None,
    payer_display_name: Optional[str] = None,
) -> str:
    """Compact markdown table summary for chat."""
    result = compute_splits(receipt, selections, all_participants=all_participants)
    per_person = result["per_person"]

    def name(sid: str) -> str:
        return (sender_display_names or {}).get(sid) or "Unknown"

    lines = [
        "📊 **Expense split (table)**",
        "",
        "| Person | Total | Items |",
        "|---|---:|---:|",
    ]
    for sid, data in sorted(per_person.items(), key=lambda x: -x[1]["total"]):
        lines.append(
            f"| {name(sid)} | ${data['total']:.2f} | {len(data.get('item_indices', []))} |"
        )
    lines.append("")
    lines.append(f"**Receipt total:** ${receipt.total():.2f}")

    effective_payer_sid = payer_sender_id
    if not effective_payer_sid and payer_display_name and sender_display_names:
        for sid, nm in sender_display_names.items():
            if (nm or "").strip().lower() == payer_display_name.strip().lower():
                effective_payer_sid = sid
                break

    if effective_payer_sid or payer_display_name:
        payer_name = payer_display_name or name(effective_payer_sid)
        lines.append("")
        lines.append("**Settlement**")
        lines.append("")
        lines.append("| From | To | Amount |")
        lines.append("|---|---|---:|")
        has_rows = False
        for sid, data in sorted(per_person.items(), key=lambda x: -x[1]["total"]):
            if effective_payer_sid and sid == effective_payer_sid:
                continue
            amt = data["total"]
            if amt > 0:
                lines.append(f"| {name(sid)} | {payer_name} | ${amt:.2f} |")
                has_rows = True
        if not has_rows:
            lines.append("| - | - | $0.00 |")
    return "\n".join(lines)


def format_split_full_table(
    receipt: Receipt,
    selections: dict[str, list[int]],
    sender_display_names: Optional[dict[str, str]] = None,
    all_participants: Optional[list[str]] = None,
    payer_sender_id: Optional[str] = None,
    payer_display_name: Optional[str] = None,
) -> str:
    """Compact full table: totals + per-item + settlement."""
    result = compute_splits(receipt, selections, all_participants=all_participants)
    per_person = result["per_person"]
    per_item = result["per_item"]

    def name(sid: str) -> str:
        return (sender_display_names or {}).get(sid) or "Unknown"

    lines = [
        "📊 **Expense split (full table)**",
        "",
        "**Totals by person**",
        "",
        "| Person | Total | Items |",
        "|---|---:|---:|",
    ]
    for sid, data in sorted(per_person.items(), key=lambda x: -x[1]["total"]):
        lines.append(
            f"| {name(sid)} | ${data['total']:.2f} | {len(data.get('item_indices', []))} |"
        )
    lines.append("")
    lines.append(f"**Receipt total:** ${receipt.total():.2f}")
    lines.append("")

    lines.extend(
        [
            "**Per-item split**",
            "",
            "| # | Item | Price | Shared By | Each | Note |",
            "|---:|---|---:|---|---:|---|",
        ]
    )
    for item in receipt.items:
        info = per_item.get(item.index, {})
        shared_by = info.get("shared_by", [])
        share_each = info.get("share_each", Decimal("0"))
        shared_names = ", ".join(name(sid) for sid in shared_by) if shared_by else "-"
        note = info.get("note") or "-"
        lines.append(
            f"| {item.index} | {item.name} | ${item.price:.2f} | {shared_names} | ${share_each:.2f} | {note} |"
        )

    effective_payer_sid = payer_sender_id
    if not effective_payer_sid and payer_display_name and sender_display_names:
        for sid, nm in sender_display_names.items():
            if (nm or "").strip().lower() == payer_display_name.strip().lower():
                effective_payer_sid = sid
                break

    if effective_payer_sid or payer_display_name:
        payer_name = payer_display_name or name(effective_payer_sid)
        lines.append("")
        lines.append("**Settlement**")
        lines.append("")
        lines.append("| From | To | Amount |")
        lines.append("|---|---|---:|")
        has_rows = False
        for sid, data in sorted(per_person.items(), key=lambda x: -x[1]["total"]):
            if effective_payer_sid and sid == effective_payer_sid:
                continue
            amt = data["total"]
            if amt > 0:
                lines.append(f"| {name(sid)} | {payer_name} | ${amt:.2f} |")
                has_rows = True
        if not has_rows:
            lines.append("| - | - | $0.00 |")
    return "\n".join(lines)
