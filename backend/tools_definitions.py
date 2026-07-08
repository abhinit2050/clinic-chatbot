tools = [
    {
        "type": "function",
        "name": "list_doctors",
        "description": "Returns a list of all available doctors with their id, name and specialty. Call this when the user asks about available doctors or wants to know who they can book with.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },

    {
        "type": "function",
        "name": "check_availability",
        "description": "Checks available time slots for a specific doctor on a given date. Call this when the user has chosen a doctor and a date and wants to see available slots.",
        "parameters": {
            "type": "object",
            "properties": {
                "doctor_id": {
                    "type": "integer",
                    "description": "The id of the doctor whose availability is being checked"
                },
                "date": {
                    "type": "string",
                    "description": "The date to check availability for, in YYYY-MM-DD format"
                }
            },
            "required": ["doctor_id", "date"]
        }
    },

    {
        "type":"function",
        "name":"book_appointment",
        "description":"Books an appointment for a patient with the specified doctor on a specified time slot. Call this when the patient has finalised the doctor and the appointment date",
        "parameters":{
            "type":"object",
            "properties":{
                "doctor_id":{
                    "type":"integer",
                     "description": "The id of the doctor whose availability is finalised"
                },
                "slot_id":{
                    "type":"integer",
                    "description":"The id of the time slot which was finalised by the patient"
                },
                "name":{
                    "type":"string",
                    "description":"name provided by the patient"
                },
                "phone":{
                    "type":"string",
                    "description":"phone number of the patient"
                },
                "reason":{
                    "type":"string",
                    "description":"reason for appointment like the symptoms mentioned by the patient"
                },
                "date":{
                    "type":"string",
                    "description":"date of the appointment"
                }

            },
            "required": ["doctor_id", "slot_id", "name", "phone", "date"]
        }
    }
]