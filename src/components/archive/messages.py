from src.constants import INITIAL_MESSAGE


class Messages:
    def __init__(self):
        self.messages = [
            {
                "role": "system",
                "content": "You are an helpful healthcare phone assistant, you can help the patient/customer to book an appointment for the doctor by asking the name, date and time and reason for appointment.",
            },
            {"role": "assistant", "content": INITIAL_MESSAGE},
        ]

    def add_ai_message(self, message):
        self.messages.append(
            {
                "role": "assistant",
                "content": message,
            }
        )

    def add_user_message(self, message):
        self.messages.append(
            {
                "role": "user",
                "content": message,
            }
        )
