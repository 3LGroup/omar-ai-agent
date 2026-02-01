from pprint import pprint
import firebase_admin
from google.cloud import firestore
from firebase_admin import credentials
from firebase_admin import firestore as firestore_client
import os
from datetime import datetime
from google.cloud.firestore_v1 import FieldFilter
from google.cloud import storage
from google.oauth2 import service_account
class DB:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DB, cls).__new__(cls)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self):
        current_dir = os.path.dirname(os.path.abspath(__file__))
        secret_path = os.path.join(current_dir, 'secrets.json')

        # Handle missing or invalid Firebase credentials gracefully
        try:
            if os.path.exists(secret_path):
                self.cred = credentials.Certificate(secret_path)
                self.storage_credentials = service_account.Credentials.from_service_account_file(secret_path)

                try:
                    self.app = firebase_admin.get_app()
                except ValueError:
                    self.app = firebase_admin.initialize_app(credential=self.cred)

                self.db = firestore_client.client()
            else:
                print("Warning: Firebase secrets.json not found. Firebase features disabled.")
                self.cred = None
                self.storage_credentials = None
                self.app = None
                self.db = None
        except Exception as e:
            print(f"Warning: Firebase initialization failed: {e}. Firebase features disabled.")
            self.cred = None
            self.storage_credentials = None
            self.app = None
            self.db = None

    def write_to_firestore(self, collection_name, data, user_id = None):
        if user_id is None:
            doc_ref = self.db.collection(collection_name).document()
        else:
            doc_ref = self.db.collection(collection_name).document(user_id)
        
        doc_ref.set(data)
        return doc_ref

    def get_calls_for_user(self, user_id):
        doc_ref = self.db.collection('calls_tracking').where('admin_id', '==', user_id)
        docs = doc_ref.stream()
        data = []
        for doc in docs:
            doc_dict = doc.to_dict()
            # Convert Firestore timestamps to ISO format strings
            for key, value in doc_dict.items():
                if isinstance(value, datetime):
                    doc_dict[key] = value.isoformat()
            data.append(doc_dict)
        return data

    def get_credits_for_user(self, user_id):
        doc_ref = self.db.collection('credits').where('uid', '==', user_id)
        docs = doc_ref.stream()
        data = []
        for doc in docs:
            doc_dict = doc.to_dict()
            # Convert Firestore timestamps to ISO format strings
            for key, value in doc_dict.items():
                if isinstance(value, datetime):
                    doc_dict[key] = value.isoformat()
            data.append(doc_dict)
        return data


    def get_user_by_agent_id(self, agent_id, inbound = True):
        if inbound:
            inbound_doc_ref = self.db.collection('users_auth').where('inboundAgent', '==', agent_id).limit(1)
            # inbound_doc_ref = self.db.collection('users_auth').where('testAgent', '==', agent_id).limit(1)
            inbound_docs = inbound_doc_ref.stream()
        else:
            inbound_doc_ref = self.db.collection('users_auth').where('outBoundAgent', '==', agent_id).limit(1)
            inbound_docs = inbound_doc_ref.stream()

        data = []

        for doc in inbound_docs:
            data.append(doc.to_dict())

        return data



    def read_from_firestore(self, collection_name, user_id):
        doc_ref = self.db.collection(collection_name).where('uid', '==', user_id).limit(1)
        docs = doc_ref.stream()

        for doc in docs:
            return doc.to_dict()

    def delete_from_firestore(self):
        doc_ref = self.db.collection("test_coll").document("test_doc")
        doc_ref.delete()

    def update_in_firestore(self, collection_name, data, user_id):
        doc_ref = self.db.collection(collection_name).where('uid', '==', user_id).limit(1)
        docs = doc_ref.stream()

        for doc in docs:
            # Get the reference to the actual document
            doc_ref = doc.reference
            
            # Update the document in Firestore
            doc_ref.update(data)
            
            # Fetch the updated document
            updated_doc = doc_ref.get()
            
            print("Updated document:", updated_doc.to_dict())
            return updated_doc.to_dict()

    def read_by_agent_id(self, collection_name, agent_id, inbound = True):

        if inbound:
            doc_ref = self.db.collection(collection_name).where('inboundAgent', '==', agent_id).limit(1)
            # doc_ref = self.db.collection(collection_name).where('testAgent', '==', agent_id).limit(1)
        else:
            doc_ref = self.db.collection(collection_name).where('outBoundAgent', '==', agent_id).limit(1)

        docs = doc_ref.stream()

        for doc in docs:
            return doc.to_dict()

    def save_payment(self, data):
        # this is provided from the frontend
        user_id = data['userId']
        paidAmount = data['paidAmount']
        paymentIntentId = data['paymentIntentId']
        paymentMethod = data['paymentMethod']
        totalAUDAmount = data['totalAUDAmount']

        # get user data from firestore from users_auth collection
        user = self.read_from_firestore("users_auth", user_id)
        pprint(user)

        if user is None:
            return {"success": False, "message": "User not found"}
        
        # get unpaidCost from firestore from credits collection
        db_data = self.read_from_firestore("credits", user_id)
        staff= db_data['staff']
        locations = db_data['locations']
        
        # if user does not have a creditId, create a new creditId
        if user.get('creditId', '') == '':
            self.write_to_firestore(
                    collection_name="credits", 
                    data= { 
                        'subscriptionPlan': 'basic', 
                        'isActive': True,
                        'unpaidCost': 0,
                        'unpaidCalls': 0,
                        'unpaidMinutes': 0,
                        'totalCost': 0,
                        'totalMinutes': 0,
                        'totalCalls': 0,
                        'averageCostPerCall': 0,
                        'locations': locations,
                        'staff': staff,
                        'uid': user_id,
                        'createdAt': firestore.SERVER_TIMESTAMP,
                        'updatedAt': firestore.SERVER_TIMESTAMP
                    },
                    user_id=user_id, 
                )
            self.update_in_firestore(collection_name="users_auth", data={"creditId": user_id}, user_id=user_id)
            user['creditId'] = user_id
            return {"success": True, "message": "First Time Payment saved successfully"}
        else:
            self.update_in_firestore(
                collection_name="credits", 
                data = { 
                    'unpaidCost': 0,
                    'unpaidMinutes': 0,
                    'unpaidCalls': 0,
                    'updatedAt': firestore.SERVER_TIMESTAMP
                }, 
                user_id=user_id
            )

        # write the transaction to the transactions collection
        self.write_to_firestore(
            collection_name="transactions",
            data= { 
                "amountPaid": paidAmount,
                "creditId": user_id,
                "paymentIntentId": paymentIntentId,
                "paymentMethod": paymentMethod,
                "totalAUDAmount": totalAUDAmount,
                "userId": user_id,
                'createdAt': firestore.SERVER_TIMESTAMP,
                'updatedAt': firestore.SERVER_TIMESTAMP
            }
        )
        return {"success": True, "message": "Payment saved successfully"}        


    async def get_clinic_data(self, agent_id):
        # doc_ref = self.db.collection('users_auth').where(filter=FieldFilter('inboundAgent', '==', agent_id)).limit(1)
        doc_ref = self.db.collection('users_auth').where(filter=FieldFilter('testAgent', '==', agent_id)).limit(1)
        docs = doc_ref.stream()

        # Iterate through the documents
        for doc in docs:
            output = doc.to_dict()  # Convert the document snapshot to a dictionary
            print(f"Output: {output}")

            return output


    def get_clinic_data_sync(self, agent_id):
        # doc_ref = self.db.collection('users_auth').where(filter=FieldFilter('inboundAgent', '==', agent_id)).limit(1)
        doc_ref = self.db.collection('users_auth').where(filter=FieldFilter('testAgent', '==', agent_id)).limit(1)

        docs = doc_ref.stream()

        # Iterate through the documents
        for doc in docs:
            output = doc.to_dict()  # Convert the document snapshot to a dictionary
            print(f"Output: {output}")

            return output

    def update_token_data_in_firestore(self, collection_name, data, agent_id):
        doc_ref = self.db.collection(collection_name).where(filter=FieldFilter('inboundAgent', '==', agent_id)).limit(1)
        # doc_ref = self.db.collection(collection_name).where(filter=FieldFilter('testAgent', '==', agent_id)).limit(1)
        docs = doc_ref.stream()

        for doc in docs:
            # Get the reference to the actual document
            doc_ref = doc.reference
            
            # Update the document in Firestore
            doc_ref.update(data)
            
            # Fetch the updated document
            updated_doc = doc_ref.get()
            
            print("Updated document:", updated_doc.to_dict())
            return updated_doc.to_dict()
        

    def get_all_records(self, collection):
        doc_ref = self.db.collection(collection)
        docs = doc_ref.stream()

        data = []

        for doc in docs:
            output = doc.to_dict()  # Convert the document snapshot to a dictionary
            data.append(output)

        return data


    def delete_documents(self, collection, user_id):
        try:
            # Query documents where agent_id matches
            docs = self.db.collection(collection).where("admin_id", "==", user_id ).stream()

            # Iterate and delete each document
            deleted_count = 0
            for doc in docs:
                self.db.collection(collection).document(doc.id).delete()
                print(f"Deleted document ID: {doc.id}")
                deleted_count += 1

            print(f"\nTotal documents deleted: {deleted_count}")
        except Exception as e:
            print("Error deleting documents:", str(e))
            
    
    async def get_profile_image_url(self, uid):
        storage_client = storage.Client(project='my-library-793bd', credentials=self.storage_credentials)
        bucket = storage_client.bucket("my-library-793bd.appspot.com")

        blobs = list(bucket.list_blobs(prefix=f"profileImages/{uid}"))
        
        if blobs:
            blob = blobs[0]
            
            # Fetch metadata to get the token
            metadata = blob.metadata
            if metadata and "firebaseStorageDownloadTokens" in metadata:
                token = metadata["firebaseStorageDownloadTokens"]
                return f"https://firebasestorage.googleapis.com/v0/b/my-library-793bd.appspot.com/o/{blob.name.replace('/', '%2F')}?alt=media&token={token}"

        return None
    
    