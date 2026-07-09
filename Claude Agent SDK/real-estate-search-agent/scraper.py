"""
scraper.py — Real estate data fetcher using HomeHarvest.

HomeHarvest is the best free option: it scrapes Zillow, Realtor.com and Redfin
simultaneously using their hidden/internal APIs (no API key needed), returns
a clean pandas DataFrame, and is actively maintained.

Why HomeHarvest over raw scraping?
- No API key required
- Scrapes 3 sources at once
- Returns structured data (price, sqft, beds, baths, url, address)
- Handles anti-bot measures internally
- Returns a pandas DataFrame — trivial to pass into Google Sheets

Caveat: Zillow blocks aggressively. If you get 403s, use site_name=["realtor.com", "redfin"]
"""

from homeharvest import scrape_property
import pandas as pd
from dataclasses import dataclass
from typing import Optional


@dataclass
class SearchInput:
    location: str  # e.g. "Austin, TX" or zip "78701"
    listing_type: str = "for_sale"  # for_sale | for_rent | sold
    min_price: Optional[int] = None
    max_price: Optional[int] = None
    min_beds: Optional[int] = None
    max_beds: Optional[int] = None
    min_sqft: Optional[int] = None
    max_sqft: Optional[int] = None
    property_type: Optional[list] = None  # ["single_family", "condo", "townhouse"]
    past_days: int = 30  # only listings from last N days


def _normalize_property_types(property_types: Optional[list]) -> Optional[list]:
    """Map user-friendly types to HomeHarvest property_type values."""
    if not property_types:
        return None

    type_map = {
        "single_family": "single_family",
        "condo": "condos",
        "condos": "condos",
        "townhouse": "townhomes",
        "townhomes": "townhomes",
        "multi_family": "multi_family",
    }
    normalized = []
    for item in property_types:
        key = str(item).strip().lower()
        mapped = type_map.get(key)
        if mapped:
            normalized.append(mapped)

    return list(dict.fromkeys(normalized)) if normalized else None


def fetch_listings(search: SearchInput) -> pd.DataFrame:
    """
    Fetch real estate listings using HomeHarvest.
    Returns a DataFrame with columns: property_url, price, street_address,
    city, state, zip_code, beds, baths, square_feet, listing_type, site_name.
    """
    print(f" Searching for properties in: {search.location}")
    print(
        f"   Type: {search.listing_type} | Budget: ${search.min_price or 0:,} - ${search.max_price or '∞'}"
    )
    normalized_property_types = _normalize_property_types(search.property_type)

    properties = scrape_property(
        location=search.location,
        listing_type=search.listing_type,
        past_days=search.past_days,
        beds_min=search.min_beds,
        beds_max=search.max_beds,
        sqft_min=search.min_sqft,
        sqft_max=search.max_sqft,
        price_min=search.min_price,
        price_max=search.max_price,
        property_type=normalized_property_types,
    )

    if properties.empty:
        print("  No properties found. Try broadening the location or date range.")
        return properties

    print(f" Raw results: {len(properties)} properties found")

    # --- Apply user filters ---
    if search.min_price:
        properties = properties[properties["list_price"] >= search.min_price]
    if search.max_price:
        properties = properties[properties["list_price"] <= search.max_price]
    if search.min_beds:
        properties = properties[properties["beds"] >= search.min_beds]
    if search.max_beds:
        properties = properties[properties["beds"] <= search.max_beds]
    if search.min_sqft:
        properties = properties[properties["sqft"] >= search.min_sqft]
    if search.max_sqft:
        properties = properties[properties["sqft"] <= search.max_sqft]

    print(f" After filtering: {len(properties)} properties match your criteria")

    # --- Select + rename only the columns we care about ---
    keep_cols = {
        "property_url": "Listing Link",
        "list_price": "Price ($)",
        "street_address": "Street Address",
        "city": "City",
        "state": "State",
        "zip_code": "Zip Code",
        "beds": "Beds",
        "full_baths": "Baths",
        "sqft": "Size (sqft)",
        "style": "Property Type",
        "site_name": "Source",
    }

    # Only keep columns that actually exist in the DataFrame
    available = {k: v for k, v in keep_cols.items() if k in properties.columns}
    result = properties[list(available.keys())].rename(columns=available)

    # Sort by price
    if "Price ($)" in result.columns:
        result = result.sort_values("Price ($)", ascending=True)

    return result.head(20)  # Top 20 results max


def format_price(price) -> str:
    """Format price for display."""
    try:
        return f"${int(price):,}"
    except (ValueError, TypeError):
        return "N/A"
