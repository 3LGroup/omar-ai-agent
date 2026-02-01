
end_call_function_schema = {
    "type": "function",
    "function": {
        "name": "end_call",
        "description": "End the call only after the user provides information about the booking or says thank you or goodbye",
        "parameters": {
            "type": "object",
            "properties": {
                "message": {
                    "type": "string",
                    "description": "The message you will say before ending the call with the customer.",
                }
            },
            "required": ["message"],
        },
    },
}

create_appointment_new_customer_schema = {
    "type": "function",
    "function": {
        "name": "create_appointment_new_customer",
        "description": "Create an appointment for a new customer. Call this whenever a new customer wants to book an appointment, but call this function only once. Do not call this function twice or multiple times.",
        "parameters": {
            "type": "object",
            "properties": {
                "firstName": {
                    "type": "string",
                    "description": "The first name of the customer.",
                },
                "lastName": {
                    "type": "string",
                    "description": "The last name of the customer.",
                },
                "phone": {
                    "type": "string",
                    "description": "The mobile number of the customer with country code (e.g., +1234567890)",
                },
                "startTime": {
                    "type": "string",
                    "description": "The start time of the appointment in ISO format YYYY-MM-DDTHH:MM:SS with timezone. e.g., 2025-10-14T04:30:00. Make sure not to change/convert the time provided by the user. This time must be in the future. Convert the time based on AM/PM to 24HR format.",
                },
                "context": {
                    "type": "string",
                    "description": "Summarize and store the context of the conversation with you. If you think the functionality of this function tool call has been completed, then do not call this function again in that conversation.",
                },
            },
            "required": ["firstName", "lastName", "phone", "startTime", "context"],
        }
    }
}

cancel_appointment_schema = {
    "type": "function",
    "function": {
        "name": "cancel_appointment",
        "description": "Cancel an appointment for a customer. Call this whenever a customer wants to cancel an appointment, but call this function only once. Do not call this function twice or multiple times.",
        "parameters": {
            "type": "object",
            "properties": {
                "startTime": {
                    "type": "string",
                    "description": "The start time of the appointment to cancel in ISO format YYYY-MM-DDTHH:MM:SS with timezone. e.g., 2025-10-14T04:30:00+05:00. Make sure not to change/convert the time provided by the user. Convert the time based on AM/PM to 24HR format.",
                },
                "context": {
                    "type": "string",
                    "description": "Summarize and store the context of the conversation with you. If you think the functionality of this function tool call has been completed, then do not call this function again in that conversation.",
                },
            },
            "required": ["startTime", "context"],
        }
    }
}

