
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

send_email_function_schema = {
    "type": "function",
    "function": {
        "name": "send_email",
        "description": "Send an email to the user",
        "parameters": {
            "type": "object",
            "properties": {
                "message": {
                    "type": "string",
                    "description": "The message patient wants to pass to the recipient. It will also contain First Name , Last Name and Phone Number of patient & Doctor Name as well",
                },
                "recipient": {
                    "type": "string",
                    "description": "The email address of the recipient.",
                },
                "subject": {
                    "type": "string",
                    "description": "The subject of the email.",
                },
                
            },
            "required": ["message" , "recipient" , "subject"],
        },
    },
}

transfer_call_function_schema = {
    "type": "function",
    "function": {
        "name": "transfer_call",
        "description": "Use this function to transfer call when necessary",
        "parameters": {
            "type": "object",
            "properties": {
                "clinic_name": {
                    "type": "string",
                    "description": "Name of the clinic",
                },
                "to_number": {
                    "type": "string",
                    "description": "The number to which the call is to be transferred",
                },
            },
            "required": ["to_number", "clinic_name" ],  # Correctly defined as an array of required fields
        },
    },
}

get_specific_available_slot_schema = {
    "type": "function",
    "function": {
        "name": "get_specific_available_slot",
        "description": "Get a free slot for the requested doctor and appointment name, based on the date and time provided by the user.",
        "parameters": {
            "type": "object",
            "properties": {
                "business_id": {
                    "type": "string",
                    "description": "Business ID of clinic.",
                },
                "doctor_name": {
                    "type": "string",
                    "description": "The name of the doctor.",
                },
                "appointment_name": {
                    "type": "string",
                    "description": "The name of the appointment.",
                },
                "clinic_name": {
                    "type": "string",
                    "description": "The name of the clinic.",
                },
                "starts_at": {
                    "type": "string",
                    "description" : "The start time of the appointment in the form of YYYY-MM-DDTHH:MM:SSZ. e.g 2024-08-13T11:00:00Z, Do not to change/convert the time provided by the user or add anything additional. This time must be in future and in UTC 24HR. If user just provides the date then add time as T00:00:00Z",
                },
                "user_preference": {
                    "type": "string",
                    "description" : "The preferred time of the user, the values can be `exact`, `before`, or `after`. e.g before 11:00 AM, pass it as 2025-05-07T11:00:00Z",
                },
                "context": {
                    "type": "string",
                    "description": "Summarize and store the context of the conversation with you, if you think the functionality of this function tool call has been completed, then do not call this function again in that conversation.",
                },
            },
            "required": ["business_id","doctor_name", "starts_at", "appointment_name", "clinic_name", "user_preference", "context", ],
        }
    }
}


get_next_available_slot_schema = {
    "type": "function",
    "function": {
        "name": "get_next_available_slot",
        "description": "Get a free slot for the requested doctor and appointment name, based on the date and time provided by the user.",
        "parameters": {
            "type": "object",
            "properties": {
                "business_id": {
                    "type": "string",
                    "description": "Business ID of clinic.",
                },
                "doctor_name": {
                    "type": "string",
                    "description": "The name of the doctor.",
                },
                "appointment_name": {
                    "type": "string",
                    "description": "The name of the appointment.",
                },
                "clinic_name": {
                    "type": "string",
                    "description": "The name of the clinic.",
                },
                "starts_at": {
                    "type": "string",
                    "description" : "The start time of the appointment in the form of YYYY-MM-DDTHH:MM:SSZ. e.g 2024-08-13T11:00:00Z, make sure not to change/convert the time provided by the user. This time must be in future and in UTC 24HR.",
                },
            },
            "required": ["business_id","doctor_name", "starts_at", "appointment_name", "clinic_name"],
        }
    }
}

create_appointment_new_patient_schema = {
    "type": "function",
    "function": {
        "name": "create_appointment_new_patient",
        "description": "Create an appointment for a new patient. Call this whenver a new patient wants to book an appointment, but call this function only once. Do not twice call or multple call this function.",
        "parameters": {
            "type": "object",
            "properties": {
                "doctor_name": {
                    "type": "string",
                    "description": "The name of the doctor.",
                },
                "first_name": {
                    "type": "string",
                    "description": "The first name of the patient.",
                },
                "last_name": {
                    "type": "string",
                    "description": "The last name of the patient.",
                },
                "date_of_birth": {
                    "type": "string",
                    "description": "The date of birth of the patient in the form of YYYY-MM-DD.",
                },
                "phone_number": {
                    "type": "string",
                    "description": "The mobile number of the patient",
                },
                "starts_at": {
                    "type": "string",
                    "description": "The start time of the appointment in the form of YYYY-MM-DDTHH:MM:SSZ. e.g 2024-08-13T11:00:00Z, make sure not to change/convert the time that is provided by the user. Pass the same time in params that patient tells you. This time must be in future and in UTC 24HR.",
                },
                "appointment_type": {
                    "type": "string",
                    "description": "The type of appointment.",
                },
                "appointment_name": {
                    "type": "string",
                    "description": "The name of the appointment.",
                },
                "clinic_name" : {
                    "type": "string",
                    "description": "The name of the clinic."
                }
            },
            "required": ["doctor_name","first_name", "last_name", "date_of_birth", "phone_number", "starts_at", "appointment_name" , "clinic_name"],
        }
    }
}

create_appointment_existing_patient_schema = {
    "type": "function",
    "function": {
        "name": "create_appointment_existing_patient",
        "description": "Create an appointment for an existing patient. Call this whenver an existing patient wants to book an appointment, but call this function only once. Do not twice call or multple call this function.",
        "parameters": {
            "type": "object",
            "properties": {
                "doctor_name": {
                    "type": "string",
                    "description": "The name of the doctor.",
                },
                "phone_number": {
                    "type": "string",
                    "description": "The mobile number of the patient",
                },
                "starts_at": {
                    "type": "string",
                    "description": "The start time of the appointment in the form of YYYY-MM-DDTHH:MM:SSZ. e.g 2024-08-13T11:00:00Z, make sure not to change/convert the time that is provided by the user. Pass the same time in params that patient tells you. This time must be in future and in UTC 24HR.",
                },
                "appointment_type": {
                    "type": "string",
                    "description": "The type of appointment.",
                },
                "appointment_name": {
                    "type": "string",
                    "description": "The name of the appointment.",
                },
                "clinic_name" : {
                    "type": "string",
                    "description": "The name of the clinic."
                },
                },
            "required": ["doctor_name", "phone_number", "starts_at", "appointment_name", "clinic_name"],
        }
    }
}

update_individual_appointment_schema = {
    "type": "function",
    "function": {
        "name": "update_individual_appointment",
        "description": "Update an individual appointment.  Call this whenver a patient wants to update or reshedule an appointment, but call this function only once. Do not twice call or multple call this function.",
        "parameters": {
            "type": "object",
            "properties": {
                "new_starts_date": {
                    "type": "string",
                    "description": "The new start date of the updated appointment in the form of YYYY-MM-DDTHH:MM:SSZ e.g. 2019-08-24T14:15:22Z,  make sure not to change/convert the time that is provided by the user. Pass the same time in params that patient tells you. The start time must be in the future.",
                },
                "old_start_date": {
                    "type": "string",
                    "description": "The old start date of the appointment in the form of YYYY-MM-DDTHH:MM:SSZ e.g. 2019-08-24T14:15:22Z,  make sure not to change/convert the time that is provided by the user. Pass the same time in params that patient tells you.",
                },      
                "phone_number": {
                    "type": "string",
                    "description": "The mobile number of the patient",
                },
                "clinic_name" :{
                    "type": "string",
                    "description": "The name of the clinic."
                }
            },
            "required": [
                "new_starts_date",
                "phone_number", "old_start_date",
                "clinic_name" ,
            ],
        },
    }
}

get_patient_appointment_schema = {
    "type": "function",
    "function": {
        "name": "get_patient_appointment",
        "description": "If the patient wants to update their appointment but doesn't remeber their appointment date and time, then call this function once, and get the appointment date and time. Do not twice call or multple call this function.",
        "parameters": {
            "type": "object",
            "properties": {
                "first_name": {
                    "type": "string",
                    "description": "The first name of the patient.",
                },
                "last_name": {
                    "type": "string",
                    "description": "The last name of the patient.",
                },
                "date_of_birth": {
                    "type": "string",
                    "description": "The date of birth of the patient in the form of YYYY-MM-DD",
                },
                "flag":{
                    "type": "string",
                    "description": "A flag to check if the patient wants to update or cancel appointment. Default value of flag is `check`. Its value can be `update` or `cancel` or `check`. ."
                },
                "context": {
                    "type": "string",
                    "description": "Summarize and store the context of the conversation with you, if you think the functionality of this function tool call has been completed, then do not call this function again in that conversation.",
                },
            },
            "required": [
                "first_name", "last_name",
                "date_of_birth",
                "flag",
                "context",
            ],
        },
    }
}


update_outbound_appointment_schema = {
    "type": "function",
    "function": {
        "name": "update_outbound_appointment",
        "description": "Update an individual appointment.",
        "parameters": {
            "type": "object",
            "properties": {
                "doctor_name": {
                    "type": "string",
                    "description": "The name of the doctor.",
                },
                "new_ends_date": {
                    "type": "string",
                    "description": "The new end date of the updated appointment in the form of YYYY-MM-DDTHH:MM:SSZ e.g. 2019-08-24T14:15:22Z",
                },
                "new_starts_date": {
                    "type": "string",
                    "description": "The new start date of the updated appointment in the form of YYYY-MM-DDTHH:MM:SSZ e.g. 2019-08-24T14:15:22Z",
                },
                "old_end_date": {
                    "type": "string",
                    "description": "The old end date of the appointment in the form of YYYY-MM-DDTHH:MM:SSZ e.g. 2019-08-24T14:15:22Z",
                },
                "old_start_date": {
                    "type": "string",
                    "description": "The old start date of the appointment in the form of YYYY-MM-DDTHH:MM:SSZ e.g. 2019-08-24T14:15:22Z",
                },
                "first_name": {
                    "type": "string",
                    "description": "The first name of the patient.",
                },
                "last_name": {
                    "type": "string",
                    "description": "The last name of the patient.",
                },
                "date_of_birth": {
                    "type": "string",
                    "description": "The date of birth of the patient in the form of YYYY-MM-DD.",
                },
            },
            "required": [
                "new_ends_date", "new_starts_date",
                "first_name", "last_name",
                "date_of_birth", "old_end_date", "old_start_date",
            ],
        },

    }
}

cancel_individual_appointment_schema = {
    "type": "function",
    "function": {
        "name": "cancel_individual_appointment",
        "description": "Cancel an individual appointment.  Call this whenver a patient wants to cancel an appointment, but call this function only once. Do not twice call or multple call this function.",
        "parameters": {
            "type": "object",
            "properties": {  
                "phone_number": {
                    "type": "string",
                    "description": "The mobile number of the patient without any dashes or spaces",
                },
                "starts_at": {
                    "type": "string",
                    "description": "The start date of the appointment in the form of YYYY-MM-DDTHH:MM:SSZ e.g. 2019-08-24T14:15:22Z,  make sure not to change/convert the time that is provided by the user. Pass the same time in params that patient tells you. This time must be in future and in UTC 24HR.",
                },
                "clinic_name" :{
                    "type": "string",
                    "description": "The name of the clinic"
                }
            },
            "required": ["phone_number", "starts_at" , "clinic_name"],
        }
    }
}
