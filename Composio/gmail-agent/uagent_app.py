from datetime import datetime, timezone
from uuid import uuid4
import os
import re
from dotenv import load_dotenv
from uagents import Context, Protocol, Agent
from uagents_core.contrib.protocols.chat import (
    ChatAcknowledgement,
    ChatMessage,
    TextContent,
    chat_protocol_spec,
)

from tools import (
    get_gmail_tools_for_user,
    get_gmail_reply_tools_for_user,
    get_gmail_trash_tools_for_user,
    get_gmail_contacts_tools_for_user,
)
from llm import build_email_agent, run_email_task
from formatting import (
    extract_gmail_response,
    format_success_markdown,
    format_fetched_emails_markdown,
    format_reply_success_markdown,
    format_trash_success_markdown,
    format_contacts_markdown,
)
from system_prompt import DEFAULT_HELP_TEXT


load_dotenv()

agent = Agent(
    name="Gmail-Agent",
    seed="Gmail-ASI-Agent",
    port=8028,
    mailbox=True,
)

SENDER_TO_USER_EMAIL: dict[str, str] = {}


def send_gmail_email(recipient_email: str, subject: str, body: str, user_email: str):
    try:
        tools = get_gmail_tools_for_user(user_email)
        agent_executor = build_email_agent(tools)
        result = run_email_task(agent_executor, recipient_email, subject, body)
        return {"success": True, "result": result}
    except Exception as e:
        return {"success": False, "error": str(e)}


protocol = Protocol(spec=chat_protocol_spec)


@protocol.on_message(ChatMessage)
async def handle_message(ctx: Context, sender: str, msg: ChatMessage):
    await ctx.send(
        sender,
        ChatAcknowledgement(timestamp=datetime.now(), acknowledged_msg_id=msg.msg_id),
    )
    text = ""
    for item in msg.content:
        if isinstance(item, TextContent):
            text += item.text

    response = "Hello! I'm your Gmail agent. I can help you send emails."

    lower_text = text.lower()

    if ("fetch" in lower_text and "inbox" in lower_text) or any(keyword in lower_text for keyword in ["fetch emails", "get inbox", "list emails"]):
        try:
            # default: last 10 inbox
            email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
            emails = re.findall(email_pattern, text)
            if emails:
                SENDER_TO_USER_EMAIL[sender] = emails[0]
            user_email = SENDER_TO_USER_EMAIL.get(sender)
            if not user_email:
                response = (
                    "❌ Please connect your Gmail first or include 'From: you@example.com'.\n"
                    "Say: 'Connect to my mail you@example.com' then authorize, or include your email."
                )
            else:
                # parse requested count (e.g., "fetch 10 emails")
                import re as _re
                count = 10
                m = _re.search(r"\b(\d{1,3})\b", lower_text)
                if m:
                    try:
                        count = max(1, min(500, int(m.group(1))))
                    except Exception:
                        count = 10

                # Execute GMAIL_FETCH_EMAILS directly via the tool to avoid LLM context bloat
                from tools import get_gmail_fetch_tools_for_user
                tools = get_gmail_fetch_tools_for_user(user_email)
                fetch_tool = tools[0] if tools else None
                if not fetch_tool:
                    response = "❌ Fetch tool unavailable. Please try reconnecting your Gmail."
                else:
                    params = {
                        "ids_only": False,
                        "include_payload": False,
                        "include_spam_trash": False,
                        "label_ids": ["INBOX"],
                        "max_results": count,
                        "user_id": "me",
                        "verbose": False,
                    }
                    try:
                        result = fetch_tool.invoke(params)
                    except Exception:
                        # Some tool wrappers accept string input
                        import json as _json
                        result = fetch_tool.run(_json.dumps(params))

                    # Parse result
                    messages = []
                    next_token = None
                    estimate = 0
                    try:
                        data = result
                        if isinstance(result, str):
                            import ast
                            brace_idx = result.find("{")
                            if brace_idx != -1:
                                data = ast.literal_eval(result[brace_idx:])
                        if isinstance(data, dict):
                            wrapper = data
                            resp_data = wrapper.get("data", {})
                            messages = resp_data.get("messages", [])
                            next_token = resp_data.get("nextPageToken")
                            estimate = resp_data.get("resultSizeEstimate", 0)
                    except Exception:
                        pass

                    response = format_fetched_emails_markdown(messages, next_token, estimate)
        except Exception as e:
            response = f"❌ Error fetching emails: {str(e)}"

    elif any(keyword in lower_text for keyword in ["move to trash", "trash message", "delete email", "move email to trash"]):
        try:
            # Expect: message id and optional From
            message_id = ""
            sender_email = ""
            lines = text.split('\n')
            parts = text.split(',') if ',' in text else lines
            for part in parts:
                segment = part.strip()
                lower = segment.lower()
                if "message id:" in lower or lower.startswith("id:"):
                    raw_id = segment.split(":", 1)[1].strip()
                    # Extract clean message id token (avoid trailing text like 'From: ...')
                    import re as _re2
                    m_id = _re2.search(r"([0-9A-Za-z]+)", raw_id)
                    message_id = m_id.group(1) if m_id else raw_id.split()[0].rstrip(",")
                elif "from:" in lower or "sender:" in lower:
                    sender_email = segment.split(":", 1)[1].strip()

            if sender_email:
                SENDER_TO_USER_EMAIL[sender] = sender_email
            else:
                sender_email = SENDER_TO_USER_EMAIL.get(sender)

            if not sender_email:
                response = (
                    "❌ Please specify your email using 'From: you@example.com' "
                    "or connect first: 'Connect to my mail you@example.com'"
                )
            elif not message_id:
                response = "❌ Please provide a Message Id. Example: Message Id: 1875f42779f726f2"
            else:
                tools = get_gmail_trash_tools_for_user(sender_email)
                tool = tools[0] if tools else None
                if not tool:
                    response = "❌ Trash tool unavailable. Please reconnect your Gmail."
                else:
                    params = {"message_id": message_id, "user_id": "me"}
                    try:
                        result = tool.invoke(params)
                    except Exception:
                        import json as _json
                        result = tool.run(_json.dumps(params))

                    msg_id = message_id
                    thread_id = None
                    labels = None
                    try:
                        data = result
                        if isinstance(result, str):
                            import ast
                            brace_idx = result.find("{")
                            if brace_idx != -1:
                                data = ast.literal_eval(result[brace_idx:])
                        if isinstance(data, dict):
                            email_obj = data.get("data", {}).get("email", {})
                            msg_id = email_obj.get("id", msg_id)
                            thread_id = email_obj.get("threadId")
                            labels = email_obj.get("labelIds")
                    except Exception:
                        pass

                    response = format_trash_success_markdown(msg_id, thread_id, labels)
        except Exception as e:
            response = f"❌ Error moving to trash: {str(e)}"

    elif any(keyword in lower_text for keyword in ["get contacts", "list contacts", "fetch contacts", "my contacts"]):
        try:
            sender_email = ""
            lines = text.split('\n')
            parts = text.split(',') if ',' in text else lines
            for part in parts:
                segment = part.strip()
                lower = segment.lower()
                if "from:" in lower or "sender:" in lower:
                    sender_email = segment.split(":", 1)[1].strip()

            if sender_email:
                SENDER_TO_USER_EMAIL[sender] = sender_email
            else:
                sender_email = SENDER_TO_USER_EMAIL.get(sender)

            if not sender_email:
                response = (
                    "❌ Please specify your email using 'From: you@example.com' "
                    "or connect first: 'Connect to my mail you@example.com'"
                )
            else:
                tools = get_gmail_contacts_tools_for_user(sender_email)
                tool = tools[0] if tools else None
                if not tool:
                    response = "❌ Contacts tool unavailable. Please reconnect your Gmail."
                else:
                    params = {
                        "include_other_contacts": True,
                        "resource_name": "people/me",
                        "person_fields": "names,emailAddresses",
                    }
                    try:
                        result = tool.invoke(params)
                    except Exception:
                        import json as _json
                        result = tool.run(_json.dumps(params))

                    connections = []
                    next_token = None
                    try:
                        data = result
                        if isinstance(result, str):
                            import ast
                            brace_idx = result.find("{")
                            if brace_idx != -1:
                                data = ast.literal_eval(result[brace_idx:])
                        if isinstance(data, dict):
                            resp = data.get("data", {}).get("response_data", {})
                            connections = resp.get("connections", [])
                            next_token = resp.get("nextPageToken")
                    except Exception:
                        pass

                    response = format_contacts_markdown(connections, next_token)
        except Exception as e:
            response = f"❌ Error fetching contacts: {str(e)}"

    elif any(keyword in lower_text for keyword in ["search contacts", "search people", "find contact", "find people"]):
        try:
            # Expect: query; optional other_contacts/pageSize/person_fields; optional From
            sender_email = ""
            query = ""
            other_contacts = True
            page_size = 10
            person_fields = "emailAddresses,names,phoneNumbers"
            lines = text.split('\n')
            parts = text.split(',') if ',' in text else lines
            for part in parts:
                segment = part.strip()
                lower = segment.lower()
                if lower.startswith("query:"):
                    query = segment.split(":", 1)[1].strip()
                elif "other_contacts:" in lower:
                    flag = segment.split(":", 1)[1].strip().lower()
                    other_contacts = flag in ["1", "true", "yes"]
                elif "pagesize:" in lower:
                    try:
                        page_size = max(1, min(30, int(segment.split(":", 1)[1].strip())))
                    except Exception:
                        page_size = 10
                elif "person_fields:" in lower:
                    person_fields = segment.split(":", 1)[1].strip()
                elif "from:" in lower or "sender:" in lower:
                    sender_email = segment.split(":", 1)[1].strip()

            if sender_email:
                SENDER_TO_USER_EMAIL[sender] = sender_email
            else:
                sender_email = SENDER_TO_USER_EMAIL.get(sender)

            if not sender_email:
                response = (
                    "❌ Please specify your email using 'From: you@example.com' "
                    "or connect first: 'Connect to my mail you@example.com'"
                )
            elif not query:
                # Allow simple language if no explicit Query: provided (e.g., "Search people Rishank Javar")
                import re as _re3
                m_q = _re3.search(r"search\s+(people|contacts)\s*[,\s]*(.*)", lower_text)
                if m_q and m_q.group(2).strip():
                    query = m_q.group(2).strip()
                else:
                    response = "❌ Please provide a search query. Example: Search people John Doe"
            else:
                from tools import get_gmail_search_people_tools_for_user
                tools = get_gmail_search_people_tools_for_user(sender_email)
                tool = tools[0] if tools else None
                if not tool:
                    response = "❌ Search people tool unavailable. Please reconnect your Gmail."
                else:
                    params = {
                        "query": query,
                        "other_contacts": other_contacts,
                        "pageSize": page_size,
                        "person_fields": person_fields,
                    }
                    try:
                        result = tool.invoke(params)
                    except Exception:
                        import json as _json
                        result = tool.run(_json.dumps(params))

                    results = []
                    next_token = None
                    try:
                        data = result
                        if isinstance(result, str):
                            import ast
                            brace_idx = result.find("{")
                            if brace_idx != -1:
                                data = ast.literal_eval(result[brace_idx:])
                        if isinstance(data, dict):
                            resp = data.get("data", {}).get("response_data", {})
                            raw_list = resp.get("results") or resp.get("connections") or []
                            # Normalize items that may be nested under 'person'
                            normalized = []
                            for item in raw_list:
                                if isinstance(item, dict) and isinstance(item.get("person"), dict):
                                    normalized.append(item["person"])
                                else:
                                    normalized.append(item)
                            results = normalized
                            next_token = resp.get("nextPageToken")
                    except Exception:
                        pass

                    from formatting import format_people_search_markdown
                    response = format_people_search_markdown(results, next_token)

                    # Fallback: if empty, fetch contacts and filter locally for a best-effort match
                    if not results and query:
                        try:
                            ctools = get_gmail_contacts_tools_for_user(sender_email)
                            ctool = ctools[0] if ctools else None
                            if ctool:
                                cparams = {
                                    "include_other_contacts": True,
                                    "resource_name": "people/me",
                                    "person_fields": "names,emailAddresses",
                                }
                                try:
                                    cres = ctool.invoke(cparams)
                                except Exception:
                                    import json as _json
                                    cres = ctool.run(_json.dumps(cparams))
                                cdata = cres
                                if isinstance(cres, str):
                                    import ast
                                    brace_idx2 = cres.find("{")
                                    if brace_idx2 != -1:
                                        cdata = ast.literal_eval(cres[brace_idx2:])
                                connections = []
                                if isinstance(cdata, dict):
                                    connections = cdata.get("data", {}).get("response_data", {}).get("connections", [])
                                q = query.lower()
                                filtered = []
                                for person in connections:
                                    names = [n.get("displayName", "") for n in (person.get("names") or [])]
                                    emails = [e.get("value", "") for e in (person.get("emailAddresses") or [])]
                                    if any(q in n.lower() for n in names) or any(q in e.lower() for e in emails):
                                        filtered.append(person)
                                response = format_people_search_markdown(filtered[:10], None)
                        except Exception:
                            pass
        except Exception as e:
            response = f"❌ Error searching people: {str(e)}"

    elif any(keyword in lower_text for keyword in ["fetch thread", "get thread messages", "messages in thread"]):
        try:
            # Expect: Thread Id; optional From
            sender_email = ""
            thread_id = ""
            parts = text.split(',') if ',' in text else text.split('\n')
            for part in parts:
                segment = part.strip()
                lower = segment.lower()
                if "thread id:" in lower or lower.startswith("thread:"):
                    thread_id = segment.split(":", 1)[1].strip()
                elif "from:" in lower or "sender:" in lower:
                    sender_email = segment.split(":", 1)[1].strip()

            if sender_email:
                SENDER_TO_USER_EMAIL[sender] = sender_email
            else:
                sender_email = SENDER_TO_USER_EMAIL.get(sender)

            if not sender_email:
                response = (
                    "❌ Please specify your email using 'From: you@example.com' "
                    "or connect first: 'Connect to my mail you@example.com'"
                )
            elif not thread_id:
                response = "❌ Please provide a Thread Id. Example: Thread Id: 1995..."
            else:
                from tools import get_gmail_thread_fetch_tools_for_user
                tools = get_gmail_thread_fetch_tools_for_user(sender_email)
                tool = tools[0] if tools else None
                if not tool:
                    response = "❌ Fetch thread tool unavailable. Please reconnect your Gmail."
                else:
                    params = {
                        "thread_id": thread_id,
                        "user_id": "me",
                        "ids_only": False,
                        "include_payload": False,
                        "verbose": True,
                    }
                    try:
                        result = tool.invoke(params)
                    except Exception:
                        import json as _json
                        result = tool.run(_json.dumps(params))

                    from formatting import format_thread_messages_markdown
                    messages = []
                    next_token = None
                    try:
                        data = result
                        if isinstance(result, str):
                            import ast
                            brace_idx = result.find("{")
                            if brace_idx != -1:
                                data = ast.literal_eval(result[brace_idx:])
                        if isinstance(data, dict):
                            # Prefer response_data if present, fallback to data, then top-level
                            resp = (
                                data.get("data", {}).get("response_data")
                                or data.get("data")
                                or data
                            )
                            if not isinstance(resp, dict):
                                resp = {}
                            # Try common locations for messages array
                            raw_messages = (
                                resp.get("messages")
                                or resp.get("thread", {}).get("messages")
                                or resp.get("emails")
                                or resp.get("items")
                                or resp.get("list")
                                or []
                            )
                            if isinstance(raw_messages, dict) and "messages" in raw_messages:
                                raw_messages = raw_messages.get("messages", [])
                            if not raw_messages and (resp.get("message") or resp.get("email")):
                                candidate = resp.get("message") or resp.get("email")
                                raw_messages = [candidate] if isinstance(candidate, dict) else []

                            # Normalize message fields for formatter
                            normalized = []
                            for m in raw_messages:
                                if not isinstance(m, dict):
                                    continue
                                mm = dict(m)
                                if "messageId" not in mm and mm.get("id"):
                                    mm["messageId"] = mm.get("id")
                                if "threadId" not in mm and (mm.get("thread_id") or mm.get("threadId")):
                                    mm["threadId"] = mm.get("thread_id") or mm.get("threadId")
                                if "sender" not in mm:
                                    mm["sender"] = mm.get("from") or mm.get("From") or mm.get("sender")
                                if "to" not in mm:
                                    mm["to"] = mm.get("to") or mm.get("To")
                                if not mm.get("subject") and (mm.get("Subject") is not None):
                                    mm["subject"] = mm.get("Subject")
                                if "messageTimestamp" not in mm:
                                    ts = mm.get("timestamp") or mm.get("date") or mm.get("Date") or mm.get("internalDate")
                                    if ts:
                                        mm["messageTimestamp"] = ts
                                if "messageText" not in mm:
                                    mm["messageText"] = mm.get("text") or mm.get("snippet") or ""
                                if "labelIds" not in mm and mm.get("labels"):
                                    mm["labelIds"] = mm.get("labels")
                                normalized.append(mm)
                            messages = normalized

                            next_token = (
                                resp.get("nextPageToken")
                                or data.get("data", {}).get("nextPageToken")
                            )
                    except Exception:
                        pass

                    response = format_thread_messages_markdown(messages, next_token)
        except Exception as e:
            response = f"❌ Error fetching thread messages: {str(e)}"

    elif any(keyword in lower_text for keyword in ["get profile", "my profile", "gmail profile"]):
        try:
            sender_email = ""
            parts = text.split(',') if ',' in text else text.split('\n')
            for part in parts:
                segment = part.strip()
                lower = segment.lower()
                if "from:" in lower or "sender:" in lower:
                    sender_email = segment.split(":", 1)[1].strip()

            if sender_email:
                SENDER_TO_USER_EMAIL[sender] = sender_email
            else:
                sender_email = SENDER_TO_USER_EMAIL.get(sender)

            if not sender_email:
                response = (
                    "❌ Please specify your email using 'From: you@example.com' "
                    "or connect first: 'Connect to my mail you@example.com'"
                )
            else:
                from tools import get_gmail_profile_tools_for_user
                tools = get_gmail_profile_tools_for_user(sender_email)
                tool = tools[0] if tools else None
                if not tool:
                    response = "❌ Profile tool unavailable. Please reconnect your Gmail."
                else:
                    params = {"user_id": "me"}
                    try:
                        result = tool.invoke(params)
                    except Exception:
                        import json as _json
                        result = tool.run(_json.dumps(params))

                    profile = {}
                    try:
                        data = result
                        if isinstance(result, str):
                            import ast
                            brace_idx = result.find("{")
                            if brace_idx != -1:
                                data = ast.literal_eval(result[brace_idx:])
                        if isinstance(data, dict):
                            profile = data.get("data", {}).get("response_data", {})
                    except Exception:
                        pass

                    from formatting import format_profile_markdown
                    response = format_profile_markdown(profile)
        except Exception as e:
            response = f"❌ Error fetching profile: {str(e)}"

    
    elif any(keyword in lower_text for keyword in ["list drafts", "show drafts", "my drafts"]):
        try:
            sender_email = ""
            max_results = 10
            parts = text.split(',') if ',' in text else text.split('\n')
            for part in parts:
                segment = part.strip()
                lower = segment.lower()
                if "from:" in lower or "sender:" in lower:
                    sender_email = segment.split(":", 1)[1].strip()
                elif "max:" in lower or "max results:" in lower:
                    try:
                        max_results = max(1, min(100, int(segment.split(":", 1)[1].strip())))
                    except Exception:
                        max_results = 10

            if sender_email:
                SENDER_TO_USER_EMAIL[sender] = sender_email
            else:
                sender_email = SENDER_TO_USER_EMAIL.get(sender)

            if not sender_email:
                response = (
                    "❌ Please specify your email using 'From: you@example.com' "
                    "or connect first: 'Connect to my mail you@example.com'"
                )
            else:
                from tools import get_gmail_list_drafts_tools_for_user
                tools = get_gmail_list_drafts_tools_for_user(sender_email)
                tool = tools[0] if tools else None
                if not tool:
                    response = "❌ List drafts tool unavailable. Please reconnect your Gmail."
                else:
                    params = {"max_results": max_results, "user_id": "me", "verbose": True}
                    try:
                        result = tool.invoke(params)
                    except Exception:
                        import json as _json
                        result = tool.run(_json.dumps(params))

                    drafts = []
                    next_token = None
                    try:
                        data = result
                        if isinstance(result, str):
                            import ast
                            brace_idx = result.find("{")
                            if brace_idx != -1:
                                data = ast.literal_eval(result[brace_idx:])
                        if isinstance(data, dict):
                            resp = data.get("data", {}).get("response_data", {})
                            drafts = resp.get("drafts", [])
                            next_token = resp.get("nextPageToken")
                    except Exception:
                        pass

                    from formatting import format_drafts_list_markdown
                    response = format_drafts_list_markdown(drafts, next_token)
        except Exception as e:
            response = f"❌ Error listing drafts: {str(e)}"

    elif any(keyword in lower_text for keyword in ["create draft", "draft email", "save draft"]):
        try:
            # Expect: To, Subject, Body, optional HTML, optional From
            lines = text.split('\n')
            recipient = ""
            subject = ""
            body = ""
            is_html = False
            sender_email = ""
            parts = text.split(',') if ',' in text else lines
            for part in parts:
                segment = part.strip()
                lower = segment.lower()
                if "to:" in lower or "recipient:" in lower:
                    recipient = segment.split(":", 1)[1].strip()
                elif "subject:" in lower:
                    subject = segment.split(":", 1)[1].strip()
                elif "body:" in lower or "message:" in lower:
                    body = segment.split(":", 1)[1].strip()
                elif "html:" in lower:
                    flag = segment.split(":", 1)[1].strip().lower()
                    is_html = flag in ["1", "true", "yes"]
                elif "from:" in lower or "sender:" in lower:
                    sender_email = segment.split(":", 1)[1].strip()

            if sender_email:
                SENDER_TO_USER_EMAIL[sender] = sender_email
            else:
                sender_email = SENDER_TO_USER_EMAIL.get(sender)

            if not sender_email:
                response = (
                    "❌ Please specify your email using 'From: you@example.com' "
                    "or connect first: 'Connect to my mail you@example.com'"
                )
            elif not recipient or not subject or not body:
                response = "❌ Provide To, Subject, and Body to create a draft."
            else:
                from tools import get_gmail_draft_tools_for_user
                tools = get_gmail_draft_tools_for_user(sender_email)
                # First tool should be create draft
                create_tool = None
                for t in tools:
                    if getattr(t, "name", "") == "GMAIL_CREATE_EMAIL_DRAFT" or getattr(t, "slug", "") == "GMAIL_CREATE_EMAIL_DRAFT":
                        create_tool = t
                        break
                if not create_tool:
                    create_tool = tools[0] if tools else None
                if not create_tool:
                    response = "❌ Draft tool unavailable. Please reconnect your Gmail."
                else:
                    params = {
                        "recipient_email": recipient,
                        "subject": subject,
                        "body": body,
                        "is_html": is_html,
                        "user_id": "me",
                    }
                    try:
                        result = create_tool.invoke(params)
                    except Exception:
                        import json as _json
                        result = create_tool.run(_json.dumps(params))

                    draft_id = None
                    thread_id = None
                    try:
                        data = result
                        if isinstance(result, str):
                            import ast
                            brace_idx = result.find("{")
                            if brace_idx != -1:
                                data = ast.literal_eval(result[brace_idx:])
                        if isinstance(data, dict):
                            resp = data.get("data", {}).get("response_data", {})
                            draft_id = resp.get("id") or resp.get("draftId")
                            thread_id = resp.get("threadId")
                    except Exception:
                        pass

                    from formatting import format_draft_created_markdown
                    response = format_draft_created_markdown(draft_id or '(unknown)', thread_id, recipient, subject)
        except Exception as e:
            response = f"❌ Error creating draft: {str(e)}"

    elif any(keyword in lower_text for keyword in ["send draft", "deliver draft"]):
        try:
            # Expect: Draft Id, optional From
            draft_id = ""
            sender_email = ""
            parts = text.split(',') if ',' in text else text.split('\n')
            for part in parts:
                segment = part.strip()
                lower = segment.lower()
                if "draft id:" in lower or lower.startswith("draft:"):
                    draft_id = segment.split(":", 1)[1].strip()
                elif "from:" in lower or "sender:" in lower:
                    sender_email = segment.split(":", 1)[1].strip()

            if sender_email:
                SENDER_TO_USER_EMAIL[sender] = sender_email
            else:
                sender_email = SENDER_TO_USER_EMAIL.get(sender)

            if not sender_email:
                response = (
                    "❌ Please specify your email using 'From: you@example.com' "
                    "or connect first: 'Connect to my mail you@example.com'"
                )
            elif not draft_id:
                response = "❌ Please provide a Draft Id. Example: Draft Id: r123..."
            else:
                from tools import get_gmail_draft_tools_for_user
                tools = get_gmail_draft_tools_for_user(sender_email)
                send_tool = None
                for t in tools:
                    if getattr(t, "name", "") == "GMAIL_SEND_DRAFT" or getattr(t, "slug", "") == "GMAIL_SEND_DRAFT":
                        send_tool = t
                        break
                if not send_tool:
                    send_tool = tools[0] if tools else None
                if not send_tool:
                    response = "❌ Send draft tool unavailable. Please reconnect your Gmail."
                else:
                    params = {"draft_id": draft_id, "user_id": "me"}
                    try:
                        _ = send_tool.invoke(params)
                    except Exception:
                        import json as _json
                        _ = send_tool.run(_json.dumps(params))

                    from formatting import format_draft_sent_markdown
                    response = format_draft_sent_markdown(draft_id)
        except Exception as e:
            response = f"❌ Error sending draft: {str(e)}"

    elif any(keyword in lower_text for keyword in ["delete draft", "remove draft", "trash draft"]):
        try:
            # Expect: Draft Id, optional From
            draft_id = ""
            sender_email = ""
            parts = text.split(',') if ',' in text else text.split('\n')
            for part in parts:
                segment = part.strip()
                lower = segment.lower()
                if "draft id:" in lower or lower.startswith("draft:"):
                    draft_id = segment.split(":", 1)[1].strip()
                elif "from:" in lower or "sender:" in lower:
                    sender_email = segment.split(":", 1)[1].strip()

            if sender_email:
                SENDER_TO_USER_EMAIL[sender] = sender_email
            else:
                sender_email = SENDER_TO_USER_EMAIL.get(sender)

            if not sender_email:
                response = (
                    "❌ Please specify your email using 'From: you@example.com' "
                    "or connect first: 'Connect to my mail you@example.com'"
                )
            elif not draft_id:
                response = "❌ Please provide a Draft Id. Example: Draft Id: r123..."
            else:
                from tools import get_gmail_draft_tools_for_user
                tools = get_gmail_draft_tools_for_user(sender_email)
                del_tool = None
                for t in tools:
                    if getattr(t, "name", "") == "GMAIL_DELETE_DRAFT" or getattr(t, "slug", "") == "GMAIL_DELETE_DRAFT":
                        del_tool = t
                        break
                if not del_tool:
                    del_tool = tools[0] if tools else None
                if not del_tool:
                    response = "❌ Delete draft tool unavailable. Please reconnect your Gmail."
                else:
                    params = {"draft_id": draft_id, "user_id": "me"}
                    try:
                        _ = del_tool.invoke(params)
                    except Exception:
                        import json as _json
                        _ = del_tool.run(_json.dumps(params))

                    from formatting import format_draft_deleted_markdown
                    response = format_draft_deleted_markdown(draft_id)
        except Exception as e:
            response = f"❌ Error deleting draft: {str(e)}"
    elif any(keyword in lower_text for keyword in ["reply", "reply to", "respond", "answer"]):
        try:
            # Extract thread id, recipient, body, optional flags
            lines = text.split('\n')
            thread_id = ""
            recipient = ""
            body = ""
            is_html = False
            sender_email = ""

            # Accept comma-separated or multi-line
            parts = text.split(",") if "," in text else lines
            for part in parts:
                segment = part.strip()
                lower = segment.lower()
                if "thread id:" in lower or "thread:" in lower:
                    thread_id = segment.split(":", 1)[1].strip()
                elif "to:" in lower or "recipient:" in lower:
                    recipient = segment.split(":", 1)[1].strip()
                elif "body:" in lower or "message:" in lower:
                    body = segment.split(":", 1)[1].strip()
                elif "html:" in lower:
                    flag = segment.split(":", 1)[1].strip().lower()
                    is_html = flag in ["1", "true", "yes"]
                elif "from:" in lower or "sender:" in lower:
                    sender_email = segment.split(":", 1)[1].strip()

            if sender_email:
                SENDER_TO_USER_EMAIL[sender] = sender_email
            else:
                remembered = SENDER_TO_USER_EMAIL.get(sender)
                if remembered:
                    sender_email = remembered
                else:
                    response = (
                        "❌ Please specify your email using 'From: you@example.com' "
                        "or connect first: 'Connect to my mail you@example.com'"
                    )

            if thread_id and recipient and body and sender_email:
                tools = get_gmail_reply_tools_for_user(sender_email)
                reply_tool = tools[0] if tools else None
                if not reply_tool:
                    response = "❌ Reply tool unavailable. Please reconnect your Gmail."
                else:
                    params = {
                        "thread_id": thread_id,
                        "recipient_email": recipient,
                        "message_body": body,
                        "is_html": is_html,
                        "user_id": "me",
                    }
                    try:
                        result = reply_tool.invoke(params)
                    except Exception:
                        import json as _json
                        result = reply_tool.run(_json.dumps(params))

                    # Extract message id if present
                    message_id = None
                    try:
                        data = result
                        if isinstance(result, str):
                            import ast
                            brace_idx = result.find("{")
                            if brace_idx != -1:
                                data = ast.literal_eval(result[brace_idx:])
                        if isinstance(data, dict):
                            resp = data.get("data", {}).get("response_data", {})
                            message_id = resp.get("id") or resp.get("messageId")
                    except Exception:
                        pass

                    response = format_reply_success_markdown(recipient, body, thread_id, message_id)
            else:
                response = (
                    "❌ Missing fields. Provide: Thread Id, To/Recipient, Body.\n"
                    "Example: Reply to: user@example.com, Thread Id: 1995..., Body: Thanks!"
                )
        except Exception as e:
            response = f"❌ Error replying to thread: {str(e)}"

    elif any(keyword in lower_text for keyword in ["send email", "send mail", "email to", "mail to"]):
        try:
            lines = text.split('\n')
            recipient = ""
            subject = ""
            body = ""
            sender_email = ""

            if "," in text:
                parts = text.split(",")
                for part in parts:
                    part = part.strip()
                    lower = part.lower()
                    if "to:" in lower or "recipient:" in lower:
                        recipient = part.split(":", 1)[1].strip()
                    elif "subject:" in lower:
                        subject = part.split(":", 1)[1].strip()
                    elif "body:" in lower or "message:" in lower:
                        body = part.split(":", 1)[1].strip()
                    elif "from:" in lower or "sender:" in lower:
                        sender_email = part.split(":", 1)[1].strip()
            else:
                for line in lines:
                    lower = line.lower()
                    if "to:" in lower or "recipient:" in lower:
                        recipient = line.split(":", 1)[1].strip()
                    elif "subject:" in lower:
                        subject = line.split(":", 1)[1].strip()
                    elif "body:" in lower or "message:" in lower:
                        body = line.split(":", 1)[1].strip()
                    elif "from:" in lower or "sender:" in lower:
                        sender_email = line.split(":", 1)[1].strip()

            if not subject:
                response = "❌ Please provide a subject. Include: Subject: Your subject"
            elif not body:
                response = "❌ Please provide a message body. Include: Body: Your message"
            if sender_email:
                SENDER_TO_USER_EMAIL[sender] = sender_email
            else:
                remembered = SENDER_TO_USER_EMAIL.get(sender)
                if remembered:
                    sender_email = remembered
                else:
                    response = (
                        "❌ Please specify your email address using 'From: you@example.com' "
                        "or connect first: 'Connect to my mail you@example.com'"
                    )

            if recipient and subject and body:
                email_result = send_gmail_email(recipient, subject, body, sender_email)
                if email_result.get("success"):
                    result_obj = email_result.get("result") or {}
                    meta = extract_gmail_response(result_obj.get("intermediate_steps", []))
                    response = format_success_markdown(
                        recipient=recipient,
                        sender_email=sender_email,
                        subject=subject,
                        body=body,
                        email_id=meta["email_id"],
                        thread_id=meta["thread_id"],
                        labels=meta["labels"],
                    )
                else:
                    response = f"❌ Failed to send email: {email_result.get('error', 'Unknown error')}"
            else:
                response = "❌ Please provide a recipient email address. Format: 'Send email to: email@example.com, Subject: Your Subject, Body: Your message'"
        except Exception as e:
            response = f"❌ Error processing email request: {str(e)}"

    elif "connect" in text.lower() and "mail" in text.lower():
        try:
            email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
            emails = re.findall(email_pattern, text)
            email = emails[0] if emails else ""
            if email:
                from tools import get_gmail_auth_url
                auth_result = get_gmail_auth_url(email)
                if auth_result["success"]:
                    SENDER_TO_USER_EMAIL[sender] = email
                    response = (
                        f"🔗 Gmail Auth URL for {email}:\n\n{auth_result['auth_url']}\n\n"
                        "1. Click the link above to authorize\n"
                        "2. Complete the OAuth flow\n"
                        "3. Come back and send emails using:\n"
                        f"'Send email to: recipient@example.com, Subject: Your Subject, Body: Your message"
                    )
                else:
                    response = (
                        f"❌ Error getting auth URL: {auth_result['error']}\n\n"
                        "Ensure GMAIL_AUTH_CONFIG_ID is set in your .env, or ask me: 'connect to my mail your@email.com'"
                    )
            else:
                response = "Please specify your email address. Example: 'Connect to my mail account your@email.com'"
        except Exception as e:
            response = f"Error setting up connection: {str(e)}"

    elif "help" in text.lower():
        response = DEFAULT_HELP_TEXT

    await ctx.send(sender, ChatMessage(
        timestamp=datetime.utcnow(),
        msg_id=uuid4(),
        content=[
            TextContent(type="text", text=response),
        ]
    ))


@protocol.on_message(ChatAcknowledgement)
async def handle_ack(ctx: Context, sender: str, msg: ChatAcknowledgement):
    pass


agent.include(protocol, publish_manifest=True)


