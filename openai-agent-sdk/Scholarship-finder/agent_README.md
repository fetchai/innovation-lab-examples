# Scholarship Finder

## Overview

An AI agent that helps students find scholarships they actually qualify for by searching databases and matching them to their profile.

## Purpose

Saves students 10+ hours of manual scholarship searching by providing personalized matches based on their profile (GPA, major, interests, activities).

## What It Does

- **Scholarship Search**: Searches 100+ scholarship databases using AI-powered web search
- **Profile Matching**: Matches students to scholarships they qualify for based on eligibility criteria
- **Eligibility Checking**: Verifies requirements (GPA, major, year, ethnicity, activities, etc.)
- **Deadline Tracking**: Calculates days remaining and prioritizes urgent applications
- **Smart Filtering**: Shows only relevant scholarships (Highly Qualified / Maybe / Don't Apply)

## How to Use

### Step 1: Share Your Profile
Send a message with:
- GPA (e.g., "3.7")
- Major (e.g., "Computer Science")
- Year (e.g., "Junior")
- Location (e.g., "San Jose, CA")

### Step 2: Optional Details (helps find more)
- Ethnicity/Identity
- Gender
- Interests (e.g., "AI/ML, Women in Tech")
- Activities (e.g., "Coding club president, volunteer tutor")
- Financial need level

### Step 3: Get Results
Receive personalized scholarship matches with:
- Scholarship name and amount
- Deadline with countdown
- Eligibility status
- Required documents
- Application links

## Example Usage

**You send:**
```
I'm a junior CS major with 3.7 GPA in San Jose, CA. 
Asian-American female interested in AI/ML. 
President of coding club, volunteer tutor. 
Moderate financial need.
```

**Agent responds:**
```
🎓 SCHOLARSHIP MATCHES FOUND: 12 scholarships
💰 TOTAL POTENTIAL: $85,000

✅ HIGHLY QUALIFIED (8 matches):

1. 🏆 Google Women Techmakers Scholarship
   Amount: $10,000
   Deadline: March 15, 2026 (45 days left)
   Eligibility: ✅ You meet ALL requirements
   - Female in CS major
   - Junior/Senior
   - 3.5+ GPA
   Required: Essay (500 words), 2 recommendations
   Link: https://buildyourfuture.withgoogle.com

2. 🏆 Society of Women Engineers Scholarship
   Amount: $15,000
   Deadline: February 28, 2026 (30 days left) ⏰ URGENT!
   ...
```

## Features

### Search & Matching
- Real-time web search across scholarship databases
- Intelligent filtering based on student profile
- Match scoring (percentage)

### Eligibility Analysis
- ✅ Highly Qualified: Meet ALL requirements
- ⚠️ Maybe Qualified: Need to verify some requirements
- ❌ Don't Apply: Don't meet key requirements (saves time!)

### Deadline Management
- Days remaining calculation
- Urgency categorization (< 30 days, 30-60 days, > 60 days)
- Priority sorting

### Results Organization
- Sorted by urgency and amount
- Direct application links
- Required documents checklist
- Next steps guidance

## Pricing

Free to search (powered by OpenAI API)

## Processing Time

10-15 seconds per search

## Target Users

- High school seniors applying to college
- Current college students (all years)
- Graduate students seeking funding
- Non-traditional students (adult learners)
- Parents helping their children

## Unique Value

Unlike Fastweb/Scholarships.com:
- Personalized to YOUR profile (not 1000+ generic results)
- Eligibility pre-checked (saves hours of reading requirements)
- Smart filtering (shows only what you qualify for)
- Deadline tracking (never miss opportunities)

## Technical Details

### Tech Stack
- **OpenAI Agent SDK**: AI-powered search and matching (GPT-4o with WebSearchTool)
- **uAgents Framework**: Fetch.ai's agent framework
- **Chat Protocol**: ASI-One compatible messaging
- **Agentverse**: Deployment platform (mailbox mode)

### Deployment
- **Transport**: Mailbox (no public HTTP endpoint required)
- **Identity**: Stable seed phrase
- **Port**: 8003 (default)

## Limitations

- Requires OpenAI API credits (not free)
- Search accuracy depends on web search results
- Cannot apply to scholarships automatically (provides links)
- Profile data not stored (must provide each time)

## Quick Commands

- **"help"** - See detailed instructions
- Send your profile to start finding scholarships

## Privacy & Security

- Profile processed in real-time only
- No storage of personal information
- No sharing with scholarship providers

---

**Project**: Scholarship Finder  
**Built with**: OpenAI Agent SDK + Fetch.ai uAgents  
**Version**: 1.0.0
