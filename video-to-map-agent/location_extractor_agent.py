import os
import json
from dotenv import load_dotenv
from openai import OpenAI
from uagents import Agent, Context
from shared_models import LocationExtractionRequest, LocationExtractionResponse

load_dotenv()

agent = Agent(
    name="location_extractor_agent",
    seed=os.getenv("LOCATION_SEED"),
    port=8006,
    endpoint=[os.getenv("LOCATION_EXTRACTOR_ENDPOINT", "http://localhost:8006/submit")],
    network="testnet",
)

asi1_client = OpenAI(
    base_url="https://api.asi1.ai/v1",
    api_key=os.getenv("ASI1_API_KEY"),
)


@agent.on_message(LocationExtractionRequest)
async def handle_extraction(ctx: Context, sender: str, msg: LocationExtractionRequest):
    ctx.logger.info(f"Extracting locations from {len(msg.text):,} char transcript")
    try:
        response = asi1_client.chat.completions.create(
            model="asi1-mini",
            max_tokens=1000,
            temperature=0,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a location extraction assistant. "
                        "Return ONLY valid JSON arrays. "
                        "No explanation, no markdown, no preamble."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        "Extract ONLY visitable tourist destinations from this "
                        "travel video transcript.\n\n"
                        "INCLUDE: specific named parks, landmarks, viewpoints, "
                        "trailheads, lakes, waterfalls, towns worth visiting, "
                        "beaches, historical sites, museums, notable restaurants, "
                        "campgrounds, scenic overlooks.\n\n"
                        "STRICTLY EXCLUDE:\n"
                        "- Broad geographic regions (California, West Coast, "
                        "Southern California, Pacific Ocean, Northern Hemisphere)\n"
                        "- Roads and highways (Highway 1, I-5, North Palm Canyon "
                        "Drive, State Street, any street name)\n"
                        "- Sports or administrative bodies (CIF, any league, "
                        "section, district, council)\n"
                        "- Medical or professional facilities (any hospice, "
                        "clinic, hospital, racquet club, law firm)\n"
                        "- Borders or abstract zones (California-Nevada Border, "
                        "the Pacific, the coast)\n"
                        "- Vague references ('a small town', 'the forest', "
                        "'some restaurant', 'that place')\n"
                        "- Duplicates or near-duplicates of the same place\n"
                        "- Any location clearly outside the trip's primary "
                        "region (e.g. Italian villages if the trip is in "
                        "California)\n\n"
                        "Use full names where mentioned "
                        "(e.g. 'McArthur-Burney Falls' not just 'falls'). "
                        "Preserve the order they appear in the video. "
                        "No duplicates.\n\n"
                        f"Transcript:\n{msg.text[:12000]}\n\n"
                        'Return format: ["Location A", "Location B", "Location C"]'
                    ),
                },
            ],
        )
        raw = response.choices[0].message.content.strip()
        raw = raw.replace("```json", "").replace("```", "").strip()
        ctx.logger.info(f"ASI1 raw output: {raw[:200]}")
        locations = json.loads(raw)
        if not isinstance(locations, list):
            locations = []
        ctx.logger.info(f"Extracted {len(locations)} locations: {locations}")
        await ctx.send(sender, LocationExtractionResponse(locations=locations))
    except json.JSONDecodeError as e:
        ctx.logger.error(f"JSON parse error: {e} — raw: {raw[:300]}")
        await ctx.send(sender, LocationExtractionResponse(locations=[]))
    except Exception as e:
        ctx.logger.error(f"Extraction error: {e}")
        await ctx.send(sender, LocationExtractionResponse(locations=[]))


if __name__ == "__main__":
    agent.run()
