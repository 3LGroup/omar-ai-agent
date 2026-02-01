"""
Function call schemas for Three Lines Operations Agent
OpenAI Function Calling format
"""

THREELINES_FUNCTIONS = [
    {
        "name": "search_products",
        "description": "Search for aircraft parts, GSE equipment, or simulator components in inventory. Use this when the user asks about products, parts, or wants to find something in inventory.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "General search term for product name or description"
                },
                "part_number": {
                    "type": "string",
                    "description": "Specific part number to search for"
                },
                "category": {
                    "type": "string",
                    "description": "Product category filter (e.g., 'Aircraft Parts', 'GSE', 'Simulators')"
                }
            }
        }
    },
    {
        "name": "check_stock_availability",
        "description": "Check if a specific part is available in stock and get quantity information. Use this when user asks about availability or stock levels.",
        "parameters": {
            "type": "object",
            "properties": {
                "part_number": {
                    "type": "string",
                    "description": "The part number to check availability for"
                }
            },
            "required": ["part_number"]
        }
    },
    {
        "name": "get_order_status",
        "description": "Get the status of a sales order including delivery information. Use this when user asks about order status, tracking, or delivery.",
        "parameters": {
            "type": "object",
            "properties": {
                "order_number": {
                    "type": "string",
                    "description": "The sales order number (e.g., SO001, S00123)"
                }
            },
            "required": ["order_number"]
        }
    },
    {
        "name": "get_customer_orders",
        "description": "Get all orders for a specific customer. Use this when user asks about a customer's order history.",
        "parameters": {
            "type": "object",
            "properties": {
                "customer_name": {
                    "type": "string",
                    "description": "Customer's company or contact name"
                },
                "customer_email": {
                    "type": "string",
                    "description": "Customer's email address"
                }
            }
        }
    },
    {
        "name": "get_purchase_order_status",
        "description": "Get the status of a purchase order from suppliers. Use this when user asks about PO status or incoming shipments.",
        "parameters": {
            "type": "object",
            "properties": {
                "po_number": {
                    "type": "string",
                    "description": "The purchase order number (e.g., PO001, P00123)"
                }
            },
            "required": ["po_number"]
        }
    },
    {
        "name": "search_suppliers",
        "description": "Search for suppliers/vendors. Use this when user asks about suppliers or where to source parts.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search term for supplier name"
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "get_supplier_info",
        "description": "Get detailed information about a specific supplier including contact details.",
        "parameters": {
            "type": "object",
            "properties": {
                "supplier_name": {
                    "type": "string",
                    "description": "The supplier's company name"
                }
            },
            "required": ["supplier_name"]
        }
    },
    {
        "name": "search_customers",
        "description": "Search for customers by name, email, or phone. Use this when user asks about customer information.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search term for customer name, email, or phone"
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "get_customer_info",
        "description": "Get detailed information about a specific customer.",
        "parameters": {
            "type": "object",
            "properties": {
                "customer_email": {
                    "type": "string",
                    "description": "Customer's email address"
                }
            },
            "required": ["customer_email"]
        }
    },
    {
        "name": "create_quote_request",
        "description": "Create a new quotation/RFQ for a customer. Use this when user wants to create a quote.",
        "parameters": {
            "type": "object",
            "properties": {
                "customer_name": {
                    "type": "string",
                    "description": "Customer's name or company name"
                },
                "customer_email": {
                    "type": "string",
                    "description": "Customer's email address"
                },
                "customer_phone": {
                    "type": "string",
                    "description": "Customer's phone number"
                },
                "products": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "part_number": {"type": "string"},
                            "quantity": {"type": "integer"}
                        }
                    },
                    "description": "List of products with part numbers and quantities"
                },
                "notes": {
                    "type": "string",
                    "description": "Additional notes for the quotation"
                }
            },
            "required": ["customer_name", "customer_email", "products"]
        }
    },
    {
        "name": "get_product_categories",
        "description": "Get list of all product categories. Use this when user asks what types of products are available.",
        "parameters": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "create_support_ticket",
        "description": "Create a support or helpdesk ticket for issues that need follow-up.",
        "parameters": {
            "type": "object",
            "properties": {
                "subject": {
                    "type": "string",
                    "description": "Brief subject/title for the ticket"
                },
                "description": {
                    "type": "string",
                    "description": "Detailed description of the issue"
                },
                "customer_email": {
                    "type": "string",
                    "description": "Email of the person reporting the issue"
                },
                "priority": {
                    "type": "string",
                    "enum": ["0", "1", "2", "3"],
                    "description": "Priority level: 0=Low, 1=Medium, 2=High, 3=Urgent"
                }
            },
            "required": ["subject", "description"]
        }
    },
    {
        "name": "end_call",
        "description": "End the conversation when the user is done or says goodbye.",
        "parameters": {
            "type": "object",
            "properties": {
                "reason": {
                    "type": "string",
                    "description": "Reason for ending the call"
                }
            }
        }
    }
]
