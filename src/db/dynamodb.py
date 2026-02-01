# # import asyncio
# # import os
# # import pprint
# import boto3
# from boto3.dynamodb.conditions import Attr
# from botocore.exceptions import ClientError
# from dotenv import load_dotenv
# load_dotenv()

# class DynamoDBClient:
#     def __init__(self, local=False):
#         self.resource = self._init_dynamodb_resource(local)
        
#     def _init_dynamodb_resource(self, local):
#         if local:
#             return boto3.resource(
#                 'dynamodb',
#                 endpoint_url='http://localhost:8000',
#                 region_name='us-west-2',
#                 aws_access_key_id='fakeMyKeyId',
#                 aws_secret_access_key='fakeSecretAccessKey'
#             )
#         else:
#             return boto3.resource(
#                 'dynamodb',
#                 region_name=os.environ.get('AWS_REGION'),
#                 aws_access_key_id=os.environ.get('AWS_ACCESS_KEY_ID'),
#                 aws_secret_access_key=os.environ.get('AWS_SECRET_ACCESS_KEY')
#             )

#     async def create_table(self, table_name):
#         """Create a DynamoDB table with patient_id as partition key"""
#         try:
#             table = self.resource.create_table(
#                 TableName=table_name,
#                 KeySchema=[{'AttributeName': 'patient_id', 'KeyType': 'HASH'}],
#                 AttributeDefinitions=[{'AttributeName': 'patient_id', 'AttributeType': 'S'}],
#                 ProvisionedThroughput={'ReadCapacityUnits': 5, 'WriteCapacityUnits': 5}
#             )
#             table.wait_until_exists()
#             return table
#         except ClientError as e:
#             print(f"Error creating table: {e}")
#             return None
            
#     async def add_patient(self, table_name, patient_data):
#         """Add a new patient with automatic empty field removal"""
#         try:
#             table = self.resource.Table(table_name)
#             cleaned_data = {k: v for k, v in patient_data.items() if v}
#             response = table.put_item(Item=cleaned_data)
#             return response
#         except ClientError as e:
#             print(f"Error adding patient: {e}")
#             return None

#     async def update_patient(self, table_name, patient_id, update_data):
#         """Update patient information with proper attribute handling"""
#         try:
#             table = self.resource.Table(table_name)
            
#             # Create safe attribute names and values
#             expr_attr_names = {f"#{k.replace(' ', '_')}": k for k in update_data.keys()}
#             expr_attr_values = {f":{k.replace(' ', '_')}": v 
#                             for k, v in update_data.items()}
            
#             update_expr = "SET " + ", ".join(
#                 [f"{name} = {value}" for name, value in zip(
#                     expr_attr_names.keys(),
#                     expr_attr_values.keys()
#                 )]
#             )
            
#             response = table.update_item(
#                 Key={'patient_id': patient_id},
#                 UpdateExpression=update_expr,
#                 ExpressionAttributeNames=expr_attr_names,
#                 ExpressionAttributeValues=expr_attr_values,
#                 ReturnValues="UPDATED_NEW"
#             )
#             return response
#         except ClientError as e:
#             print(f"Error updating patient: {e}")
#             return None

#     async def search_patient_by_phone(self, table_name, phone_number):
#         """Search across all phone number fields with pagination handling"""
#         try:
#             table = self.resource.Table(table_name)
            
#             filter_expr = Attr('phone_number').eq(phone_number) | \
#                          Attr('home_number').eq(phone_number) | \
#                          Attr('work_number').eq(phone_number)
            
#             items = []
#             response = table.scan(FilterExpression=filter_expr)
#             items.extend(response.get('Items', []))
            
#             while 'LastEvaluatedKey' in response:
#                 response = table.scan(
#                     FilterExpression=filter_expr,
#                     ExclusiveStartKey=response['LastEvaluatedKey']
#                 )
#                 items.extend(response.get('Items', []))
                
#             return items
#         except ClientError as e:
#             print(f"Error searching patients: {e}")
#             return []
        
#     async def search_patient(self, table_name, phone_number, clinic_name=None):
#         """
#         Search patients by phone number (any type) and optional clinic name
#         """
#         try:
#             table = self.resource.Table(table_name)
            
#             # Base phone number condition
#             phone_condition = (
#                 Attr('phone_number').eq(phone_number) |
#                 Attr('home_number').eq(phone_number) |
#                 Attr('work_number').eq(phone_number)
#             )
            
#             # Combine with clinic name filter if provided
#             if clinic_name:
#                 filter_expr = phone_condition & Attr('clinic_name').eq(clinic_name)
#             else:
#                 filter_expr = phone_condition
            
#             items = []
#             response = table.scan(FilterExpression=filter_expr)
#             items.extend(response.get('Items', []))
            
#             # Pagination handling
#             while 'LastEvaluatedKey' in response:
#                 response = table.scan(
#                     FilterExpression=filter_expr,
#                     ExclusiveStartKey=response['LastEvaluatedKey']
#                 )
#                 items.extend(response.get('Items', []))
                
#             return items
            
#         except ClientError as e:
#             print(f"Error searching patients: {e}")
#             return []

#     async def delete_patient(self, table_name, patient_id):
#         """Delete a patient by Patient ID"""
#         try:
#             table = self.resource.Table(table_name)
#             response = table.delete_item(Key={'patient_id': patient_id})
#             return response
#         except ClientError as e:
#             print(f"Error deleting patient: {e}")
#             return None
        
#     async def list_all_tables(self):
#         """List all tables in DynamoDB"""
#         try:
#             response = self.resource.meta.client.list_tables()
#             return response.get('TableNames', [])
#         except ClientError as e:
#             print(f"Error listing tables: {e}")
#             return []

#     async def scan_table(self, table_name):
#         """Complete table scan with pagination support"""
#         try:
#             table = self.resource.Table(table_name)
#             items = []
#             response = table.scan()
#             items.extend(response.get('Items', []))
            
#             while 'LastEvaluatedKey' in response:
#                 response = table.scan(ExclusiveStartKey=response['LastEvaluatedKey'])
#                 items.extend(response.get('Items', []))
                
#             return items
#         except ClientError as e:
#             print(f"Error scanning table {table_name}: {e}")
#             return []

#     async def print_all_tables(self):
#         """Print all tables with formatted output"""
#         tables = self.list_all_tables()
#         print("\n=== DynamoDB Tables ===")
#         for table in tables:
#             self.print_table_contents(table)

#     async def _print_dynamodb_item(self, item):
#         """Helper to print items in readable format"""
#         for attr, value in item.items():
#             print(f"    {attr}: {value}")

#     async def print_table_contents(self, table_name):
#         """Print formatted contents of a specific table"""
#         try:
#             items = self.scan_table(table_name)
#             print(f"\nTable: {table_name}")
#             print(f"Items Found: {len(items)}")
#             for idx, item in enumerate(items, 1):
#                 print(f"\n  Patient #{idx}:")
#                 self._print_dynamodb_item(item)
#         except ClientError as e:
#             print(f"Error accessing table {table_name}: {e}")


#     async def batch_add_patients(self, table_name, patients):
#         try:
#             table = self.resource.Table(table_name)
#             added_count = 0  # To track how many patients were actually added

#             for patient in patients:
#                 patient_id = patient.get("patient_id")
#                 if not patient_id:
#                     print(f"Skipping patient due to missing 'patient_id': {patient}")
#                     continue

#                 # Check if the patient already exists in the table
#                 existing_patient = await self.get_patient_by_id(table_name, patient_id)

#                 if existing_patient:
#                     print(f"Patient with ID {patient_id} already exists. Skipping.")
#                     continue

#                 # If the patient does not exist, clean the data and add it
#                 cleaned_data = {k: v for k, v in patient.items() if v}  # Remove empty values
#                 table.put_item(Item=cleaned_data)
#                 added_count += 1
#                 print(f"Added patient with ID {patient_id}.")

#             print(f"Successfully added {added_count} new patients out of {len(patients)} total patients.")
#         except ClientError as e:
#             print(f"Error adding patients in batch: {e}")
            


#     async def fetch_all_patients_from_dynamodb(self, table_name):
#         """Fetch all patient records from DynamoDB."""
#         try:
#             table = self.resource.Table(table_name)
#             response = table.scan()  # Use scan to retrieve all records
#             patients = response.get("Items", [])
#             return patients
#         except ClientError as e:
#             print(f"Error fetching patients from DynamoDB: {e}")
#             return []
     

#     async def get_patient_by_id(self, table_name, patient_id):
#         try:
#             table = self.resource.Table(table_name)
#             response = table.get_item(Key={"patient_id": patient_id})
#             return response.get("Item", None)
#         except ClientError as e:
#             print(f"Error fetching patient {patient_id}: {e}")
#             return None
        
    
#     from botocore.exceptions import ClientError


# dynamo_client = DynamoDBClient(local=False)


# # async def main():
# #     db_manager = DynamoDBClient(local=False)
# #     # await db_manager.create_table("nookal-client")
# #     # await db_manager.getUpdatedUsers()  # This will print "Hello world"
# #     # await db_manager.getNewCreatedUsers()  # This will print "Hello world"

# # if __name__ == "__main__":
# #     asyncio.run(main())

# # Example usage:
# # async def main():
# #     # For local development
# #     db_manager = DynamoDBClient(local=False)
    
# #     # For AWS cloud
# #     # db_manager = DynamoDBClient(local=False)
    
# #     # Create table
# #     table_name = "dovestone-patients"
# #     # db_manager.create_table(table_name)
    
# #     # Add patient
# #     patient_data = {
# #         "phone_number": "123123",
# #         "home_number": "",
# #         "work_number": "",
# #         "patient_id": "124324327",
# #         "first_name": "Test",
# #         "last_name": "Test2",
# #         "date_of_birth": "1947-07-26",
# #         "clinic_name": "Doveston Health Clinic"
# #     }
# #     await db_manager.add_patient(table_name, patient_data)
    
# #     #Search patients
# #     results = db_manager.search_patient_by_phone(table_name, "123123")
# #     print("Search results:", results)

# #     # # Update patient
# #     # update_data = {
# #     #     "phone_number": "5555555555",
# #     #     "home_number": "1111111111"
# #     # }
# #     # db_manager.update_patient(table_name, "124324326", update_data)
    
# #     # Delete patient
# #     # db_manager.delete_patient(table_name, "124324326")
    
# #     # print("\nPrinting all tables and contents...")
# #     # db_manager.print_all_tables()
    
# # if __name__ == "__main__":
# #     asyncio.run(main())