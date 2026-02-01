from fastapi import Request
from twilio.rest import Client
import os
import urllib.parse
from src.logger import logger
from dotenv import load_dotenv
from src.components.archive.redis_service import RedisService

load_dotenv()
redis = RedisService()
class TwilioClient:
    def __init__(self):
        try:
            # for local
            # load_dotenv('.env')
            self.client = Client(
                os.environ.get("TWILIO_ACCOUNT_ID", None), os.environ.get("TWILIO_AUTH_TOKEN", None)
            )

            # for local
            self.url = os.environ.get("NGROK_IP_ADDRESS", None)
            self.messaging_service_sid = os.environ.get("TWILIO_MESSAGING_SERVICE_SID")
            # for production
            # self.url = os.environ.get("AZURE_URL")
            # logger.info("Voice URL", self.url)
            print("Voice URL", self.url)
            calls = self.client.calls.list(limit=10)

            # for record in calls:
            #     print(record.sid)

        except Exception as e:
            print(e)

    # Create a new phone number and route it to use this server
    def create_phone_number(self, area_code, agent_id):
        try:
            local_number = self.client.available_phone_numbers("US").local.list(
                area_code=area_code, limit=1
            )
            if local_number is None or local_number[0] is None:
                raise "No phone numbers of this area code."
            phone_number_object = self.client.incoming_phone_numbers.create(
                phone_number=local_number[0].phone_number,
                voice_url=f"{self.url}/twilio-voice-webhook/{agent_id}",
            )
            print("Getting phone number:", vars(phone_number_object))
            return phone_number_object
        except Exception as err:
            print(err)

    # Update this phone number to use provided agent id. Also updates voice URL address.
    def register_phone_agent(self, phone_number, agent_id):
        try:
            phone_number_objects = self.client.incoming_phone_numbers.list(limit=200)
            print("Here")

            numbers_sid = ""
            for phone_number_object in phone_number_objects:
                if phone_number_object.phone_number == phone_number:
                    number_sid = phone_number_object.sid

            if number_sid is None:
                print(
                    "Unable to locate this number in your Twilio account, is the number you used in BCP 47 format?"
                )
                return
            phone_number_object = self.client.incoming_phone_numbers(number_sid).update(
                voice_url=f"{self.url}/twilio-voice-webhook/{agent_id}"
            )
            print("Register phone agent:", vars(phone_number_object))
            return phone_number_object
        except Exception as err:
            print("Exception while registering number: ", err)

    # Release a phone number
    def delete_phone_number(self, phone_number):
        try:
            phone_number_objects = self.client.incoming_phone_numbers.list(limit=200)
            numbers_sid = ""
            for phone_number_object in phone_number_objects:
                if phone_number_object.phone_number == phone_number:
                    number_sid = phone_number_object.sid
                if number_sid is None:
                    print(
                        "Unable to locate this number in your Twilio account, is the number you used in BCP 47 format?"
                    )
                    return
                phone_number_object = self.client.incoming_phone_numbers(
                    number_sid
                ).delete()
                print("Delete phone number:", phone_number)
                return phone_number_object
        except Exception as err:
            print(err)

    # Use LLM function calling or some kind of parsing to determine when to let AI end the call
    def end_call(self, sid):
        try:
            call = self.client.calls(sid).update(
                twiml="<Response><Hangup/></Response>",
            )
            print("INSIDE END CALL FUNCTION")
            print(f"Ended call: ", vars(call))
        except Exception as err:
            print(err)
    # def get_in_progress_call_sid(self):
    #     """Retrieve the CallSid of the first in-progress call."""
    #     calls = self.client.calls.list(status="in-progress")
    #     for call in calls:
    #         print(f"CallSid inside get_in_progress_call_sid: {call.sid},")
    #         return call.sid  # Get the first in-progress call's sid
    #     else:
    #         print("No in-progress calls found.")
    #         return None
        
    # Use LLM function calling or some kind of parsing to determine when to transfer away this call
    def transfer_call(self, to_numebr, sid):
        try:
            print("Transferring Call to number: ", to_numebr) 
            call = self.client.calls(sid).update(
                twiml=f"<Response><Dial>{to_numebr}</Dial></Response>",
            )
            print(f"Transferred call: ", vars(call))
        except Exception as err:
            print(err)

    # Create an outbound call
    def create_phone_call(
        self,
        from_number,
        to_number,
        agent_id,
        dr,
        reason,
        agent_type,
        appointment_id,
        date,
    ):
        try:
            dr_encoded = urllib.parse.quote(dr)
            reason_encoded = urllib.parse.quote(reason)
            appointment_id_encoded = urllib.parse.quote(appointment_id)
            date = urllib.parse.quote(date)
            url = f"{self.url.rstrip('/')}/twilio-voice-webhook/{agent_id}?dr={dr_encoded}&agent_type={agent_type}&appointment_id={appointment_id_encoded}&date={date}&reason={reason_encoded}"

            call = self.client.calls.create(
                machine_detection="Enable",  # detects if the other party is IVR
                machine_detection_timeout=8,
                async_amd="true",  # call webhook when determined whether it is machine
                async_amd_status_callback=url,  # Webhook url for machine detection
                url=url,
                to=to_number,
                from_=from_number,
            )
            # you can use call sid as key in redis caching
            print(f"Calling {to_number} from {from_number} {call.sid}")
            return call

        except Exception as err:
            print(err)

    def create_phone_call_cliniko(
        self,
        from_number,
        to_number,
        agent_id,
        dr,
        reason,
        agent_type,
        first_name,
        last_name,
        date_of_birth,
        old_start_date,
        old_end_date,
        crm
    ):
        logger.info(f"Calling cliniko ")
        try:
            dr_encoded = urllib.parse.quote(dr)
            reason_encoded = urllib.parse.quote(reason)
            first_name_encoded = urllib.parse.quote(first_name)
            last_name_encoded = urllib.parse.quote(last_name)
            date_of_birth_encoded = urllib.parse.quote(date_of_birth)
            old_start_date_encoded = urllib.parse.quote(old_start_date)
            old_end_date_encoded = urllib.parse.quote(old_end_date)
            crm_encoded = urllib.parse.quote(crm)
            url = f"{self.url.rstrip('/')}/twilio-voice-webhook/{agent_id}?dr={dr_encoded}&agent_type={agent_type}&first_name={first_name_encoded}&last_name={last_name_encoded}&date_of_birth={date_of_birth_encoded}&old_start_date={old_start_date_encoded}&old_end_date={old_end_date_encoded}&crm={crm_encoded}&reason={reason_encoded}"


            call = self.client.calls.create(
                machine_detection="Enable",  # detects if the other party is IVR
                machine_detection_timeout=8,
                async_amd="true",  # call webhook when determined whether it is machine
                async_amd_status_callback=url,  # Webhook url for machine detection
                url=url,
                to=to_number,
                from_=from_number,
            )
            # you can use call sid as key in redis caching
            print(f"Calling {to_number} from {from_number} {call.sid}")
            return call

        except Exception as err:
            print(err)

    def create_phone_call_cliniko_patient_review(
        self,
        from_number,
        to_number,
        agent_id,
        dr,
        reason,
        agent_type,
        first_name,
        last_name,
        appointment_date,
        checkup,
        review,
        crm
    ):
        logger.info(f"Calling function create_phone_call_cliniko_patient_review")
        try:
            dr_encoded = urllib.parse.quote(dr)
            first_name_encoded = urllib.parse.quote(first_name)
            last_name_encoded = urllib.parse.quote(last_name)
            crm_encoded = urllib.parse.quote(crm)
            appointment_date_encoded = urllib.parse.quote(appointment_date)
            checkup_encoded = urllib.parse.quote(checkup)
            review_encoded = urllib.parse.quote(review)
            reason_encoded = urllib.parse.quote(reason)


            url = f"{self.url.rstrip('/')}/twilio-voice-webhook/{agent_id}?dr={dr_encoded}&agent_type={agent_type}&first_name={first_name_encoded}&last_name={last_name_encoded}&crm={crm_encoded}&appointment_date={appointment_date_encoded}&checkup={checkup_encoded}&review={review_encoded}&reason={reason_encoded}"

            print('url', url)
            call = self.client.calls.create(
                machine_detection="Enable",  # detects if the other party is IVR
                machine_detection_timeout=8,
                async_amd="true",  # call webhook when determined whether it is machine
                async_amd_status_callback=url,  # Webhook url for machine detection
                url=url,
                to=to_number,
                from_=from_number,
            )
            # you can use call sid as key in redis caching
            print(f"Calling {to_number} from {from_number} {call.sid}")
            return call

        except Exception as err:
            print(err)


    def create_call_cliniko_appointment_confirmation(
        self,
        from_number,
        to_number,
        agent_id,
        dr,
        reason,
        agent_type,
        first_name,
        last_name,
        date_of_birth,
        appointment_date,
        crm
    ):
        logger.info(f"Calling function create_call_cliniko_appointment_confirmation")
        try:
            dr_encoded = urllib.parse.quote(dr)
            first_name_encoded = urllib.parse.quote(first_name)
            last_name_encoded = urllib.parse.quote(last_name)
            date_of_birth_encoded = urllib.parse.quote(date_of_birth)
            crm_encoded = urllib.parse.quote(crm)
            appointment_date_encoded = urllib.parse.quote(appointment_date)
            reason_encoded = urllib.parse.quote(reason)

            url = f"{self.url.rstrip('/')}/twilio-voice-webhook/{agent_id}?dr={dr_encoded}&agent_type={agent_type}&first_name={first_name_encoded}&last_name={last_name_encoded}&crm={crm_encoded}&appointment_date={appointment_date_encoded}&reason={reason_encoded}&date_of_birth={date_of_birth_encoded}"


            call = self.client.calls.create(
                machine_detection="Enable",  # detects if the other party is IVR
                machine_detection_timeout=8,
                async_amd="true",  # call webhook when determined whether it is machine
                async_amd_status_callback=url,  # Webhook url for machine detection
                url=url,
                to=to_number,
                from_=from_number,
            )


            print(f"Calling {to_number} from {from_number} {call.sid}")
            return call

        except Exception as err:
            print(err)


    def create_phone_call_cliniko_patient_outreach(
        self,
        from_number,
        to_number,
        agent_id,
        dr,
        reason,
        agent_type,
        first_name,
        last_name,
        date_of_birth,
        old_start_date,
        crm
    ):
        logger.info(f"Calling cliniko ")
        try:
            dr_encoded = urllib.parse.quote(dr)
            reason_encoded = urllib.parse.quote(reason)
            first_name_encoded = urllib.parse.quote(first_name)
            last_name_encoded = urllib.parse.quote(last_name)
            date_of_birth_encoded = urllib.parse.quote(date_of_birth)
            old_start_date_encoded = urllib.parse.quote(old_start_date)
            crm_encoded = urllib.parse.quote(crm)
            url = f"{self.url.rstrip('/')}/twilio-voice-webhook/{agent_id}?dr={dr_encoded}&agent_type={agent_type}&first_name={first_name_encoded}&last_name={last_name_encoded}&date_of_birth={date_of_birth_encoded}&old_start_date={old_start_date_encoded}&crm={crm_encoded}&reason={reason_encoded}"


            call = self.client.calls.create(
                machine_detection="Enable",  # detects if the other party is IVR
                machine_detection_timeout=8,
                async_amd="true",  # call webhook when determined whether it is machine
                async_amd_status_callback=url,  # Webhook url for machine detection
                url=url,
                to=to_number,
                from_=from_number,
            )
            # you can use call sid as key in redis caching
            print(f"Calling {to_number} from {from_number} {call.sid}")
            return call

        except Exception as err:
            print(err)
          
    def send_message(self, from_number, to_number, message_body, params):
        try:
            encoded_params = urllib.parse.urlencode(params)
            message = self.client.messages.create(
                body=message_body,
                from_=from_number,
                to=to_number,
                messaging_service_sid=self.messaging_service_sid,
                status_callback_url = f"{self.url.rstrip('/')}/outbound/handle-incoming-messages?{encoded_params}",
            )
            print(f"Message with sid: {message.sid} has been sent sucessfully to {to_number}")
            return message
        except Exception as err:
            print("Error while sending message from Twilio:" , err)
            
    def handle_incoming_messages(self , req: Request):
        print("Handling incoming messages")
        print("REQ BODY IN HANDLE_INCOMING" , req.body)
        # try:
        #     sms_status = req.body.get("status")
        #     if outbound_type = confirmation
        #     if sms_status == "delivered":
        #         print("Message has been delivered" , req.body)
        #         body -> yes
        #             send message ( your appointment has been confirmed)
        #         body -> no
        #             cancel appointment (appointment_id )
        #     else outbound_type = rescheduling
        #         second rescheduling flow
            
            
                    
                
        #     #TODO Add message handling
        # except Exception as err:
        #     print("Error while handling message from Twilio:" , err)