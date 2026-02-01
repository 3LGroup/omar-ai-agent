import os
import aiohttp
import logging
# from src.db.db import DB
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter
from src.db.db import DB
# DynamoDB is commented out - import conditionally
try:
    from src.db.dynamodb import DynamoDBClient
    dynamo_client = DynamoDBClient(local=False)
except (ImportError, AttributeError):
    DynamoDBClient = None
    dynamo_client = None
import asyncio
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

router = APIRouter()

db = DB()


# Configure logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Get the timestamp 24 hours ago in ISO 8601 format
def get_time_24_hours_ago():
    return (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat().replace('+00:00', 'Z')

# @router.get('/auto-upsert-patients')

async def get_cron_job_data():
    users_ref = db.db.collection('users_auth')
    users = users_ref.stream()

    print("checking users...")

    for user_doc in users:
        user_data = user_doc.to_dict()

        if "db_tablename" in user_data:
            clinic_name = user_data.get("name", "N/A")
            clinic_url = user_data.get("cliniko_url") or user_data.get("nookal_url", "N/A")
            db_tablename = user_data["db_tablename"]

            print(f"Clinic Name: {clinic_name}")
            print(f"DB Table Name: {db_tablename}")
            print(f"Clinic URL: {clinic_url}")

            if "cliniko" in clinic_url.lower():
                clinic_api = user_data.get("cliniko_api", "N/A")
                print(f"\nClinic API: {clinic_api}")
                await process_created_patients_flow(clinic_name, db_tablename, clinic_api, clinic_url)
                print("\nUpdate...")
                await process_recently_updated_patients(clinic_name, db_tablename, clinic_api, clinic_url)

            # elif "nookal" in clinic_url.lower():
            #     clinic_api = user_data.get("nookal_api", "N/A")
            #     print(f"Nookal API: {clinic_api}")
            #     print("Processing Nookal patients...")
            #     # await process_created_patients_flow(clinic_name, db_tablename, clinic_api, clinic_url)

            # else:
            #     print(f"Unknown provider in URL: {clinic_url}")

            print("----------------------------------------")
    
    return {"message": "Cron job completed successfully."}


async def fetch_newly_created_patients(CRM, params=None):
    
    url = f"{CRM['base_url']}/patients"
    api_key = CRM['api_key']
    auth = aiohttp.BasicAuth(login=api_key)

    if params is None:
        params = {}

    # time_24_hours_ago = "2025-04-11T00:00:00Z"
    time_24_hours_ago = get_time_24_hours_ago()
    print("time_24_hours_ago", time_24_hours_ago)
    logger.info(f"Fetching created patients for clinic: {CRM['base_url']}")

    query = {
        "order": params.get("order", "asc"),
        "page": params.get("page", 1),
        "per_page": params.get("per_page", 50),
        "sort": params.get("sort", "created_at:desc"),
        "q[]": [f"created_at:>{time_24_hours_ago}"]
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=query, auth=auth) as response:
                data = await response.json()
                return data, response.status
    except aiohttp.ClientError as e:
        logger.error(f"Error in fetch_newly_created_patients for {CRM['base_url']}: {e}")
        return None, 500

import os
import pprint
import logging

logger = logging.getLogger(__name__)

async def fetch_created_patients_from_all_clinics(clinic_name, clinic_api, clinic_url):
    created_patients = []
    page = 1

    CRM = {
        "name": clinic_name,
        "base_url": clinic_url,
        "api_key": os.getenv(clinic_api)
    }

    while True:
        params = {
            "page": page,
            "per_page": 50,
            "sort": "created_at:desc",
            "order": "asc"
        }

        patient_data, status = await fetch_newly_created_patients(CRM, params)

        if status == 200 and "patients" in patient_data:
            patients = patient_data["patients"]

            if not patients:
                logger.info(f"No more patients on page {page} for clinic: {clinic_name}")
                break

            for patient in patients:
                formatted_patient = {
                    "phone_number": (patient.get("patient_phone_numbers") or [{}])[0].get("number", ""),
                    "home_number": patient.get("home_number", ""),
                    "work_number": patient.get("work_number", ""),
                    "patient_id": patient.get("id", ""),
                    "first_name": patient.get("first_name", ""),
                    "last_name": patient.get("last_name", ""),
                    "date_of_birth": patient.get("date_of_birth", ""),
                    "clinic_name": clinic_name
                }
                created_patients.append(formatted_patient)

            page += 1

        else:
            logger.error(f"Failed to fetch created patients from {CRM['base_url']} (page {page}). Status code: {status}")
            break

    return created_patients


async def process_created_patients_flow(clinic_name, db_tablename, clinic_api, clinic_url):
    
    created_patients_raw = await fetch_created_patients_from_all_clinics(clinic_name, clinic_api, clinic_url)

    await dynamo_client.batch_add_patients(db_tablename, created_patients_raw)

    print("DynamoDB batch add completed.")


async def list_recently_updated_patients(cliniko, params=None):
    
    url = f"{cliniko['base_url']}/patients"
    api_key = cliniko['api_key']
    auth = aiohttp.BasicAuth(login=api_key)

    if params is None:
        params = {}

    print("current page param:", params.get("page"))

    time_24_hours_ago = get_time_24_hours_ago()
    # time_24_hours_ago = "2025-04-11T00:00:00Z"

    logger.info(f"Fetching updated patients for clinic: {cliniko['base_url']}")
    # logger.info(f"Time 24 hours ago: {time_24_hours_ago}")

    query = {
        "order": params.get("order", "asc"),
        "page": params.get("page", 1),
        "per_page": params.get("per_page", 50),
        "sort": params.get("sort", "updated_at:desc"),
        "q[]": [f"updated_at:>{time_24_hours_ago}"]
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=query, auth=auth) as response:
                data = await response.json()
                return data, response.status
    except aiohttp.ClientError as e:
        logger.error(f"Error fetching updated patients from {cliniko['base_url']}: {e}")
        return None, 500

async def fetch_updated_patients_from_all_clinics(clinic_name, cliniko_api, cliniko_url):
    updated_patients = []
    page = 1

    cliniko = {
        "name": clinic_name,
        "base_url": cliniko_url,
        "api_key": os.getenv(cliniko_api)
    }

    while True:
        params = {
            "page": page,
            "per_page": 50,
            "sort": "updated_at:desc",
            "order": "asc"
        }

        patient_data, status = await list_recently_updated_patients(cliniko, params)

        if status == 200 and "patients" in patient_data:
            patients = patient_data["patients"]

            if not patients:
                logger.info(f"No more updated patients on page {page} for clinic: {clinic_name}")
                break

            for patient in patients:
                formatted_patient = {
                    "phone_number": (patient.get("patient_phone_numbers") or [{}])[0].get("number", ""),
                    "home_number": patient.get("home_number", ""),
                    "work_number": patient.get("work_number", ""),
                    "patient_id": patient.get("id", ""),
                    "first_name": patient.get("first_name", ""),
                    "last_name": patient.get("last_name", ""),
                    "date_of_birth": patient.get("date_of_birth", ""),
                    "clinic_name": clinic_name
                }
                updated_patients.append(formatted_patient)

            page += 1

        else:
            logger.error(f"Failed to fetch updated patients from {cliniko['base_url']} (page {page}). Status code: {status}")
            break

    return updated_patients


async def process_recently_updated_patients(clinic_name, db_tablename, cliniko_api, cliniko_url):
    updated_patients = await fetch_updated_patients_from_all_clinics(clinic_name, cliniko_api, cliniko_url)

    if not updated_patients:
        print("No patients updated in the last 24 hours.")
        return

    dynamodb_patients = await dynamo_client.fetch_all_patients_from_dynamodb(db_tablename)

    if not dynamodb_patients:
        print("No patients found in DynamoDB.")
        return

    dynamodb_patients_by_id = {patient["patient_id"]: patient for patient in dynamodb_patients}

    for patient in updated_patients:
        patient_id = patient.get("patient_id")
        if not patient_id:
            print("Skipping patient due to missing Patient ID")
            continue

        # Check if the patient exists in DynamoDB
        if patient_id not in dynamodb_patients_by_id:
            print(f"Patient ID {patient_id} not found in DynamoDB. Skipping update.")
            continue

        # Get the existing patient record from DynamoDB
        existing_patient = dynamodb_patients_by_id[patient_id]

        # Prepare the data to be updated
        updated_data = {
            "phone_number": patient.get("phone_number", ""),
            "home_number": patient.get("home_number", ""),
            "work_number": patient.get("work_number", ""),
            "first_name": patient.get("first_name", ""),
            "last_name": patient.get("last_name", ""),
            "date_of_birth": patient.get("date_of_birth", ""),
            "clinic_name": clinic_name
        }

        # Remove fields with "N/A" values
        cleaned_data = {k: v for k, v in updated_data.items() if v != ""}

        # Identify changes
        changes = {k: v for k, v in cleaned_data.items() if existing_patient.get(k) != v}

        if not changes:
            print(f"No changes detected for patient ID {patient_id}. Skipping update.")
            continue

        # Update the patient in DynamoDB
        print(f"Updating patient ID {patient_id} with changes: {changes}")
        await dynamo_client.update_patient(db_tablename, patient_id, changes)

    print("All updated patients processed.")

def run_async_job():
    asyncio.run(get_cron_job_data())
    
scheduler = BackgroundScheduler()
trigger = CronTrigger(hour=0, minute=0)
scheduler.add_job(run_async_job, trigger)
scheduler.start()