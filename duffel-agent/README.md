# Duffel Flight Booking Agents 🛫

AI-powered flight booking agents with payment integration, built on the Fetch.ai uAgents framework.

## Overview

This repository contains two production-ready flight booking agents:

1. **`duffel-lg-agent/`** - LangGraph-based agent with comprehensive features
2. **`duffel-flights-agent/`** - OpenAI-powered agent with streamlined booking flow

Both agents provide end-to-end flight booking capabilities with natural language interaction, payment processing (FET & Skyfire USDC), and email notifications.

---

## 🌟 Features

### Core Capabilities
- ✈️ **Flight Search** - Search flights with pagination and filtering
- 💺 **Offer Management** - Select, refresh, and compare flight offers
- 👤 **Passenger Collection** - Smart extraction of passenger details
- 💳 **Multi-Payment Support** - FET Direct & Skyfire USDC payments
- 📧 **Email Notifications** - Beautiful HTML emails for bookings & cancellations
- 🔄 **Order Management** - List bookings and process cancellations
- 🤖 **Natural Language** - Conversational interface powered by OpenAI GPT

### Technical Features
- 🔐 **Payment Verification** - Blockchain transaction verification
- 💾 **Session Persistence** - SQLite-based state management
- 🌐 **Agentverse Integration** - Mailbox protocol support
- 🐳 **Docker Ready** - Complete containerization
- 📊 **Logging & Monitoring** - Comprehensive logging system
- ⚡ **Async Architecture** - High-performance async/await patterns

---

## 📁 Project Structure

```
duffel-final/
├── duffel-lg-agent/              # LangGraph-based agent (Port 8030)
│   ├── src/
│   │   ├── graph.py              # LangGraph workflow definition
│   │   └── duffel_tools.py       # Duffel API tools
│   ├── protocols/
│   │   ├── chat_proto.py         # Chat protocol handler
│   │   └── payment_proto.py      # Payment protocol handler
│   ├── agent.py                  # Main agent entry point
│   ├── Dockerfile
│   └── docker-compose.yml
│
├── duffel-flights-agent/         # OpenAI-powered agent (Port 8044)
│   └── duffel-agent/
│       ├── tools/
│       │   ├── openai_client.py  # OpenAI LLM integration
│       │   ├── duffel_tools.py   # Duffel API tools
│       │   ├── skyfire.py        # Skyfire payment verification
│       │   └── fet_payments.py   # FET payment verification
│       ├── protocols/
│       │   ├── chat_proto.py     # Chat protocol handler
│       │   └── payment_proto.py  # Payment protocol handler
│       ├── schemas/
│       │   └── schemas.py        # Protocol schemas
│       ├── agent.py              # Main agent entry point
│       ├── Dockerfile
│       └── docker-compose.yml
│
└── README.md                     # This file
```

---

## 🚀 Quick Start

### Prerequisites

- **Python 3.11+**
- **Docker & Docker Compose** (optional)
- **API Keys:**
  - OpenAI API key
  - Duffel API token (test mode)
  - Agentverse mailbox key
  - FreeCurrencyAPI key
  - Skyfire credentials (optional)
  - SMTP credentials (optional, for emails)

### Option 1: Docker (Recommended)

#### Start duffel-lg-agent (Port 8030):
```bash
cd duffel-lg-agent
cp env.example .env
# Edit .env with your credentials
docker-compose up -d --build
docker-compose logs -f
```

#### Start duffel-flights-agent (Port 8044):
```bash
cd duffel-flights-agent
cp duffel-agent/env.example duffel-agent/.env
# Edit .env with your credentials
docker-compose up -d --build
docker-compose logs -f
```

### Option 2: Local Development

#### Setup duffel-lg-agent:
```bash
cd duffel-lg-agent
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp env.example .env
# Edit .env with your credentials
python agent.py
```

#### Setup duffel-flights-agent:
```bash
cd duffel-flights-agent/duffel-agent
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp env.example .env
# Edit .env with your credentials
python agent.py
```

---

## 💬 Usage Examples

### 1. Search for Flights
```
User: "SFO to LAX on January 22, 2026 for 1 adult"
Agent: Shows 5 flight options with prices in USDC
```

### 2. Navigate Results
```
User: "next"        # Next page
User: "back"        # Previous page
User: "page 5"      # Jump to page 5
```

### 3. Select a Flight
```
User: "3"           # Select option 3
Agent: Shows flight details and asks for passenger info
```

### 4. Provide Passenger Details
```
User: "Mr. John Smith, 1990-05-15, male, john@example.com, +1234567890"
Agent: Validates and requests payment
```

### 5. Complete Payment
- Approve payment request in wallet (0.001 FET or 0.001 USDC for testing)
- Booking confirmed automatically
- Email receipt sent

### 6. Manage Orders
```
User: "my orders"                    # List all bookings
User: "cancel ord_xxxxx"             # Request cancellation
User: "confirm cancel ord_xxxxx"     # Confirm cancellation
```

---

## 🔧 Configuration

### Environment Variables

#### Required:
```env
# OpenAI
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini

# Duffel
DUFFEL_TOKEN=duffel_test_...

# Agentverse
AGENT_MAILBOX_KEY=...

# Currency
FREECURRENCYAPI_KEY=...
```

#### Optional (Skyfire Payments):
```env
SKYFIRE_ENV=production
SELLER_ACCOUNT_ID=...
SELLER_SERVICE_ID=...
SKYFIRE_API_KEY=...
```

#### Optional (Email Notifications):
```env
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASS=your-app-password
SMTP_FROM=your-email@gmail.com
SMTP_FROM_NAME=Flight Booking Team
```

### Port Configuration

- **duffel-lg-agent**: Port 8030
- **duffel-flights-agent**: Port 8044

To change ports, update:
1. `AGENT_PORT` in `.env`
2. Port mapping in `docker-compose.yml`

---

## 🎨 Email Templates

Both agents send beautiful HTML emails for:

### Booking Confirmation
- Purple gradient header with ✈️ emoji
- Booking details card with PNR, route, timing
- Payment method display
- "What's Next?" section with travel tips
- Mobile-responsive design

### Cancellation Confirmation
- Pink/red gradient header with 🔄 emoji
- Cancellation details with refund amount
- Refund timeline (5 working days)
- Support contact information

---

## 🔐 Payment Integration

### Supported Methods

1. **FET Direct**
   - Native FET token payments
   - Blockchain verification via Fetch.ai REST API
   - Test amount: 0.001 FET

2. **Skyfire USDC**
   - USDC payments via Skyfire network
   - JWT token verification
   - Test amount: 0.001 USDC

### Payment Flow

1. User completes passenger details
2. Agent sends `RequestPayment` message to wallet
3. User approves payment in wallet
4. Agent receives `CommitPayment` with transaction ID
5. Agent verifies transaction on blockchain
6. Booking created automatically
7. Confirmation email sent

---

## 📊 Architecture

### Agent Components

```
┌─────────────────────────────────────────┐
│           User (Chat Interface)          │
└─────────────────┬───────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────┐
│         Chat Protocol Handler            │
│  • Message routing                       │
│  • Session management                    │
│  • LLM integration                       │
└─────────────────┬───────────────────────┘
                  │
        ┌─────────┴─────────┐
        ▼                   ▼
┌──────────────┐    ┌──────────────┐
│ OpenAI LLM   │    │ Duffel API   │
│ • Intent     │    │ • Search     │
│ • Extraction │    │ • Booking    │
│ • Response   │    │ • Orders     │
└──────────────┘    └──────────────┘
        │                   │
        └─────────┬─────────┘
                  ▼
┌─────────────────────────────────────────┐
│       Payment Protocol Handler           │
│  • FET verification                      │
│  • Skyfire verification                  │
│  • Booking creation                      │
└─────────────────┬───────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────┐
│         Email Service (SMTP)             │
│  • Booking confirmations                 │
│  • Cancellation receipts                 │
└─────────────────────────────────────────┘
```

### Data Flow

1. **User Input** → Chat Protocol
2. **LLM Processing** → Intent & Slot Extraction
3. **Tool Execution** → Duffel API calls
4. **Payment Request** → Payment Protocol
5. **Verification** → Blockchain check
6. **Booking** → Duffel order creation
7. **Notification** → Email service

---

## 🧪 Testing

### Test Flight Search
```bash
# Using curl
curl -X POST http://localhost:8044 \
  -H "Content-Type: application/json" \
  -d '{"message": "SFO to LAX on Jan 22, 2026 for 1 adult"}'
```

### Test Payment (Testnet)
- Use Fetch.ai testnet tokens
- Test amount: 0.001 FET or 0.001 USDC
- No real money charged

### Duffel Test Mode
- Uses Duffel test API
- No real bookings created
- Safe for development

---

## 🐛 Troubleshooting

### Agent Won't Start

```bash
# Check logs
docker-compose logs -f

# Common issues:
# 1. Missing .env file → Copy from env.example
# 2. Invalid API keys → Verify credentials
# 3. Port conflict → Change port in docker-compose.yml
```

### Payment Verification Fails

```bash
# Check Skyfire configuration
# Ensure SELLER_ACCOUNT_ID and SELLER_SERVICE_ID match
# Verify SKYFIRE_ENV is correct (production/qa)
```

### Email Not Sending

```bash
# For Gmail:
# 1. Enable 2FA
# 2. Generate App Password
# 3. Use app password as SMTP_PASS
```

### Database Issues

```bash
# Reset database
docker-compose down
rm -rf duffel-agent/state/*.sqlite*
docker-compose up -d
```

---

## 📈 Performance

- **Response Time**: < 2s for flight searches
- **Concurrent Sessions**: Unlimited (session-isolated)
- **Database**: SQLite with WAL mode
- **Memory**: ~200MB per agent
- **CPU**: Minimal (async I/O bound)

---

## 🔒 Security

- ✅ Environment variables for secrets
- ✅ Payment verification on blockchain
- ✅ Session isolation
- ✅ Input validation
- ✅ HTTPS for external APIs
- ✅ JWT verification for Skyfire

---

## 🤝 Contributing

Contributions welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

---

## 📝 License

MIT License - See LICENSE file for details

---

## 🙏 Acknowledgments

- **Fetch.ai** - uAgents framework
- **Duffel** - Flight booking API
- **OpenAI** - GPT models
- **Skyfire** - USDC payment infrastructure

---

## 📞 Support

For issues or questions:
- Check logs: `docker-compose logs -f`
- Review environment variables
- Verify API keys are valid
- Check Duffel API status

---

## 🗺️ Roadmap

- [ ] Multi-city flights support
- [ ] Seat selection
- [ ] Baggage add-ons
- [ ] Hotel bookings
- [ ] Car rentals
- [ ] Trip recommendations
- [ ] Price alerts
- [ ] Loyalty program integration

---

**Built with ❤️ using Fetch.ai uAgents**

