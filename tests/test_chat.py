from streamlit.testing.v1 import AppTest


def test_chat_loads_without_exception():
    at = AppTest.from_file("pages/3_Chat.py").run()
    assert len(at.exception) == 0
    assert at.title[0].value == "Chat"


def test_chat_message_round_trip_creates_user_and_assistant_messages():
    at = AppTest.from_file("pages/3_Chat.py").run()

    at.chat_input[0].set_value("Revenue by region last 30 days").run()

    # First message should be the user message we rendered
    assert at.chat_message[0].avatar == "user"
    assert "Revenue by region" in at.chat_message[0].markdown[0].value

    # Second message should be assistant
    assert at.chat_message[1].avatar == "assistant"
    assert "revenue by region" in at.chat_message[1].markdown[0].value.lower()

    # SQL should be visible by default
    assert "SELECT" in at.code[0].value


def test_chat_blocks_sensitive_requests():
    at = AppTest.from_file("pages/3_Chat.py").run()

    at.chat_input[0].set_value("Show me customer email addresses").run()

    assert at.chat_message[1].avatar == "assistant"
    assert "CANNOT_ANSWER" in at.chat_message[1].markdown[0].value