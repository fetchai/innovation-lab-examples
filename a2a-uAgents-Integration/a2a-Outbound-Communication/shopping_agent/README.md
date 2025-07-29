# Shopping Partner Agent

## Description
The Shopping Partner Agent is an AI-powered product recommender designed to help users find products that match their specific preferences. It focuses on searching trusted e-commerce websites and verifying product availability.

## Purpose
To assist users in efficiently discovering and selecting products by providing tailored recommendations with key attributes like price, brand, and features.

## Key Features
*   **Product Recommendation**: Suggests products based on user requirements.
*   **Preference Matching**: Prioritizes products that meet a high percentage of user criteria.
*   **Trusted Source Search**: Searches reputable e-commerce platforms (e.g., Amazon, Flipkart, Myntra, Meesho, Google Shopping, Nike).
*   **Stock Verification**: Ensures recommended products are in stock and available for purchase.
*   **Detailed Attributes**: Provides clear information on product attributes.

## Usage Example
"Find me a durable, waterproof backpack suitable for hiking under $150."

## Required Environment Variables
To run the Shopping Partner Agent, you need to set the following environment variables in your `.env` file:

*   `OPENAI_API_KEY`: Your API key for OpenAI models (e.g., `gpt-4o`).
*   `EXA_API_KEY`: Your API key for ExaTools, used for web search.
