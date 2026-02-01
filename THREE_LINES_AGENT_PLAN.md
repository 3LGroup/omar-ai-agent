# Three Lines Operations Agent - Project Plan

## Executive Summary

**Project Name:** Three Lines Operations Agent "Omar"
**Company:** Three Lines - Saudi Arabia's first GAMI-licensed supplier of aircraft spare parts, GSE, and simulators
**Purpose:** Internal AI-powered operations assistant to streamline business processes and information access

---

## 1. Project Vision

### What This Agent Does
Transform how Three Lines employees access company information and perform daily operations through an intelligent conversational AI assistant named "Omar".

### Core Concept
Instead of manually searching through:
- Odoo ERP for inventory, orders, suppliers
- Document folders for specs, manuals, SOPs
- Multiple systems for customer/supplier info

Employees simply **ask Omar**:
- "Do we have part ABC123 in stock?"
- "What's the status of order SO-4521?"
- "Who is our supplier for Boeing parts?"
- "Show me the technical specs for F-15 brakes"

---

## 2. Current State (What Exists)

### Original Project: Answerly
This codebase was originally built for **healthcare clinics** to handle:
- Patient appointment scheduling via phone calls
- Integration with medical practice management systems
- Voice-based AI conversations using Retell AI + Twilio
- Multi-tenant SaaS for multiple clinics

### What We've Transformed
✅ **Completed:**
1. Created Odoo ERP integration client
2. Built AI conversation handler for operations queries
3. Defined 13 core functions (search products, check orders, etc.)
4. Set up Omar's personality and prompts (English/Arabic)
5. Created REST API endpoints for operations
6. Configured custom AI endpoint (ai3lines.com)
7. Fixed import issues and made system modular

✅ **Working Features:**
- Odoo connection established (User ID: 141)
- Product search in inventory
- Order status tracking
- Supplier/customer lookup
- Real-time data access

---

## 3. Technology Architecture

### Current Tech Stack
```
┌─────────────────────────────────────────────────────────┐
│                   EMPLOYEE INTERFACE                    │
│            Web Chat | WhatsApp | Voice Calls            │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│                   OMAR (AI AGENT)                       │
│        Custom LLM (ai3lines.com/api/v1/openai)         │
│                 Function Calling                        │
└────────────────────────┬────────────────────────────────┘
                         │
          ┌──────────────┼──────────────┐
          │              │              │
          ▼              ▼              ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│  ODOO ERP    │  │  DOCUMENTS   │  │  SUPABASE    │
│              │  │  (Future)    │  │  (Planned)   │
│ • Inventory  │  │ • Specs      │  │ • User Auth  │
│ • Orders     │  │ • Manuals    │  │ • Logs       │
│ • Suppliers  │  │ • SOPs       │  │ • Analytics  │
│ • Customers  │  │ • Contracts  │  │              │
└──────────────┘  └──────────────┘  └──────────────┘
```

### Key Components
| Component | Technology | Purpose |
|-----------|------------|---------|
| Backend | FastAPI (Python) | API server |
| AI Model | Custom endpoint (localmodel) | Conversation AI |
| Database | Odoo ERP | Business data |
| Future DB | Supabase | User auth, logs, analytics |
| Voice (Optional) | Retell AI + Twilio | Phone calls |
| Deployment | Docker | Containerization |

---

## 4. Omar's Capabilities (Implemented)

### Function Categories

#### 📦 Inventory & Products
```
✅ search_products(query, part_number, category)
   Example: "Find all F-15 brake assemblies"

✅ check_stock_availability(part_number)
   Example: "Is part ABC-123 in stock?"

✅ get_product_categories()
   Example: "What types of products do we carry?"
```

#### 📋 Sales & Orders
```
✅ get_order_status(order_number)
   Example: "Status of order SO-4521?"

✅ get_customer_orders(customer_name, customer_email)
   Example: "Show all Boeing orders"

✅ create_quote_request(customer, products, notes)
   Example: "Create quote for Saudi Airlines for 10 units of X"
```

#### 🚚 Purchase Orders
```
✅ get_purchase_order_status(po_number)
   Example: "Where is PO-8921?"
```

#### 👥 Suppliers & Customers
```
✅ search_suppliers(query)
   Example: "Who supplies hydraulic pumps?"

✅ get_supplier_info(supplier_name)
   Example: "Contact info for Lockheed Martin"

✅ search_customers(query)
   Example: "Find customer Royal Saudi Air Force"

✅ get_customer_info(customer_email)
   Example: "Get details for contact@boeing.com"
```

#### 🎫 Support
```
✅ create_support_ticket(subject, description, priority)
   Example: "Create urgent ticket for missing shipment"
```

---

## 5. What Needs to Be Implemented

### Phase 1: Core Operations (High Priority)

#### 1.1 Supabase Integration
**Status:** 🔴 Not Started
**Purpose:** Replace Firebase with Supabase for user management, logs, and analytics

**Tasks:**
- [ ] Create Supabase project
- [ ] Design database schema (users, sessions, query_logs, feedback)
- [ ] Build Supabase client (`src/db/supabase.py`)
- [ ] Migrate existing Firebase operations
- [ ] Set up Row Level Security (RLS) policies

**Tables Needed:**
```sql
-- User authentication and profiles
users (id, email, full_name, role, department, created_at)

-- Track every query to Omar
query_logs (id, user_id, query, response, timestamp, function_called)

-- User feedback on responses
feedback (id, query_log_id, helpful, comments)

-- API usage tracking
api_usage (id, user_id, endpoint, timestamp, response_time)
```

#### 1.2 Document Search (RAG - Retrieval Augmented Generation)
**Status:** 🔴 Not Started
**Purpose:** Allow Omar to search and answer questions from company documents

**Tasks:**
- [ ] Set up vector database (Supabase pgvector or Pinecone)
- [ ] Create document upload system
- [ ] Implement PDF/DOCX text extraction
- [ ] Build embedding generation pipeline
- [ ] Create semantic search function
- [ ] Add `search_documents()` function to Omar

**Example Use Cases:**
```
User: "Show me the F-15 maintenance manual"
Omar: [Retrieves and displays relevant PDF sections]

User: "What are the export compliance requirements for Saudi Arabia?"
Omar: [Searches compliance documents and provides answer]
```

#### 1.3 Web Chat Interface
**Status:** 🔴 Not Started
**Purpose:** Simple web UI for employees to chat with Omar

**Tasks:**
- [ ] Create React/Vue frontend
- [ ] Design chat UI (inspired by ChatGPT)
- [ ] Implement WebSocket connection
- [ ] Add authentication (login page)
- [ ] Deploy on company domain

**Features:**
- Conversation history
- File upload (for quote requests)
- Export conversation as PDF
- Multi-language toggle (English/Arabic)

---

### Phase 2: Enhanced Features (Medium Priority)

#### 2.1 Arabic Language Support
**Status:** 🟡 Partially Done (prompts exist, not tested)

**Tasks:**
- [ ] Test Arabic conversations with local model
- [ ] Fine-tune Arabic responses
- [ ] Add right-to-left (RTL) UI support
- [ ] Create Arabic-specific prompts for aviation terms

#### 2.2 Advanced Analytics Dashboard
**Status:** 🔴 Not Started

**Purpose:** Admin dashboard to monitor Omar usage and insights

**Features:**
- Most asked questions
- Response accuracy metrics
- User satisfaction ratings
- API performance monitoring
- Cost tracking (AI API usage)

#### 2.3 WhatsApp Integration
**Status:** 🔴 Not Started
**Purpose:** Allow employees to query Omar via WhatsApp (for field staff)

**Tasks:**
- [ ] Set up WhatsApp Business API
- [ ] Create webhook handler
- [ ] Map WhatsApp messages to Omar functions
- [ ] Handle image/document uploads via WhatsApp

---

### Phase 3: Voice & Advanced (Low Priority)

#### 3.1 Voice Assistant (Phone Calls)
**Status:** 🟡 Infrastructure exists (Retell AI + Twilio already in codebase)

**Tasks:**
- [ ] Configure Retell AI for Three Lines
- [ ] Set up Saudi phone number via Twilio
- [ ] Test voice recognition in Arabic
- [ ] Create voice-specific prompts
- [ ] Handle background noise in warehouse/field

#### 3.2 Mobile App
**Status:** 🔴 Not Started

**Options:**
- Flutter app (iOS + Android)
- React Native
- Progressive Web App (PWA) - simpler, works on all devices

#### 3.3 Workflow Automation
**Status:** 🔴 Not Started

**Examples:**
```
User: "Notify me when PO-123 arrives"
Omar: [Sets up notification trigger in Supabase]

User: "Send weekly inventory report every Monday"
Omar: [Schedules automated report via cron job]
```

---

## 6. Database Migration Plan: Firebase → Supabase

### Why Supabase?
| Feature | Firebase | Supabase | Winner |
|---------|----------|----------|--------|
| **Database** | NoSQL (Firestore) | PostgreSQL (SQL) | **Supabase** - Better for relational data |
| **Cost** | Expensive at scale | Cheaper + open source | **Supabase** |
| **Queries** | Limited complex queries | Full SQL power | **Supabase** |
| **Self-hosted** | No | Yes | **Supabase** |
| **Real-time** | Yes | Yes | **Tie** |

### Migration Steps

#### Step 1: Set Up Supabase
```bash
# 1. Create Supabase project at supabase.com
# 2. Copy project URL and keys to .env
# 3. Install Supabase client
pip install supabase
```

#### Step 2: Create Schema
```sql
-- Users table
CREATE TABLE users (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  email TEXT UNIQUE NOT NULL,
  full_name TEXT,
  role TEXT CHECK (role IN ('admin', 'sales', 'warehouse', 'finance')),
  department TEXT,
  created_at TIMESTAMP DEFAULT NOW()
);

-- Query logs
CREATE TABLE query_logs (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  user_id UUID REFERENCES users(id),
  query TEXT NOT NULL,
  response TEXT,
  function_called TEXT,
  execution_time_ms INT,
  created_at TIMESTAMP DEFAULT NOW()
);

-- Enable Row Level Security
ALTER TABLE query_logs ENABLE ROW LEVEL SECURITY;
```

#### Step 3: Build Supabase Client
Create `src/db/supabase_client.py`:
```python
from supabase import create_client, Client

class SupabaseClient:
    def __init__(self):
        self.client = create_client(
            os.getenv("SUPABASE_URL"),
            os.getenv("SUPABASE_KEY")
        )

    def log_query(self, user_id, query, response):
        return self.client.table("query_logs").insert({
            "user_id": user_id,
            "query": query,
            "response": response
        }).execute()
```

#### Step 4: Replace Firebase Calls
Instead of:
```python
from src.db.db import DB
db = DB()  # Firebase
```

Use:
```python
from src.db.supabase_client import SupabaseClient
db = SupabaseClient()  # Supabase
```

---

## 7. Deployment Roadmap

### Immediate (This Week)
- [ ] Get Supabase credentials from you
- [ ] Create Supabase database schema
- [ ] Build Supabase client
- [ ] Test basic queries

### Short-term (Next 2 Weeks)
- [ ] Build simple web chat interface
- [ ] Deploy to company server/cloud
- [ ] Add user authentication
- [ ] Train 5-10 employees on using Omar

### Medium-term (1-2 Months)
- [ ] Add document search (RAG)
- [ ] Implement WhatsApp integration
- [ ] Build analytics dashboard
- [ ] Expand to all departments

### Long-term (3-6 Months)
- [ ] Voice assistant for warehouse
- [ ] Mobile app
- [ ] Workflow automation
- [ ] Integration with other systems (accounting, logistics)

---

## 8. Success Metrics

### How We Measure Success

| Metric | Target | How to Track |
|--------|--------|--------------|
| **Daily Active Users** | 20+ employees | Supabase query_logs |
| **Queries per Day** | 100+ queries | Count from query_logs |
| **Response Accuracy** | 90%+ helpful | User feedback ratings |
| **Time Saved** | 2 hours/employee/week | User surveys |
| **Odoo API Calls Reduced** | 50% less manual Odoo logins | Monitor Odoo access logs |

---

## 9. Security & Compliance

### Data Protection
- [ ] Encrypt sensitive data in Supabase
- [ ] Implement role-based access control (RBAC)
- [ ] Audit logs for all queries
- [ ] Regular security reviews

### Compliance
- [ ] GAMI compliance for defense data
- [ ] ISO 9001 alignment
- [ ] Data residency (keep data in Saudi Arabia if required)

---

## 10. Cost Estimate

### Monthly Operational Costs

| Item | Cost (USD) | Notes |
|------|------------|-------|
| **Supabase** | $25-75 | Based on usage |
| **AI API (ai3lines.com)** | Your internal cost | Already have |
| **Odoo** | Already have | Existing license |
| **Twilio** (optional voice) | $50-100 | Only if voice enabled |
| **Server Hosting** | $20-50 | DigitalOcean/AWS |
| **Total** | ~$100-200/month | For 30-50 employees |

---

## 11. Next Steps

### What You Need to Provide

1. **Supabase Credentials** (Priority 1)
   - Go to [supabase.com](https://supabase.com)
   - Create new project
   - Share: Project URL, anon key, service key

2. **Sample Documents** (Priority 2)
   - 5-10 PDF files (specs, manuals, SOPs)
   - To test document search feature

3. **User List** (Priority 3)
   - Emails of employees who will use Omar
   - Their roles/departments

### What I'll Build Next

**Option A: Supabase Setup** (Recommended)
- Create database schema
- Build Supabase client
- Replace Firebase
- Set up user authentication

**Option B: Web Chat UI**
- Simple React chat interface
- Test Omar with real employees
- Gather feedback

**Option C: Document Search (RAG)**
- Upload documents
- Enable "Ask about documents" feature
- Most impressive demo feature

**Which would you like me to start with?**

---

## 12. Vision: 6 Months from Now

Imagine your company in 6 months:

✅ **Every employee uses Omar daily**
✅ **No more searching through Odoo manually**
✅ **Warehouse staff ask via WhatsApp: "How many units of X left?"**
✅ **Sales team: "Create quote for customer Y for 20 units of Z"**
✅ **Technical team: "Show me the maintenance specs for F-15"**
✅ **Finance: "What's the status of all pending POs?"**
✅ **Management dashboard shows Omar saved 50+ hours/week company-wide**

**Omar becomes the central nervous system of Three Lines operations.**

---

## Contact & Questions

**Project Lead:** Abdul Rafay (abdulrafay@3lines.com.sa)
**Agent Name:** Omar
**Company:** Three Lines
**Status:** Phase 1 - Core Implementation
**Last Updated:** January 26, 2026

---

**Ready to proceed? Let's start with Supabase setup - just share the credentials and we'll build the foundation!**
