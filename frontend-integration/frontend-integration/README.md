# UAgent Chat Application

A modern Next.js chat application that interfaces with UAgent AI, styled similar to ChatGPT.

## Features

- 🎨 Modern, responsive UI with dark mode support
- 💬 Real-time chat interface
- 🤖 Integration with UAgent AI
- ⚡ Built with Next.js 14 and TypeScript
- 🎯 Tailwind CSS for styling

## Getting Started

### Installation

```bash
npm install
```

### Running the Development Server

```bash
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) in your browser to see the application.

### Building for Production

```bash
npm run build
npm start
```

## UAgent Configuration

The application is configured to query the UAgent with address:
```
agent1q2g97humd4d6mgmcg783s2dsncu8hn37r3sgglu6eqa6es07wk3xqlmmy4v
```

To change the agent address, modify the `UAGENT_ADDRESS` constant in `app/api/chat/route.ts`.

## Project Structure

```
uagent-chat-app/
├── app/
│   ├── api/
│   │   └── chat/
│   │       └── route.ts       # API endpoint for UAgent queries
│   ├── globals.css            # Global styles
│   ├── layout.tsx             # Root layout
│   └── page.tsx               # Main chat interface
├── package.json
├── tsconfig.json
├── tailwind.config.ts
└── README.md
```

## Technologies Used

- **Next.js 14**: React framework with App Router
- **TypeScript**: Type-safe development
- **Tailwind CSS**: Utility-first CSS framework
- **uagent-client**: UAgent SDK for querying agents

## Usage

1. Type your message in the input field at the bottom
2. Press Enter or click the send button
3. The UAgent will process your query and respond
4. Continue the conversation naturally




# uAgent Client

Talk to any Fetch.ai uAgent from your Node.js or web application. Simple, fast, and easy to use.

[![npm version](https://img.shields.io/npm/v/uagent-client.svg)](https://www.npmjs.com/package/uagent-client)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## What is this?

A simple client that lets you chat with Fetch.ai uAgents (AI agents on the blockchain) from your JavaScript/TypeScript code.

### Why use uAgent Client?

- ✅ **Easy Integration** - Works with any Node.js or web app
- ✅ **TypeScript Ready** - Full type support out of the box
- ✅ **Auto Bridge** - Automatically handles the bridge agent for you
- ✅ **Simple API** - Just query and get responses
- ✅ **No Setup** - Zero configuration needed
- ✅ **Production Ready** - Used in real applications

## Quick Start

### Install

```bash
npm install uagent-client
```

### Use it

```javascript
const UAgentClient = require('uagent-client');

// Create client
const client = new UAgentClient();

// Ask a question
const result = await client.query(
    'agent1q2g97humd4d6mgmcg783s2dsncu8hn37r3sgglu6eqa6es07wk3xqlmmy4v',
    'Search for pizza restaurants in New York'
);

if (result.success) {
    console.log(result.response);
} else {
    console.error(result.error);
}
```

That's it! 🎉

## How to Use

### Basic Query

```javascript
const UAgentClient = require('uagent-client');

async function main() {
    const client = new UAgentClient();
    
    const result = await client.query(
        'agent_address_here',
        'Your question here'
    );
    
    if (result.success) {
        console.log('Agent says:', result.response);
    } else {
        console.log('Error:', result.error);
    }
}

main();
```

### Simple Method (Returns String)

```javascript
const client = new UAgentClient();

try {
    const response = await client.ask('agent_address', 'Your question');
    console.log(response); // Just the response string
} catch (error) {
    console.error('Failed:', error.message);
}
```

### Configure Settings

```javascript
const client = new UAgentClient({
    timeout: 60000,         // Wait 60 seconds for response
    bridgeUrl: 'http://localhost:8000',  // Bridge server URL
    autoStartBridge: true   // Auto-start bridge (default: true)
});
```

## Build a Web App (Next.js)

Want to build a chat interface? Here's how:

### 1. Backend API (`app/api/chat/route.ts`)

```typescript
import { NextRequest, NextResponse } from 'next/server';
import UAgentClient from 'uagent-client';

const client = new UAgentClient();

export async function POST(req: NextRequest) {
    const { agentAddress, query } = await req.json();
    
    const result = await client.query(agentAddress, query);
    
    return NextResponse.json(result);
}
```

### 2. Frontend Component (`app/page.tsx`)

```typescript
'use client';

import { useState } from 'react';

export default function Chat() {
    const [messages, setMessages] = useState([]);
    const [input, setInput] = useState('');
    const [loading, setLoading] = useState(false);

    const handleSubmit = async (e) => {
        e.preventDefault();
        if (!input.trim() || loading) return;

        const userMessage = input.trim();
        setInput('');
        setMessages(prev => [...prev, { role: 'user', content: userMessage }]);
        setLoading(true);

        try {
            const res = await fetch('/api/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    agentAddress: 'your_agent_address',
                    query: userMessage
                })
            });
            
            const data = await res.json();
            
            setMessages(prev => [...prev, { 
                role: 'agent', 
                content: data.success ? data.response : 'Error: ' + data.error
            }]);
        } catch (error) {
            setMessages(prev => [...prev, { 
                role: 'agent', 
                content: 'Failed to get response' 
            }]);
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="flex flex-col h-screen max-w-4xl mx-auto p-4">
            <h1 className="text-2xl font-bold mb-4">Chat with uAgent</h1>
            
            <div className="flex-1 overflow-y-auto space-y-4 mb-4">
                {messages.map((msg, i) => (
                    <div key={i} className={`p-4 rounded-lg ${
                        msg.role === 'user' ? 'bg-blue-100 ml-auto' : 'bg-gray-100'
                    }`}>
                        <p className="font-semibold mb-1">{msg.role === 'user' ? 'You' : 'Agent'}</p>
                        <p>{msg.content}</p>
                    </div>
                ))}
                {loading && <div className="text-gray-500">Agent is thinking...</div>}
            </div>

            <form onSubmit={handleSubmit} className="flex gap-2">
                <input
                    type="text"
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    placeholder="Type your message..."
                    className="flex-1 p-3 border rounded-lg"
                    disabled={loading}
                />
                <button type="submit" disabled={loading || !input.trim()}
                    className="px-6 py-3 bg-blue-500 text-white rounded-lg hover:bg-blue-600 disabled:opacity-50">
                    Send
                </button>
            </form>
        </div>
    );
}
```

### 3. Run

```bash
npm run dev
```

**See complete example**: [frontend-integration](https://github.com/gautammanak1/frontend-integration)

## API Reference

### Constructor

```javascript
new UAgentClient({
    timeout?: number,          // Default: 35000ms
    bridgeUrl?: string,         // Default: 'http://localhost:8000'
    autoStartBridge?: boolean   // Default: true
})
```

### Methods

#### `query(agentAddress, query, requestId?)`

Send a query to an agent.

**Returns:**
```javascript
{
    success: boolean,
    response?: string,   // Response if success
    error?: string,      // Error if failed
    requestId: string
}
```

#### `ask(agentAddress, query)`

Send a query and get only the response string. Throws error if fails.

**Returns:** `Promise<string>`

#### `ping()`

Check if client is ready.

**Returns:** `Promise<boolean>`

#### `stopBridge()`

Stop the client and cleanup.

## Common Use Cases

### Query Multiple Agents

```javascript
const client = new UAgentClient();

const results = await Promise.all([
    client.query(agent1, 'Question 1'),
    client.query(agent2, 'Question 2'),
    client.query(agent3, 'Question 3')
]);

results.forEach((result, i) => {
    if (result.success) {
        console.log(`Agent ${i + 1}:`, result.response);
    }
});
```

### Add Retry Logic

```javascript
async function queryWithRetry(client, address, query, maxRetries = 3) {
    for (let i = 0; i < maxRetries; i++) {
        const result = await client.query(address, query);
        if (result.success) return result;
        await new Promise(resolve => setTimeout(resolve, 1000));
    }
    throw new Error('Max retries exceeded');
}
```

### Express.js API

```javascript
const express = require('express');
const UAgentClient = require('uagent-client');

const app = express();
const client = new UAgentClient();

app.use(express.json());

app.post('/api/query', async (req, res) => {
    const { agentAddress, query } = req.body;
    const result = await client.query(agentAddress, query);
    res.json(result);
});

app.listen(3000);
```

## Important Notes

### Security ⚠️

**Never use uAgent Client directly in the browser!**

```javascript
// ❌ DON'T DO THIS IN BROWSER
import UAgentClient from 'uagent-client';

// ✅ DO THIS INSTEAD
// Create an API route and call it from browser
fetch('/api/chat', {
    method: 'POST',
    body: JSON.stringify({ query })
});
```

### Best Practices

1. ✅ Create **one client instance** per application
2. ✅ Reuse the client instance across requests
3. ✅ Set appropriate timeout for your use case
4. ✅ Handle errors gracefully
5. ✅ Validate inputs before sending
6. ❌ Don't create new client for each request

## Troubleshooting

### "Failed to start"

**Solution:** Install Python and uagents:

```bash
python3 --version  # Should be 3.8+
pip install uagents uagents-core
```

### "No response"

**Possible causes:**
- Agent is offline
- Wrong agent address
- Network issues
- Timeout too short

**Solution:** Increase timeout:

```javascript
const client = new UAgentClient({ timeout: 120000 });
```

### "Port already in use"

**Solution:** Only create one client instance, or use different port:

```javascript
const client = new UAgentClient({ 
    bridgeUrl: 'http://localhost:8001' 
});
```

## TypeScript Support

Full TypeScript types included:

```typescript
import UAgentClient, { QueryResponse } from 'uagent-client';

const client = new UAgentClient();

const result: QueryResponse = await client.query(
    agentAddress,
    query
);
```

## Examples

### Simple Chat Bot

```javascript
const UAgentClient = require('uagent-client');

const client = new UAgentClient();

async function chat(message) {
    const result = await client.query(
        'agent1q2g97humd4d6mgmcg783s2dsncu8hn37r3sgglu6eqa6es07wk3xqlmmy4v',
        message
    );
    
    return result.success ? result.response : 'Sorry, I could not respond.';
}

// Use it
const response = await chat('Hello!');
console.log(response);
```

### Batch Processing

```javascript
const agents = [
    { address: 'agent1...', query: 'Query 1' },
    { address: 'agent2...', query: 'Query 2' }
];

const results = await Promise.all(
    agents.map(a => client.query(a.address, a.query))
);

const successful = results.filter(r => r.success);
console.log(`${successful.length}/${results.length} succeeded`);
```

## Complete Example Project

🚀 **[Frontend Integration](https://github.com/gautammanak1/frontend-integration)** - Full Next.js chat app with:
- Modern UI (like ChatGPT)
- Dark mode support
- TypeScript
- Production-ready code

## Learn More

- [GitHub Repository](https://github.com/gautammanak1/uagent-client)
- [NPM Package](https://www.npmjs.com/package/uagent-client)
- [Fetch.ai](https://fetch.ai)
- [uAgents Framework](https://github.com/fetchai/uAgents)

## License

MIT

## Author

**Gautam Manak**
- GitHub: [@gautammanak1](https://github.com/gautammanak1)

---

Made with ❤️ for the Fetch.ai ecosystem
