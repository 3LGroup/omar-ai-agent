"""
Three Lines Operations Agent Router
API endpoints for the internal operations assistant
"""

import asyncio
import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional, List
from src.components.odoo.llm import ThreeLinesLLMClient, ThreeLinesWebClient
from src.components.odoo.odoo_client import OdooClient
from src.utils.custom_types import CustomLlmRequest, CustomLlmResponse
from src.logger import logger

router = APIRouter(prefix="/threelines", tags=["Three Lines Operations"])


# ============== Pydantic Models ==============

class ChatRequest(BaseModel):
    message: str
    conversation_history: Optional[List[dict]] = None


class ProductSearchRequest(BaseModel):
    query: Optional[str] = None
    part_number: Optional[str] = None
    category: Optional[str] = None


class OrderStatusRequest(BaseModel):
    order_number: str


class QuoteRequest(BaseModel):
    customer_name: str
    customer_email: str
    customer_phone: Optional[str] = ""
    products: List[dict]  # [{"part_number": "ABC123", "quantity": 5}]
    notes: Optional[str] = ""


# ============== Health & Test Endpoints ==============

@router.get("/health")
async def health_check():
    """Check if the Three Lines Operations Agent is running"""
    return {"status": "ok", "agent": "Omar", "company": "Three Lines"}


@router.get("/test-odoo")
async def test_odoo_connection():
    """Test connection to Odoo"""
    try:
        odoo = OdooClient()
        result = odoo.test_connection()
        return JSONResponse(content=result, status_code=200 if result["connected"] else 500)
    except Exception as e:
        return JSONResponse(content={"connected": False, "error": str(e)}, status_code=500)


# ============== Chat Endpoint (Web Interface) ==============

@router.post("/chat")
async def chat_endpoint(request: ChatRequest):
    """
    Chat with Omar, the Operations Assistant

    This is the main endpoint for web-based chat interactions.
    """
    try:
        client = ThreeLinesWebClient()
        response = await client.chat(
            message=request.message,
            conversation_history=request.conversation_history
        )
        return JSONResponse(content=response, status_code=200)
    except Exception as e:
        logger.error(f"Error in chat endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============== WebSocket for Voice/Real-time ==============

@router.websocket("/voice/{call_id}")
async def websocket_handler(websocket: WebSocket, call_id: str):
    """
    WebSocket handler for voice conversations with Omar
    Compatible with Retell AI
    """
    await websocket.accept()

    # Send config
    config = CustomLlmResponse(
        response_type="config",
        config={
            "auto_reconnect": True,
            "call_details": True,
        },
        response_id=1,
    )
    await websocket.send_text(json.dumps(config.__dict__))

    llm_client = ThreeLinesLLMClient()

    # Send initial greeting
    response_id = 0
    first_event = llm_client.draft_begin_message()
    await websocket.send_text(json.dumps(first_event.__dict__))

    async def stream_response(request: CustomLlmRequest):
        nonlocal response_id
        for event in llm_client.draft_response(request):
            if event.__dict__:
                await websocket.send_text(json.dumps(event.__dict__))
                await asyncio.sleep(0.005)
            if request.response_id < response_id:
                return

    try:
        while True:
            message = await asyncio.wait_for(
                websocket.receive_text(), timeout=100 * 60
            )
            request_json = json.loads(message)
            request: CustomLlmRequest = CustomLlmRequest(**request_json)

            if request.interaction_type == "call_details":
                continue
            if request.interaction_type == "ping_pong":
                await websocket.send_text(
                    json.dumps({"response_type": "ping_pong", "timestamp": request.timestamp})
                )
                continue
            if request.interaction_type == "update_only":
                continue
            if request.interaction_type in ["response_required", "reminder_required"]:
                response_id = request.response_id
                asyncio.create_task(stream_response(request))

    except WebSocketDisconnect as e:
        logger.info(f"WebSocket disconnected for {call_id}: {e}")
    except Exception as e:
        logger.error(f"Error in WebSocket: {e}")
    finally:
        logger.info(f"WebSocket connection closed for {call_id}")


# ============== Direct API Endpoints ==============

@router.post("/products/search")
async def search_products(request: ProductSearchRequest):
    """Search for products in inventory"""
    try:
        odoo = OdooClient()
        results = odoo.search_products(
            query=request.query,
            part_number=request.part_number,
            category=request.category
        )
        return JSONResponse(content={"products": results}, status_code=200)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/products/{part_number}")
async def get_product(part_number: str):
    """Get a specific product by part number"""
    try:
        odoo = OdooClient()
        product = odoo.get_product_by_part_number(part_number)
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")
        return JSONResponse(content=product, status_code=200)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/products/{part_number}/availability")
async def check_availability(part_number: str):
    """Check stock availability for a product"""
    try:
        odoo = OdooClient()
        result = odoo.check_stock_availability(part_number=part_number)
        return JSONResponse(content=result, status_code=200)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/orders/status")
async def get_order_status(request: OrderStatusRequest):
    """Get status of a sales order"""
    try:
        odoo = OdooClient()
        order = odoo.get_order_status(request.order_number)
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")
        return JSONResponse(content=order, status_code=200)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/orders/customer/{customer_email}")
async def get_customer_orders(customer_email: str):
    """Get all orders for a customer"""
    try:
        odoo = OdooClient()
        orders = odoo.get_customer_orders(customer_email=customer_email)
        return JSONResponse(content={"orders": orders}, status_code=200)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/purchase-orders/{po_number}")
async def get_po_status(po_number: str):
    """Get status of a purchase order"""
    try:
        odoo = OdooClient()
        po = odoo.get_purchase_order_status(po_number)
        if not po:
            raise HTTPException(status_code=404, detail="Purchase order not found")
        return JSONResponse(content=po, status_code=200)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/suppliers")
async def search_suppliers(query: str = ""):
    """Search for suppliers"""
    try:
        odoo = OdooClient()
        suppliers = odoo.search_suppliers(query=query)
        return JSONResponse(content={"suppliers": suppliers}, status_code=200)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/customers")
async def search_customers(query: str = ""):
    """Search for customers"""
    try:
        odoo = OdooClient()
        customers = odoo.search_customers(query=query)
        return JSONResponse(content={"customers": customers}, status_code=200)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/quotes/create")
async def create_quote(request: QuoteRequest):
    """Create a new quotation/RFQ"""
    try:
        odoo = OdooClient()
        result = odoo.create_quote_request(
            customer_name=request.customer_name,
            customer_email=request.customer_email,
            customer_phone=request.customer_phone,
            products=request.products,
            notes=request.notes
        )
        return JSONResponse(content=result, status_code=201 if result.get("success") else 400)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/categories")
async def get_categories():
    """Get all product categories"""
    try:
        odoo = OdooClient()
        categories = odoo.get_product_categories()
        return JSONResponse(content={"categories": categories}, status_code=200)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
