# ⚡ 5-Minute Quick Start - TTS Speech Agent

Generate natural speech in 5 minutes!

## 1️⃣ Setup (1 minute)

```bash
cd 05-tts-speech-agent

# Use existing venv
pip install -r requirements.txt

# Use same .env - already have both keys!
```

## 2️⃣ Run (30 seconds)

```bash
python tts_agent.py
```

## 3️⃣ Update the seed in your agent to a unique phrase and Run the Agent

**Via ASI One:**
1. Find your agent
2. Send: `Hello! Welcome to AI speech generation.`
3. Receive natural speech audio file

## 4️⃣ Try These Prompts

### Single Speaker:
```
Read this in a warm tone: Hello world!

Welcome to our AI agent platform. We're excited to have you here.

This is a test of the text-to-speech system.
```

### Multi-Speaker Dialogue:
```
Speaker 1: Hello! How can I help you today?
Speaker 2: I'd like to learn about AI agents.
Speaker 1: Great! Let me explain...
```

```
Speaker 1: Did you hear about the new features?
Speaker 2: Not yet, tell me more!
Speaker 1: We now support video, music, and speech generation!
Speaker 2: That's amazing!
```

## 🎤 Available Voices

The agent automatically assigns these voices to speakers:
- **Zephyr** - Default, warm and friendly
- **Puck** - Playful and energetic
- **Charon** - Deep and authoritative
- **Kore** - Soft and calming
- **Fenrir** - Strong and confident
- **Aoede** - Melodic and expressive
- **Orbit** - Tech-savvy and modern
- **Nimbus** - Light and airy

## 📝 Format Guide

### Single Speaker
Just write the text naturally:
```
Your text here
```

### Multi-Speaker
Use "Speaker 1:", "Speaker 2:", etc.:
```
Speaker 1: First person's dialogue
Speaker 2: Second person's dialogue
Speaker 1: Back to first person
```

## 💡 Tips

1. **Natural Language** - Write as you'd speak
2. **Punctuation Matters** - Affects pacing and tone
3. **Dialogue Format** - Use speaker labels for conversations
4. **Length** - Keep prompts reasonable (a few paragraphs max)

## 🎯 Use Cases

- **Narration** - Story reading, audiobooks
- **Dialogue** - Conversations, interviews
- **Announcements** - Public service messages
- **Education** - Lessons, tutorials
- **Entertainment** - Character voices, podcasts

## ✅ Done!

You now have a natural speech generator! 🎤✨
