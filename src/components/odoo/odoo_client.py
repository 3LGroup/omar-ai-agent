"""
Odoo Client for Three Lines Operations Agent
Handles all Odoo ERP API interactions for inventory, sales, and operations
"""

import xmlrpc.client
import os
from typing import Optional, Dict, List, Any
from src.logger import logger


class OdooClient:
    """Client for interacting with Odoo ERP system"""

    def __init__(
        self,
        url: str = None,
        db: str = None,
        username: str = None,
        api_key: str = None
    ):
        self.url = url or os.getenv("ODOO_URL", "https://three-lines-stage5-27653523.dev.odoo.com")
        self.db = db or os.getenv("ODOO_DB", "three-lines-stage5-27653523")
        self.username = username or os.getenv("ODOO_USERNAME", "abdulrafay@3lines.com.sa")
        self.api_key = api_key or os.getenv("ODOO_API_KEY", "1c694ec83d509cb5488df484a1fbc16e78c8dfc8")

        self.common = None
        self.models = None
        self.uid = None
        self._connect()

    def _connect(self):
        """Establish connection to Odoo"""
        try:
            self.common = xmlrpc.client.ServerProxy(f'{self.url}/xmlrpc/2/common')
            self.models = xmlrpc.client.ServerProxy(f'{self.url}/xmlrpc/2/object')

            # Authenticate
            self.uid = self.common.authenticate(
                self.db,
                self.username,
                self.api_key,
                {}
            )

            if self.uid:
                logger.info(f"Connected to Odoo as user ID: {self.uid}")
            else:
                logger.error("Failed to authenticate with Odoo")

        except Exception as e:
            logger.error(f"Error connecting to Odoo: {e}")
            raise

    def _execute(self, model: str, method: str, *args, **kwargs) -> Any:
        """Execute an Odoo model method"""
        try:
            return self.models.execute_kw(
                self.db,
                self.uid,
                self.api_key,
                model,
                method,
                args,
                kwargs
            )
        except Exception as e:
            logger.error(f"Error executing {model}.{method}: {e}")
            raise

    # ============== INVENTORY / PRODUCTS ==============

    def search_products(
        self,
        query: str = None,
        part_number: str = None,
        category: str = None,
        limit: int = 10
    ) -> List[Dict]:
        """
        Search for products/parts in inventory

        Args:
            query: General search term
            part_number: Specific part number
            category: Product category filter
            limit: Max results to return
        """
        domain = []

        if query:
            domain.append('|')
            domain.append('|')
            domain.append(('name', 'ilike', query))
            domain.append(('default_code', 'ilike', query))
            domain.append(('description', 'ilike', query))

        if part_number:
            domain.append(('default_code', '=', part_number))

        if category:
            domain.append(('categ_id.name', 'ilike', category))

        products = self._execute(
            'product.product',
            'search_read',
            domain,
            fields=['id', 'name', 'default_code', 'qty_available', 'list_price',
                   'categ_id', 'description', 'image_1920'],
            limit=limit
        )

        return products

    def get_product_by_part_number(self, part_number: str) -> Optional[Dict]:
        """Get a specific product by part number"""
        products = self._execute(
            'product.product',
            'search_read',
            [('default_code', '=', part_number)],
            fields=['id', 'name', 'default_code', 'qty_available', 'list_price',
                   'categ_id', 'description', 'standard_price', 'weight', 'volume'],
            limit=1
        )
        return products[0] if products else None

    def check_stock_availability(self, product_id: int = None, part_number: str = None) -> Dict:
        """Check stock availability for a product"""
        if part_number:
            product = self.get_product_by_part_number(part_number)
            if not product:
                return {"available": False, "message": f"Part {part_number} not found"}
            product_id = product['id']

        quants = self._execute(
            'stock.quant',
            'search_read',
            [('product_id', '=', product_id)],
            fields=['product_id', 'quantity', 'reserved_quantity', 'location_id']
        )

        total_qty = sum(q['quantity'] - q['reserved_quantity'] for q in quants)

        return {
            "product_id": product_id,
            "available_quantity": total_qty,
            "available": total_qty > 0,
            "locations": quants
        }

    # ============== SALES / ORDERS ==============

    def get_order_status(self, order_number: str) -> Optional[Dict]:
        """Get status of a sales order"""
        orders = self._execute(
            'sale.order',
            'search_read',
            [('name', 'ilike', order_number)],
            fields=['id', 'name', 'state', 'partner_id', 'date_order',
                   'amount_total', 'invoice_status', 'delivery_status'],
            limit=1
        )

        if not orders:
            return None

        order = orders[0]

        # Get order lines
        order_lines = self._execute(
            'sale.order.line',
            'search_read',
            [('order_id', '=', order['id'])],
            fields=['product_id', 'product_uom_qty', 'price_unit', 'price_subtotal']
        )

        order['lines'] = order_lines

        # Get delivery info if exists
        pickings = self._execute(
            'stock.picking',
            'search_read',
            [('sale_id', '=', order['id'])],
            fields=['name', 'state', 'scheduled_date', 'carrier_tracking_ref']
        )

        order['deliveries'] = pickings

        return order

    def get_customer_orders(self, customer_name: str = None, customer_email: str = None) -> List[Dict]:
        """Get all orders for a customer"""
        # First find the customer
        domain = []
        if customer_name:
            domain.append(('name', 'ilike', customer_name))
        if customer_email:
            domain.append(('email', '=', customer_email))

        partners = self._execute(
            'res.partner',
            'search_read',
            domain,
            fields=['id', 'name', 'email'],
            limit=5
        )

        if not partners:
            return []

        partner_ids = [p['id'] for p in partners]

        orders = self._execute(
            'sale.order',
            'search_read',
            [('partner_id', 'in', partner_ids)],
            fields=['name', 'state', 'date_order', 'amount_total', 'invoice_status'],
            order='date_order desc',
            limit=20
        )

        return orders

    def create_quote_request(
        self,
        customer_name: str,
        customer_email: str,
        customer_phone: str,
        products: List[Dict],
        notes: str = ""
    ) -> Dict:
        """
        Create a new quotation/RFQ

        Args:
            customer_name: Customer's name
            customer_email: Customer's email
            customer_phone: Customer's phone
            products: List of {part_number, quantity} dicts
            notes: Additional notes
        """
        # Find or create customer
        partners = self._execute(
            'res.partner',
            'search_read',
            [('email', '=', customer_email)],
            fields=['id'],
            limit=1
        )

        if partners:
            partner_id = partners[0]['id']
        else:
            partner_id = self._execute(
                'res.partner',
                'create',
                [{
                    'name': customer_name,
                    'email': customer_email,
                    'phone': customer_phone,
                    'customer_rank': 1
                }]
            )

        # Create quotation
        order_lines = []
        for item in products:
            product = self.get_product_by_part_number(item.get('part_number'))
            if product:
                order_lines.append((0, 0, {
                    'product_id': product['id'],
                    'product_uom_qty': item.get('quantity', 1),
                }))

        if not order_lines:
            return {"success": False, "message": "No valid products found"}

        order_id = self._execute(
            'sale.order',
            'create',
            [{
                'partner_id': partner_id,
                'order_line': order_lines,
                'note': notes,
                'state': 'draft'
            }]
        )

        # Get the created order
        order = self._execute(
            'sale.order',
            'search_read',
            [('id', '=', order_id)],
            fields=['name', 'amount_total'],
            limit=1
        )

        return {
            "success": True,
            "order_id": order_id,
            "order_number": order[0]['name'] if order else None,
            "message": f"Quote request created successfully"
        }

    # ============== SUPPLIERS / VENDORS ==============

    def search_suppliers(self, query: str = None, product_category: str = None) -> List[Dict]:
        """Search for suppliers"""
        domain = [('supplier_rank', '>', 0)]

        if query:
            domain.append('|')
            domain.append(('name', 'ilike', query))
            domain.append(('email', 'ilike', query))

        suppliers = self._execute(
            'res.partner',
            'search_read',
            domain,
            fields=['id', 'name', 'email', 'phone', 'city', 'country_id'],
            limit=10
        )

        return suppliers

    def get_supplier_info(self, supplier_name: str) -> Optional[Dict]:
        """Get detailed supplier information"""
        suppliers = self._execute(
            'res.partner',
            'search_read',
            [('name', 'ilike', supplier_name), ('supplier_rank', '>', 0)],
            fields=['id', 'name', 'email', 'phone', 'mobile', 'street',
                   'city', 'country_id', 'website', 'comment'],
            limit=1
        )

        return suppliers[0] if suppliers else None

    # ============== PURCHASE ORDERS ==============

    def get_purchase_order_status(self, po_number: str) -> Optional[Dict]:
        """Get status of a purchase order"""
        orders = self._execute(
            'purchase.order',
            'search_read',
            [('name', 'ilike', po_number)],
            fields=['id', 'name', 'state', 'partner_id', 'date_order',
                   'amount_total', 'date_planned', 'receipt_status'],
            limit=1
        )

        if not orders:
            return None

        order = orders[0]

        # Get order lines
        order_lines = self._execute(
            'purchase.order.line',
            'search_read',
            [('order_id', '=', order['id'])],
            fields=['product_id', 'product_qty', 'qty_received', 'price_unit']
        )

        order['lines'] = order_lines

        return order

    # ============== CUSTOMERS ==============

    def search_customers(self, query: str) -> List[Dict]:
        """Search for customers"""
        customers = self._execute(
            'res.partner',
            'search_read',
            [
                ('customer_rank', '>', 0),
                '|', '|',
                ('name', 'ilike', query),
                ('email', 'ilike', query),
                ('phone', 'ilike', query)
            ],
            fields=['id', 'name', 'email', 'phone', 'city', 'country_id'],
            limit=10
        )

        return customers

    def get_customer_info(self, customer_id: int = None, customer_email: str = None) -> Optional[Dict]:
        """Get detailed customer information"""
        domain = []
        if customer_id:
            domain.append(('id', '=', customer_id))
        elif customer_email:
            domain.append(('email', '=', customer_email))
        else:
            return None

        customers = self._execute(
            'res.partner',
            'search_read',
            domain,
            fields=['id', 'name', 'email', 'phone', 'mobile', 'street',
                   'city', 'country_id', 'credit_limit', 'total_invoiced'],
            limit=1
        )

        return customers[0] if customers else None

    # ============== CATEGORIES ==============

    def get_product_categories(self) -> List[Dict]:
        """Get all product categories"""
        categories = self._execute(
            'product.category',
            'search_read',
            [],
            fields=['id', 'name', 'parent_id', 'complete_name']
        )

        return categories

    # ============== HELPDESK (if module installed) ==============

    def create_support_ticket(
        self,
        subject: str,
        description: str,
        customer_email: str,
        priority: str = "1"
    ) -> Dict:
        """Create a support/helpdesk ticket"""
        try:
            # Find customer
            partners = self._execute(
                'res.partner',
                'search_read',
                [('email', '=', customer_email)],
                fields=['id'],
                limit=1
            )

            partner_id = partners[0]['id'] if partners else False

            ticket_id = self._execute(
                'helpdesk.ticket',
                'create',
                [{
                    'name': subject,
                    'description': description,
                    'partner_id': partner_id,
                    'priority': priority
                }]
            )

            return {
                "success": True,
                "ticket_id": ticket_id,
                "message": "Support ticket created successfully"
            }
        except Exception as e:
            logger.error(f"Error creating support ticket: {e}")
            return {
                "success": False,
                "message": "Helpdesk module may not be installed"
            }

    # ============== DOCUMENTS (if module installed) ==============

    def search_documents(self, query: str) -> List[Dict]:
        """Search for documents in Odoo Documents module"""
        try:
            documents = self._execute(
                'documents.document',
                'search_read',
                [('name', 'ilike', query)],
                fields=['id', 'name', 'mimetype', 'create_date', 'folder_id'],
                limit=10
            )
            return documents
        except Exception as e:
            logger.warning(f"Documents module may not be installed: {e}")
            return []

    # ============== UTILITY METHODS ==============

    def test_connection(self) -> Dict:
        """Test the Odoo connection"""
        try:
            version = self.common.version()
            return {
                "connected": True,
                "version": version,
                "user_id": self.uid,
                "database": self.db
            }
        except Exception as e:
            return {
                "connected": False,
                "error": str(e)
            }
