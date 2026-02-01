"""
Three Lines Operations Agent LLM Client
Handles conversations and function calling for internal operations
"""

import json
from typing import Generator
from openai import OpenAI
from src.utils.custom_types import CustomLlmRequest, CustomLlmResponse
from src.components.odoo.odoo_client import OdooClient
from src.components.odoo.function_schemas import THREELINES_FUNCTIONS
from src.components.prompts.ThreeLines import (
    THREE_LINES_SYSTEM_PROMPT,
    THREE_LINES_FUNCTION_CALLING_PROMPT,
    OMAR_GREETING_EN
)
from src.logger import logger
import os


class ThreeLinesLLMClient:
    """LLM Client for Three Lines Operations Agent"""

    def __init__(self):
        # Use custom API endpoint (AI3Lines or OpenAI-compatible)
        self.client = OpenAI(
            api_key=os.getenv("OPENAI_API_KEY"),
            base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
        )
        self.model = os.getenv("OPENAI_MODEL", "gpt-4-turbo-preview")
        # Set to False if your model doesn't support function calling
        self.use_function_calling = os.getenv("USE_FUNCTION_CALLING", "true").lower() == "true"
        self.odoo = OdooClient()

        self.system_prompt = f"{THREE_LINES_SYSTEM_PROMPT}\n\n{THREE_LINES_FUNCTION_CALLING_PROMPT}"

        self.conversation_history = []
        self.function_results = {}

    def draft_begin_message(self) -> CustomLlmResponse:
        """Send initial greeting"""
        response = CustomLlmResponse(
            response_id=0,
            content=OMAR_GREETING_EN,
            content_complete=True,
            end_call=False,
        )
        return response

    def draft_response(self, request: CustomLlmRequest) -> Generator[CustomLlmResponse, None, None]:
        """Generate response based on user input"""

        # Build conversation history from transcript
        messages = [{"role": "system", "content": self.system_prompt}]

        # Add transcript history
        if request.transcript:
            for turn in request.transcript:
                role = "assistant" if turn.get("role") == "agent" else "user"
                content = turn.get("content", "")
                if content:
                    messages.append({"role": role, "content": content})

        try:
            # Call API - with or without function calling based on config
            if self.use_function_calling:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    tools=[{"type": "function", "function": f} for f in THREELINES_FUNCTIONS],
                    tool_choice="auto",
                    stream=True
                )
            else:
                # Simple chat without function calling
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    stream=True
                )

            # Process streamed response
            full_response = ""
            function_calls = []
            current_tool_call = None

            for chunk in response:
                if not chunk.choices:
                    continue

                delta = chunk.choices[0].delta

                # Handle function calls (only if enabled)
                if self.use_function_calling and delta.tool_calls:
                    for tool_call in delta.tool_calls:
                        if tool_call.index is not None:
                            if current_tool_call is None or tool_call.index != current_tool_call.get("index"):
                                if current_tool_call:
                                    function_calls.append(current_tool_call)
                                current_tool_call = {
                                    "index": tool_call.index,
                                    "id": tool_call.id or "",
                                    "name": "",
                                    "arguments": ""
                                }

                            if tool_call.function:
                                if tool_call.function.name:
                                    current_tool_call["name"] = tool_call.function.name
                                if tool_call.function.arguments:
                                    current_tool_call["arguments"] += tool_call.function.arguments

                # Handle text content
                if delta.content:
                    full_response += delta.content
                    yield CustomLlmResponse(
                        response_id=request.response_id,
                        content=delta.content,
                        content_complete=False,
                        end_call=False,
                    )

            # Add final tool call if exists
            if current_tool_call:
                function_calls.append(current_tool_call)

            # Process function calls
            if function_calls:
                for func_call in function_calls:
                    func_name = func_call.get("name", "")
                    func_args_str = func_call.get("arguments", "{}")

                    try:
                        func_args = json.loads(func_args_str) if func_args_str else {}
                    except json.JSONDecodeError:
                        func_args = {}

                    logger.info(f"Calling function: {func_name} with args: {func_args}")

                    # Execute the function
                    result = self._execute_function(func_name, func_args)

                    # Check if we should end the call
                    if func_name == "end_call":
                        yield CustomLlmResponse(
                            response_id=request.response_id,
                            content="Thank you for using Three Lines Operations Assistant. Goodbye!",
                            content_complete=True,
                            end_call=True,
                        )
                        return

                    # Generate response based on function result
                    follow_up_response = self._generate_response_from_result(
                        func_name, func_args, result, messages
                    )

                    yield CustomLlmResponse(
                        response_id=request.response_id,
                        content=follow_up_response,
                        content_complete=True,
                        end_call=False,
                    )
                    return

            # If no function calls, send complete marker
            if full_response:
                yield CustomLlmResponse(
                    response_id=request.response_id,
                    content="",
                    content_complete=True,
                    end_call=False,
                )

        except Exception as e:
            logger.error(f"Error in draft_response: {e}")
            yield CustomLlmResponse(
                response_id=request.response_id,
                content="I apologize, I encountered an error. Could you please repeat your request?",
                content_complete=True,
                end_call=False,
            )

    def _execute_function(self, func_name: str, args: dict) -> dict:
        """Execute a function and return the result"""
        try:
            if func_name == "search_products":
                return self.odoo.search_products(
                    query=args.get("query"),
                    part_number=args.get("part_number"),
                    category=args.get("category")
                )

            elif func_name == "check_stock_availability":
                return self.odoo.check_stock_availability(
                    part_number=args.get("part_number")
                )

            elif func_name == "get_order_status":
                return self.odoo.get_order_status(args.get("order_number"))

            elif func_name == "get_customer_orders":
                return self.odoo.get_customer_orders(
                    customer_name=args.get("customer_name"),
                    customer_email=args.get("customer_email")
                )

            elif func_name == "get_purchase_order_status":
                return self.odoo.get_purchase_order_status(args.get("po_number"))

            elif func_name == "search_suppliers":
                return self.odoo.search_suppliers(query=args.get("query"))

            elif func_name == "get_supplier_info":
                return self.odoo.get_supplier_info(args.get("supplier_name"))

            elif func_name == "search_customers":
                return self.odoo.search_customers(args.get("query"))

            elif func_name == "get_customer_info":
                return self.odoo.get_customer_info(
                    customer_email=args.get("customer_email")
                )

            elif func_name == "create_quote_request":
                return self.odoo.create_quote_request(
                    customer_name=args.get("customer_name"),
                    customer_email=args.get("customer_email"),
                    customer_phone=args.get("customer_phone", ""),
                    products=args.get("products", []),
                    notes=args.get("notes", "")
                )

            elif func_name == "get_product_categories":
                return self.odoo.get_product_categories()

            elif func_name == "create_support_ticket":
                return self.odoo.create_support_ticket(
                    subject=args.get("subject"),
                    description=args.get("description"),
                    customer_email=args.get("customer_email", ""),
                    priority=args.get("priority", "1")
                )

            elif func_name == "end_call":
                return {"end_call": True, "reason": args.get("reason", "User ended conversation")}

            else:
                return {"error": f"Unknown function: {func_name}"}

        except Exception as e:
            logger.error(f"Error executing function {func_name}: {e}")
            return {"error": str(e)}

    def _generate_response_from_result(
        self,
        func_name: str,
        func_args: dict,
        result: any,
        messages: list
    ) -> str:
        """Generate a natural language response from function result"""

        # Add function result to messages
        messages.append({
            "role": "assistant",
            "content": None,
            "tool_calls": [{
                "id": "call_1",
                "type": "function",
                "function": {
                    "name": func_name,
                    "arguments": json.dumps(func_args)
                }
            }]
        })

        messages.append({
            "role": "tool",
            "tool_call_id": "call_1",
            "content": json.dumps(result, default=str)
        })

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages
            )

            return response.choices[0].message.content

        except Exception as e:
            logger.error(f"Error generating response from result: {e}")

            # Fallback: format the result directly
            if isinstance(result, list):
                if not result:
                    return "No results found."
                return f"I found {len(result)} results. Here's what I found:\n" + \
                       "\n".join([f"- {item.get('name', item)}" for item in result[:5]])
            elif isinstance(result, dict):
                if result.get("error"):
                    return f"I encountered an issue: {result['error']}"
                if result.get("success") == False:
                    return f"The operation was not successful: {result.get('message', 'Unknown error')}"
                return f"Here's what I found: {json.dumps(result, indent=2, default=str)}"
            else:
                return str(result)


class ThreeLinesWebClient:
    """
    Web/Chat client for Three Lines Operations Agent
    Used for web dashboard and API endpoints (non-voice)
    """

    def __init__(self):
        # Use custom API endpoint (AI3Lines or OpenAI-compatible)
        self.client = OpenAI(
            api_key=os.getenv("OPENAI_API_KEY"),
            base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
        )
        self.model = os.getenv("OPENAI_MODEL", "gpt-4-turbo-preview")
        self.odoo = OdooClient()
        self.system_prompt = f"{THREE_LINES_SYSTEM_PROMPT}\n\n{THREE_LINES_FUNCTION_CALLING_PROMPT}"

    async def chat(self, message: str, conversation_history: list = None) -> dict:
        """
        Process a chat message and return response

        Args:
            message: User's message
            conversation_history: Previous messages in the conversation

        Returns:
            dict with 'response' and 'function_called' keys
        """
        messages = [{"role": "system", "content": self.system_prompt}]

        if conversation_history:
            messages.extend(conversation_history)

        messages.append({"role": "user", "content": message})

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=[{"type": "function", "function": f} for f in THREELINES_FUNCTIONS],
                tool_choice="auto"
            )

            assistant_message = response.choices[0].message

            # Check for function calls
            if assistant_message.tool_calls:
                results = []
                for tool_call in assistant_message.tool_calls:
                    func_name = tool_call.function.name
                    func_args = json.loads(tool_call.function.arguments)

                    # Execute function
                    llm_client = ThreeLinesLLMClient()
                    result = llm_client._execute_function(func_name, func_args)
                    results.append({
                        "function": func_name,
                        "args": func_args,
                        "result": result
                    })

                # Generate final response
                messages.append({
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments
                            }
                        }
                        for tc in assistant_message.tool_calls
                    ]
                })

                for i, tc in enumerate(assistant_message.tool_calls):
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": json.dumps(results[i]["result"], default=str)
                    })

                final_response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages
                )

                return {
                    "response": final_response.choices[0].message.content,
                    "functions_called": results
                }

            return {
                "response": assistant_message.content,
                "functions_called": []
            }

        except Exception as e:
            logger.error(f"Error in chat: {e}")
            return {
                "response": "I apologize, I encountered an error. Please try again.",
                "error": str(e)
            }
