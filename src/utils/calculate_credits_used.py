from src.db.db import DB
from google.cloud import firestore

async def update_total_cost(cost_per_call, call_time, agent_id, inbound=True):
    db = DB()
    user = db.read_by_agent_id("users_auth", agent_id, inbound)
    user_id = user['uid']
    locations = user['locations']
    staff = user['staff']

    # if creditID doesnt exists then make a collection in credits
    if user.get('creditId', '') == '':
            print("First Time Payment saved successfully inside if")
            db.write_to_firestore(
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
            db.update_in_firestore(collection_name="users_auth", data={"creditId": user_id}, user_id=user_id)
            user['creditId'] = user_id


    #Life Time History of client
    cost_per_call = round(float(cost_per_call), 3)
    print("Cost per call: ", cost_per_call)
    call_time= round(float(call_time), 3)
    print("Call time: ", call_time)
    data = {
            'totalCost': firestore.Increment(cost_per_call),
            'totalMinutes': firestore.Increment(call_time),
            'totalCalls': firestore.Increment(1),
        }

    db.update_in_firestore(collection_name="credits", data=data, user_id=user['uid'])

    updated_user = db.read_from_firestore("credits", user['uid'])
    
    # Calculate avg cost per call if totalCalls is greater than 0
    total_cost = updated_user.get('totalCost', 0)
    total_calls = updated_user.get('totalCalls', 1)  # Avoid division by zero
    
    avg_cost_per_call = total_cost / total_calls
    avg_cost_per_call = round(float(avg_cost_per_call), 3)
    
    # Save the avg cost per call to Firestore
    db.update_in_firestore(
        collection_name="credits",
        data={'averageCostPerCall': avg_cost_per_call},
        user_id=user['uid']
    )

    # For payment, values are converted to zero after each payment
    db.update_in_firestore(
        collection_name="credits",
        data={'unpaidCost': firestore.Increment(cost_per_call), 
              'unpaidMinutes': firestore.Increment(call_time), 
              'unpaidCalls': firestore.Increment(1)},
        user_id=user['uid']
    )