import asyncio
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse
import stripe
from decimal import Decimal, ROUND_HALF_UP
from src.db.db import DB
from pprint import pprint
import firebase_admin.firestore
from firebase_admin import firestore
from dotenv import load_dotenv
import os
load_dotenv()

router = APIRouter(prefix="/payment")
# stripe.api_key = os.getenv("STRIPE_API_KEY")  # Set via environment variable

db = DB()

def calculate_subscription_cost(user_id):
    """Calculates the monthly cost of the usage with 10% GST."""
    
    client_data = db.read_from_firestore("credits", user_id)

    total_call_cost = client_data.get("unpaidCost", 0)

    # Add 10% GST
    total_with_gst = total_call_cost * 1.10  

    return int(total_with_gst * 100)  # Convert to cents for Stripe

@router.post('/ai-usage-payment')
async def ai_usage_payment(request: Request):
    try:
        data = await request.json()
        required_fields = ['userId']

        for field in required_fields:
            if field not in data:
                raise HTTPException(status_code=400, detail=f"Missing required field: {field}")
        
        total_cost = calculate_subscription_cost(data['userId'])
        payment= stripe.PaymentIntent.create(
            amount=total_cost,
            currency='aud', 
        )
        pprint(payment)
        return JSONResponse({
            'clientSecret': payment['client_secret'],
            'paymentIntentId': payment['id']
        })
    except Exception as e:
        pprint(str(e))
        raise HTTPException(status_code=403, detail=str(e))


@router.post('/save-ai-payment')
async def save_ai_payment(request: Request):
    try:
        data = await request.json()
        response = db.save_payment(data)

        if response['success']:
                return JSONResponse(content=response, status_code=200)
        else:
            raise HTTPException(status_code=400, detail=response['message'])
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=f"Invalid input: {str(ve)}")
    except HTTPException as he:
        raise he  # Re-raise HTTP exceptions
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")




###___________________FOR FUTURE USE__________________###

@router.get('/store-subscription-details')
async def get_subscription_details(session_id: str, user_id: str):
    try:

        # Retrieve the Checkout Session
        session = stripe.checkout.Session.retrieve(session_id)

        # Retrieve the Subscription
        subscription = stripe.Subscription.retrieve(session.subscription)
        subscription_id = subscription.id
        subscription_customer_id = subscription.customer
        
        user = db.read_from_firestore("users_auth", user_id)
        
        if user is None:
            return {"success": False, "message": "User not found"}
        
        # if user does not have a creditId, create a new creditId
        if user.get('creditId', '') == '':
            db.write_to_firestore(
                    collection_name="credits", 
                    data= { 
                        'subscriptionPlan': 'basic', 
                        'stripeCustomerId': subscription_customer_id, 
                        'subscriptionId': subscription_id,
                        'isActive': True,
                        'unpaidCost': 0,
                        'unpaidCalls': 0,
                        'unpaidMinutes': 0,
                        'totalCost': 0,
                        'totalMinutes': 0,
                        'totalCalls': 0,
                        'averageCostPerCall': 0,
                        'locations': 1,
                        'practitioners': 1,
                        'uid': user_id,
                        'createdAt': firestore.SERVER_TIMESTAMP,
                        'updatedAt': firestore.SERVER_TIMESTAMP
                    },
                    user_id=user_id, 
                )
            db.update_in_firestore(collection_name="users_auth", data={"creditId": user_id}, user_id=user_id)
            user['creditId'] = user_id
        else:
            db.update_in_firestore(
                    collection_name="credits", 
                    data= { 
                        'stripeCustomerId': subscription_customer_id, 
                        'subscriptionId': subscription_id,
                        'subscriptionPlan': 'basic',
                        'isActive': True,
                        'unpaidCost': 0,
                        'unpaidCalls': 0,
                        'unpaidMinutes': 0,
                        'locations': 1,
                        'practitioners': 1,
                        'updatedAt': firestore.SERVER_TIMESTAMP
                    },
                    user_id=user_id
                )   

        return {
            "plan": subscription.plan.nickname,
            "amount": subscription.plan.amount,
            "status": subscription.status,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get('/store-update-subscription-details')
async def get_update_subscription_details(session_id: str, user_id: str, practitionersAdded: str, locationsAdded: str):
    try:

        # Retrieve the Checkout Session
        session = stripe.checkout.Session.retrieve(session_id)

        # Retrieve the Subscription
        subscription = stripe.Subscription.retrieve(session.subscription)
        subscription_id = subscription.id
        subscription_customer_id = subscription.customer
        print(practitionersAdded, type(practitionersAdded), locationsAdded, type(locationsAdded))
        practitionersAdded = int(practitionersAdded)
        locationsAdded = int(locationsAdded)

        update_data= {
            'updatedAt': firestore.SERVER_TIMESTAMP,
            'subscriptionPlan': 'custom', 
            'stripeCustomerId': subscription_customer_id, 
            'subscriptionId': subscription_id,
            'practitioners': firestore.Increment(practitionersAdded),
            'locations': firestore.Increment(locationsAdded),
        }

        db.update_in_firestore(collection_name="credits", 
                               data=update_data,
                               user_id=user_id)

        return {
            "plan": subscription.plan.nickname,
            "amount": subscription.plan.amount,
            "status": subscription.status,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post('/create-checkout-session')
async def create_checkout_session(request: Request):
    try:
        stripe.api_key = os.getenv("STRIPE_API_KEY", "")
        data = await request.json()
        locations = data['practitonersCount']
        practitioners = data['locationsCount']
        base_price = data['basePrice']

        print("Details from data",locations, practitioners, base_price)

        location_cost= (locations-1) * 50
        practitioner_cost= (practitioners-1) * 50

        total_price = base_price + location_cost + practitioner_cost


        price = stripe.Price.create(
            unit_amount=total_price * 100,
            currency="aud",
            recurring={"interval": "month"},
            product_data={"name": "Basic Plan"},
        )

        line_items = [{
            'price': price.id,
            'quantity': 1,
        }]
        
        session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=line_items,
            mode='subscription',
            success_url='https://www.yourfrontdeskai.com.au/admin/billing?session_id={CHECKOUT_SESSION_ID}&success=true',
            cancel_url='https://www.yourfrontdeskai.com.au/admin/billing?success=false',
        )

        return {'sessionId': session.id}
    except Exception as e:
        pprint(str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post('/update-subscription')
async def update_subscription(request: Request):
    try:

        stripe.api_key = os.getenv("STRIPE_API_KEY", "")
        data = await request.json()
        user_id = data["userId"]  # user ID is passed in the request
        practitioners_added = int(data.get("practitionersAdded", 0))
        locations_added = int(data.get("locationsAdded", 0))

        if practitioners_added == 0 and locations_added == 0:
            raise HTTPException(status_code=400, detail="No changes made to subscription")

        # Fetch the current practitioner's count, locations count, and subscription ID from Firestore
        user_data = db.read_from_firestore(collection_name="credits", user_id=user_id)
        subscription_id = user_data.get("subscriptionId")

        if not subscription_id:
            raise HTTPException(status_code=400, detail="No subscription ID found for the user")

        # Calculate new cost based on added practitioners and locations
        additional_practitioner_cost = max(0, practitioners_added * 50)  # Charge only for added practitioners
        additional_location_cost = max(0, locations_added * 50)  # Charge only for added locations
        total_new_cost = additional_practitioner_cost + additional_location_cost

        # Only create a checkout session if there is an additional charge
        if total_new_cost > 0:
            price = stripe.Price.create(
                unit_amount=total_new_cost * 100,  # Convert to cents
                currency="aud",
                recurring={"interval": "month"},
                product_data={"name": "Custom Plan"},
            )

            # Create a Stripe Checkout session for additional cost
            line_items = [{
                "price": price.id,
                "quantity": 1,
            }]

            session = stripe.checkout.Session.create(
                payment_method_types=["card"],
                line_items=line_items,
                mode="subscription",
                success_url="https://www.yourfrontdeskai.com.au/admin/billing?session_id={CHECKOUT_SESSION_ID}&success=true&type=update&practitionersAdded=" + str(practitioners_added) + "&locationsAdded=" + str(locations_added),
                cancel_url="https://www.yourfrontdeskai.com.au/admin/billing?success=false",
            )

            return {"sessionId": session.id}
        
        return {"message": "Subscription updated successfully."}

    except Exception as e:
        pprint(str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cancel-subscription")
async def cancel_subscription(request: Request):
    """Cancels a Stripe subscription."""
    try:
        stripe.api_key = os.getenv("STRIPE_API_KEY", "")
        data = await request.json()
        user_id = data["userId"]
        db_info= db.read_from_firestore("credits", user_id)
        subscription_id = db_info["subscriptionId"]

        # Cancel the subscription
        stripe.Subscription.cancel(subscription_id)

        db.update_in_firestore(
            collection_name="credits", 
            data={'isActive': False,
            'updatedAt': firestore.SERVER_TIMESTAMP,
            'subscriptionPlan': "cancelled"},
            user_id=user_id
            )

        return JSONResponse({"message": "Subscription canceled successfully."})

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error canceling subscription: {str(e)}")
    