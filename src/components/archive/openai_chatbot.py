from openai import OpenAI


class ChatBot:
    def __init__(self, llm):
        self.llm = llm

    def ask(self, messages: list[dict]) -> str:
        chat_completion = self.llm.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=messages.messages,
            temperature=0,
        )
        assistant_response = chat_completion.choices[0].message.content
        return assistant_response


# def on_connect(user_id, connection):
#     sessions[user_id] = Chatbot(connection)

# def on_message(user_id, query):
#     sessions[user_id].ask(query)
