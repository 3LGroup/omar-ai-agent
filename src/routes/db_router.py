#_____________________________DB Router ENDPOINTS_____________________________________
from fastapi import APIRouter, HTTPException, Query, Request
from firebase_admin import auth
from firebase_admin import firestore
from src.db.db import DB


router = APIRouter(prefix="/firebase")
db= DB()
@router.post('/update-user-status')
async def update_user_status(request: Request):
    try:
        data = await request.json()
        required_fields = ['userId', 'status']

        for field in required_fields:
            if field not in data:
                raise HTTPException(status_code=400, detail=f"Missing required field: {field}")

        user_id = data['userId']
        status = data['status'].lower()
        
        if status not in ["activate", "deactivate"]:
            raise HTTPException(status_code=400, detail="Invalid status. Use 'activate' or 'deactivate'.")

        if status == "deactivate":
            auth.update_user(user_id, disabled=(status == "deactivate"))

            db.update_in_firestore(
                collection_name="users_auth", 
                data = { 
                    'status': "inactive",
                    'updatedAt': firestore.SERVER_TIMESTAMP
                }, 
                user_id=user_id)
        elif status== "activate":
            auth.update_user(user_id, disabled=(status == "deactivate"))
            db.update_in_firestore(
                collection_name="users_auth", 
                data = { 
                    'status': "active",
                    'updatedAt': firestore.SERVER_TIMESTAMP
                }, 
                user_id=user_id)

        return {"message": f"User {status}d successfully", "userId": user_id}
    
    except auth.UserNotFoundError:
        raise HTTPException(status_code=404, detail="User not found")
    except Exception as e:
        print(f"Error updating user status: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server, {str(e)}")
    

@router.post('/create-user')
async def create_user(request: Request):
    try:
        data = await request.json()
        required_fields = ['clinicName', 'email', 'phoneNumber', 'password', 'locations', 'practitioners']

        for field in required_fields:
            if field not in data:
                raise HTTPException(status_code=400, detail=f"Missing required field: {field}")
        
        user = auth.create_user(
            display_name=data['clinicName'],
            email=data['email'],
            phone_number=data['phoneNumber'],
            password=data['password'],
            # photo_url=data['photo']
        )

        locations = int(data['locations'])
        practitioners = int(data['practitioners'])

        db.write_to_firestore(
                    collection_name="users_auth", 
                    data= { 
                        'status': "active",
                        'access': "INBOUND",
                        'clinicName': data['clinicName'],   
                        'email': data['email'],
                        'uid': user.uid,
                        'locations': locations,
                        'practitioners': practitioners,
                        'role': "USER",
                        'createdAt': firestore.SERVER_TIMESTAMP,
                        'updatedAt': firestore.SERVER_TIMESTAMP
                    },)
                    
        return {"message": "User created successfully", "userId": user.uid}
    
    except Exception as e:
        print(f"Error create user: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error, {str(e)}")
    
@router.get('/get-users')
async def get_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, le=50),
    name: str = Query(None),
    status: str = Query(None),
    uid: str = Query(None)
):
    try:
        if not name and not status and not uid:
            users_ref = db.db.collection("users_auth").order_by("createdAt")
        else:
            users_ref = db.db.collection("users_auth")
        
        # Incase of Filters Query
        if name:
            users_ref = users_ref.where("clinicName", "==", name)
        if status:
            users_ref = users_ref.where("status", "==", status)
        if uid:
            users_ref = users_ref.where("uid", "==", uid)
        
        # Pagination
        users_ref = users_ref.offset((page - 1) * page_size).limit(page_size)
        users_docs = users_ref.stream()
        
        users_data = []
        
        for doc in users_docs:
            user = doc.to_dict()
            uid = user.get("uid")
            profile_image_url = None
            
            profile_image_url = await db.get_profile_image_url(uid)
            
            users_data.append({
                "uid": user.get("uid"),
                "email": user.get("email"),
                "name": user.get("clinicName"),
                "locations": user.get("locations"),
                "practitioners": user.get("practitioners"),
                "status": user.get("status"),
                "createdAt": user.get("createdAt").isoformat() if user.get("createdAt") else None,
                "profileImage": profile_image_url
            })
        
        return {"success": True, "users": users_data, "page": page, "page_size": page_size}
    
    except Exception as e:
        print(f"Error retrieving users: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error, {str(e)}")