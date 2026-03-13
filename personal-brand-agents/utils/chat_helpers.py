from uagents_core.contrib.protocols.chat import ChatMessage, MetadataContent, TextContent

def is_sent_by_asione(msg: ChatMessage) -> bool:
    """Determines if a ChatMessage was sent by ASI:One"""
    return isinstance(msg.content[-1], MetadataContent)

def is_sent_by_agentverse(msg: ChatMessage) -> bool:
    """Determines if a ChatMessage was sent by a user through AgentVerse"""
    return isinstance(msg.content[-1], TextContent)

def get_chat_id_from_message(msg: ChatMessage):
    """Extracts the chat id from a ChatMessage if it was sent by ASI:One"""
    chat_id = None
    for content in msg.content:
        if isinstance(content, MetadataContent):
            if "x-session-id" in content.metadata:
                chat_id = content.metadata["x-session-id"]
                break
    return chat_id

def get_human_input_from_message(msg: ChatMessage):
    """Extracts the user message text from a ChatMessage if it was sent by a user"""
    user_text = None
    for content in msg.content:
        if isinstance(content, TextContent):
            user_text = content.text
            break
    return user_text
