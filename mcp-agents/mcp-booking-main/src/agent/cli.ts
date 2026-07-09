#!/usr/bin/env node
/**
 * Local CLI for the recommendation agent.
 * Usage: npm run agent -- "romantic Italian dinner in San Jose"
 * Requires MCP server running (npm run dev) and GOOGLE_MAPS_API_KEY in .env
 */
import dotenv from 'dotenv';
import { respondToUserQuery } from './recommendationAgent.js';

dotenv.config();

const query = process.argv.slice(2).join(' ').trim();
if (!query) {
  console.error('Usage: npm run agent -- "<your restaurant question>"');
  process.exit(1);
}

respondToUserQuery(query)
  .then(out => {
    console.log(out);
  })
  .catch(err => {
    console.error(err instanceof Error ? err.message : err);
    process.exit(1);
  });
