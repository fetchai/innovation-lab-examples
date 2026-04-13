from app.models.messages import ChatRequest, ChatResponse


def test_chat_request_defaults() -> None:
    r = ChatRequest()
    assert r.session_id == ""
    assert r.appliance_type == ""


def test_chat_response() -> None:
    r = ChatResponse(session_id="x", markdown="# Hi", structured={"a": 1})
    assert r.session_id == "x"
