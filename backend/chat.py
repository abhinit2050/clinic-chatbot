import os
import json
from openai import OpenAI
from dotenv import load_dotenv
from tools import list_doctors, check_availability, book_appointment
from tool_definitions import tools
from datetime import date

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def chat(conversation_history):
    
    today = date.today().strftime("%Y-%m-%d")
    print("Today's date:", today);
    system_prompt=f""" 
    You are a helpful clinic appointment assistant. You help patients book appointments with doctors.
    Today's date is {today}. Use this as reference when the user says "today", "tomorrow", or any relative date.
    You have access to the following tools:
    - list_doctors: use this when the user asks about available doctors
    - check_availability: use this when the user has chosen a doctor and a date
    - book_appointment: use this when the user has confirmed the doctor, date, time slot, and provided their name and phone number

    Always be polite and conversational. If the user hasn't provided all necessary information, ask for it one piece at a time. Never make up doctor names or available slots - always use the tools to fetch real data.
    """
    messages = [{"role":"system","content":system_prompt}]+conversation_history  

    while True:
        response = client.responses.create(
            model="gpt-4o",
            input=messages,
            tools=tools
        )

        output = response.output
        print("Output:", output)    
        for item in output:
            if item.type=="message":
                return item.content[0].text
            elif item.type=="function_call":
                tool_name = item.name
                tool_args = json.loads(item.arguments)

                if(tool_name=="list_doctors"):
                    tool_result = list_doctors()
                elif tool_name=="check_availability":
                    tool_result = check_availability(**tool_args)
                elif tool_name == "book_appointment":
                    tool_result = book_appointment(**tool_args)

                messages.append({
                    "type": "function_call",
                    "call_id": item.call_id,
                    "name": item.name,
                    "arguments": item.arguments
                })
                messages.append({
                    "type":"function_call_output",
                    "call_id":item.call_id, 
                    "output":json.dumps(tool_result)
                })



    # if __name__ == "__main__":
    #     history = [{"role": "user", "content": "Hello, which doctors are available?"}]
    #     response = chat(history)
    #     print("Response:", response)  


