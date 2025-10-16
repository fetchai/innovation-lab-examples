# ⚡ 5-Minute Quick Start - Lyria Music Agent

Generate AI music in 5 minutes! (Plus 30s per track generation)

## 1️⃣ Setup (1 minute)

```bash
cd 04-lyria-music-agent

# Use existing venv
pip install -r requirements.txt

# Use same .env - already have both keys!
```

## 2️⃣ Run (30 seconds)

```bash
python lyria_agent.py
```

## 3️⃣ Test (30 seconds + ~30s generation)

**Via ASI One:**
1. Find your agent
2. Send: `Chill lo-fi hip hop with piano`
3. **Wait ~30 seconds** - streaming music generation!
4. Receive 30-second audio file

## 4️⃣ Try These Prompts

```
Minimal techno at 120 BPM

Chill lo-fi hip hop with piano and soft beats

Epic orchestral score with strings and brass

Funky disco with bass guitar and drums

Ambient meditation music with soft pads

Jazz fusion with saxophone and smooth piano
```

## 🎵 Prompt Structure

**Genre + Instruments + Mood + Optional BPM**

### Examples:
```
[Genre] with [instruments], [mood]
```

```
[Mood] [genre] at [BPM] BPM
```

## 🎹 Popular Genres

- Electronic: Techno, House, Dubstep, Ambient
- Hip Hop: Lo-fi, Trap, Boom Bap
- Jazz: Fusion, Smooth, Bebop
- Classical: Orchestral, Piano, Chamber
- Rock: Indie, Alternative, Blues
- World: Latin, African, Asian

## 🎸 Common Instruments

- Piano, Guitar, Bass, Drums
- Strings, Brass, Woodwinds
- Synths, Pads, 808s
- Saxophone, Trumpet, Violin

## ⏳ Important Notes

1. **Generation Time**: ~30 seconds per track
2. **Track Length**: 30 seconds (configurable in code)
3. **Format**: High-quality 48kHz stereo WAV
4. **Real-time**: Uses WebSocket streaming

## 💡 Best Practices

1. **Be Descriptive** - More details = better results
2. **Combine Elements** - Genre + instruments + mood
3. **Experiment** - Try different combinations
4. **Iterate** - Refine prompts based on output

## ✅ Done!

You now have an AI music generator agent! 🎵✨
