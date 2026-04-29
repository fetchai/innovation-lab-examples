import os
from urllib.parse import quote
from dotenv import load_dotenv
import googlemaps
from uagents import Agent, Context
from shared_models import GeocodeRequest, GeocodeResponse

load_dotenv()

agent = Agent(
    name="geocoder_mapper_agent",
    seed=os.getenv("GEOCODER_SEED"),
    port=8007,
    endpoint=[os.getenv("GEOCODER_MAPPER_ENDPOINT", "http://localhost:8007/submit")],
    network="testnet",
)

gmaps = googlemaps.Client(key=os.getenv("GOOGLE_MAPS_API_KEY"))


def build_maps_url(places: list) -> str:
    if not places:
        return ""
    if len(places) == 1:
        return (
            f"https://www.google.com/maps/search/?api=1"
            f"&query={quote(places[0]['name'])}"
            f"&query_place_id={places[0]['place_id']}"
        )
    origin = quote(places[0]["address"])
    destination = quote(places[-1]["address"])
    waypoints = "|".join(quote(p["address"]) for p in places[1:-1])
    url = (
        f"https://www.google.com/maps/dir/?api=1"
        f"&origin={origin}"
        f"&destination={destination}"
        f"&travelmode=driving"
    )
    if waypoints:
        url += f"&waypoints={waypoints}"
    return url


@agent.on_message(GeocodeRequest)
async def handle_geocode(ctx: Context, sender: str, msg: GeocodeRequest):
    ctx.logger.info(f"Geocoding {len(msg.locations)} locations")
    validated = []
    skipped = 0

    for name in msg.locations:
        try:
            result = gmaps.places(query=name)
            if result.get("status") == "OK" and result.get("results"):
                place = result["results"][0]
                validated.append(
                    {
                        "name": place["name"],
                        "address": place["formatted_address"],
                        "lat": place["geometry"]["location"]["lat"],
                        "lng": place["geometry"]["location"]["lng"],
                        "place_id": place["place_id"],
                    }
                )
                ctx.logger.info(f"Validated: {place['name']}")
            else:
                ctx.logger.info(f"Could not validate: {name}")
                skipped += 1
        except Exception as e:
            ctx.logger.error(f"Geocode error for '{name}': {e}")
            skipped += 1

    maps_url = build_maps_url(validated)
    ctx.logger.info(
        f"Geocoding complete: {len(validated)} validated, {skipped} skipped"
    )
    await ctx.send(
        sender,
        GeocodeResponse(
            validated_stops=validated,
            maps_url=maps_url,
            skipped_count=skipped,
        ),
    )


if __name__ == "__main__":
    agent.run()
