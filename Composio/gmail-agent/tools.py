"""
Tooling setup via Composio and LangChain.
"""

import os
from composio import Composio
from composio_langchain import LangchainProvider


def get_composio_lc() -> Composio:
    return Composio(
        api_key=os.getenv("COMPOSIO_API_KEY", ""),
        provider=LangchainProvider(),
    )


def get_gmail_tools_for_user(user_email: str):
    composio_lc = get_composio_lc()
    return composio_lc.tools.get(user_id=user_email, tools=["GMAIL_SEND_EMAIL"])


def get_gmail_auth_url(user_email: str):
    try:
        composio = Composio(api_key=os.getenv("COMPOSIO_API_KEY", "ak_AzoffPhpAg169KC69x7a"))
        auth_config_id = os.getenv("GMAIL_AUTH_CONFIG_ID")
        if not auth_config_id:
            return {"success": False, "error": "Gmail Auth Config ID not found. Please set GMAIL_AUTH_CONFIG_ID in your .env file"}
        connection_request = composio.connected_accounts.initiate(
            user_id=user_email,
            auth_config_id=auth_config_id,
        )
        return {"success": True, "auth_url": connection_request.redirect_url}
    except Exception as e:
        return {"success": False, "error": str(e)}


def get_gmail_fetch_tools_for_user(user_email: str):
    composio_lc = get_composio_lc()
    return composio_lc.tools.get(user_id=user_email, tools=["GMAIL_FETCH_EMAILS"])


def get_tools_for_user(user_email: str, tool_slugs):
    composio_lc = get_composio_lc()
    return composio_lc.tools.get(user_id=user_email, tools=tool_slugs)


def get_gmail_reply_tools_for_user(user_email: str):
    composio_lc = get_composio_lc()
    return composio_lc.tools.get(user_id=user_email, tools=["GMAIL_REPLY_TO_THREAD"])


def get_gmail_trash_tools_for_user(user_email: str):
    composio_lc = get_composio_lc()
    return composio_lc.tools.get(user_id=user_email, tools=["GMAIL_MOVE_TO_TRASH"])


def get_gmail_contacts_tools_for_user(user_email: str):
    composio_lc = get_composio_lc()
    return composio_lc.tools.get(user_id=user_email, tools=["GMAIL_GET_CONTACTS"])


def get_gmail_search_people_tools_for_user(user_email: str):
    composio_lc = get_composio_lc()
    return composio_lc.tools.get(user_id=user_email, tools=["GMAIL_SEARCH_PEOPLE"])


def get_gmail_draft_tools_for_user(user_email: str):
    composio_lc = get_composio_lc()
    return composio_lc.tools.get(
        user_id=user_email,
        tools=["GMAIL_CREATE_EMAIL_DRAFT", "GMAIL_SEND_DRAFT", "GMAIL_DELETE_DRAFT"],
    )


def get_gmail_thread_fetch_tools_for_user(user_email: str):
    composio_lc = get_composio_lc()
    return composio_lc.tools.get(user_id=user_email, tools=["GMAIL_FETCH_MESSAGE_BY_THREAD_ID"])


def get_gmail_profile_tools_for_user(user_email: str):
    composio_lc = get_composio_lc()
    return composio_lc.tools.get(user_id=user_email, tools=["GMAIL_GET_PROFILE"])


def get_gmail_list_drafts_tools_for_user(user_email: str):
    composio_lc = get_composio_lc()
    # Try multiple possible slugs to maximize compatibility across Composio versions
    return composio_lc.tools.get(
        user_id=user_email,
        tools=[
            "GMAIL_LIST_DRAFTS",
            "GMAIL_LIST_EMAIL_DRAFTS",
            "GMAIL_GET_DRAFTS",
            "GMAIL_LIST_DRAFT",
        ],
    )


def get_gmail_message_by_id_tools_for_user(user_email: str):
    # Deprecated: removed fetch message by ID feature per request
    return []


