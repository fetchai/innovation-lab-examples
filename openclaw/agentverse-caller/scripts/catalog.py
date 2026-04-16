#!/usr/bin/env python3
"""Print curated catalog of top Agentverse agents."""

import json

CATALOG = [
    {
        "key": "stats",
        "name": "Average Agent",
        "address": "agent1qvtnt9s6uhua3c3jundxrpgqjsy9quc2h4s83anjg6r2m95g90dn2ruw8zm",
        "description": "Compute mean, median, mode, variance, and standard deviation",
        "interactions": 92902,
        "example": 'call.py stats "10, 20, 30, 40, 50"',
    },
    {
        "key": "signals",
        "name": "Asset Signal",
        "address": "agent1qtwk0kzcnqym78rq5fgl6hxua2yessmlgunan27xezk0zr4th7ugkz32ndm",
        "description": "BUY/SELL/WAIT trading signals from news sentiment + FinBERT + price data",
        "interactions": 74560,
        "example": 'call.py signals "TSLA"',
    },
    {
        "key": "stocks",
        "name": "Technical Analysis",
        "address": "agent1q085746wlr3u2uh4fmwqplude8e0w6fhrmqgsnlp49weawef3ahlutypvu6",
        "description": "Stock technical analysis with SMA, EMA, WMA indicators and buy/sell signals",
        "interactions": 66404,
        "example": 'call.py stocks "AAPL"',
    },
    {
        "key": "image",
        "name": "DALL-E 3 Image Generator",
        "address": "agent1q0utywlfr3dfrfkwk4fjmtdrfew0zh692untdlr877d6ay8ykwpewydmxtl",
        "description": "Generate images from text descriptions using DALL-E 3",
        "interactions": 60408,
        "example": 'call.py image "a cyberpunk cityscape at night"',
    },
    {
        "key": "asi",
        "name": "ASI1-Mini",
        "address": "agent1qdhaqxdvjhtchfmra6ycwjt7p3dj7ucq2ccnx2ppk4pa5mde4kc0ghep43j",
        "description": "General-purpose AI chat powered by the Web3-native ASI1-Mini LLM",
        "interactions": 55478,
        "example": 'call.py asi "explain blockchain consensus"',
    },
    {
        "key": "translate",
        "name": "OpenAI Translator",
        "address": "agent1qfuexnwkscrhfhx7tdchlz486mtzsl53grlnr3zpntxsyu6zhp2ckpemfdz",
        "description": "Translate text between languages with auto language detection",
        "interactions": 50049,
        "example": "call.py translate \"'Hello world' to Japanese\"",
    },
    {
        "key": "github",
        "name": "Github Organisation",
        "address": "agent1q20jn039g90w7lv8rch2uzjwv36tm5kwmsfe5dqc70zht27enqpkcjewdkz",
        "description": "Retrieve GitHub org metadata -- repos, followers, description",
        "interactions": 47331,
        "example": 'call.py github "fetchai"',
    },
    {
        "key": "search",
        "name": "Tavily Search",
        "address": "agent1qt5uffgp0l3h9mqed8zh8vy5vs374jl2f8y0mjjvqm44axqseejqzmzx9v8",
        "description": "Web search with ranked results, titles, URLs, and snippets",
        "interactions": 46957,
        "example": 'call.py search "latest Fetch.ai news"',
    },
]

print(json.dumps(CATALOG, indent=2))
