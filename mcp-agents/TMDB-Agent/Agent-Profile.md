![tag:TMDB-MCP](https://img.shields.io/badge/Innovation-Lab-blue)
![tag:Movie-Recommendations](https://img.shields.io/badge/Movies-Recommendations-orange)
![tag:TV-Shows](https://img.shields.io/badge/TV-Shows-green)
![tag:Streaming-Availability](https://img.shields.io/badge/Streaming-Availability-yellow)

# TMDB Agent

## Description:

The **TMDB Agent** is a conversational movie and TV show recommendation agent that translates natural-language mood descriptions into real, streaming-ready picks. It integrates with the **TMDB API** via a custom MCP server to deliver **mood-matched recommendations with live streaming availability** for your country — eliminating endless scrolling and decision fatigue.

---

## 🚀 Key Features

### 🎭 Mood-Based Discovery
- Understands natural-language vibes: *"dark and slow-burn"*, *"feel-good comedy"*, *"something mind-bending"*
- Maps moods to **TMDB genre combinations and sort strategies**
- Supports aliases: *tense*, *gripping*, *chill*, *trippy*, *sad*, *emotional*

### 📺 Movies + TV Shows
- Full support for both **movies and TV series**
- Handles mixed-mood requests: *"I want dark, they want romantic"*
- Runtime filtering: *"under 90 minutes"*, *"short films only"*

### 🌍 Real-Time Streaming Availability
- Checks **live watch providers** via TMDB (subscription, rent, buy)
- Supports any country via ISO code (US, GB, IN, AU, CA…)
- Concurrent provider lookups for all candidates simultaneously

### 💾 Session Memory
- Tracks rejections, seen titles, and a personal watchlist across turns
- Skips already-seen titles in all future recommendations
- Save picks: *"save The Dark Knight"* — retrieve later: *"show my watchlist"*

---

## 🧰 Available Tools

### `resolve_mood` / `resolve_mood_tv`
- **Purpose**: Discover movies or TV shows matching a vibe/mood
- **Vibes**: on-edge, slow-burn, dark, intense, feel-good, romantic, cosy, mind-bending, scary, funny, action-packed, tearjerker

### `search_movies` / `search_tv`
- **Purpose**: Search TMDB by title to resolve IDs before similarity lookups

### `get_similar` / `get_similar_tv`
- **Purpose**: Find titles similar to a given TMDB ID

### `get_recommendations`
- **Purpose**: TMDB behavioural recommendations for a movie

### `get_trending`
- **Purpose**: Trending movies or TV shows (day or week)

### `search_by_keyword`
- **Purpose**: Find movies tagged with a specific keyword (heist, revenge, psychological…)

### `get_movie_details` / `get_tv_details`
- **Purpose**: Full details — runtime, genres, seasons, tagline

### `check_watch_providers` / `check_tv_watch_providers`
- **Purpose**: Live streaming availability for a list of IDs in a given country

---

## 🛠️ Capabilities

### 🎬 Movie & TV Discovery
- Mood-matched discovery across 12 curated vibes
- Trending lookups for freshness signals
- Keyword-tagged search for precision
- Similarity chains from a favourite title

### 📋 Smart Session Management
- Rejection tracking — *"not that one"* removes a title from all future picks
- Seen-title exclusion — *"mark Parasite as seen"*
- Persistent watchlist across the session
- Mixed-mood blending for groups with different tastes

### 💬 Conversational Flow
- One optional follow-up if vibe and context are unclear
- Deterministic formatting — picks always display in the same clean structure
- Feature hints surfaced after each recommendation set

---

## 💬 Example Queries

### 🎭 Mood-Based
- *"I want something dark and slow-burn tonight"*
- *"Something mind-bending — I loved Inception"*
- *"Cosy and feel-good, watching with family"*
- *"Intense thriller, solo watch, under 2 hours"*

### 📺 TV Mode
- *"Something to binge — dark crime drama"*
- *"Find shows similar to Succession"*
- *"Cosy TV show for the weekend"*

### 🔄 Follow-up Refinement
- *"Not that one — already seen it"*
- *"What's available on Netflix in the UK?"*
- *"Save The Dark Knight to my watchlist"*
- *"Show my watchlist"*

### 🌍 Trending
- *"What's trending in movies this week?"*
- *"Most popular shows right now"*

---

## 🧪 Usage Examples

### ✅ Mood + Context
**Input**: `"I want something on-edge, watching solo, loved Parasite"`
**Output**: 3–4 picks matching the thriller/crime vibe, similar to Parasite's class tension, with streaming service listed for each.

### ✅ Mixed Moods
**Input**: `"I want dark, they want romantic — we can't decide"`
**Output**: Picks that blend both moods — dark romance or emotionally charged drama — available to stream.

### ✅ Runtime Filter
**Input**: `"Feel-good comedy under 90 minutes"`
**Output**: Comedy picks filtered to under 90 minutes, streaming-ready.

---

## ⚙️ Technical Benefits

### ✅ No Scroll Fatigue
- One message in, curated picks out — no genre browsing required

### ✅ Live Availability
- Streaming data is fetched live from TMDB, not cached or stale

### ✅ Context-Aware
- Remembers what you've rejected and seen across the whole session

---
