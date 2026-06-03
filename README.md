# claude-call 📞

![license: MIT](https://img.shields.io/badge/license-MIT-green) ![python 3.12](https://img.shields.io/badge/python-3.12-blue) ![macOS · Linux](https://img.shields.io/badge/os-macOS%20%C2%B7%20Linux-lightgrey) ![install: one line](https://img.shields.io/badge/install-one--line-orange)

**Talk to your Claude Code by voice — a real phone call with your terminal agent.**

Not a generic voice assistant. `claude-call` is voice I/O bolted onto **your actual Claude Code session** — same skills, MCP servers, memory, and context. You launch it from a project, it *resumes the conversation you were just having there*, and you keep going by voice. It can read files, run tools, edit code, post to your integrations — everything your Claude Code can do — because the brain **is** your Claude Code.

```
  🎙️ mic ─▶ VAD (Silero + Smart Turn) ─▶ whisper.cpp (local STT)
                                              │
                                              ▼
                         claude (daemon, --resume your session)   ◀── the brain IS your Claude Code
                                              │
  🔊 speaker ◀─ edge-tts ◀──────────────── streamed reply (sentence by sentence)
```

- **Local ears**: whisper.cpp, offline, ~0.6s/utterance (resident server).
- **Your brain**: the `claude` CLI you're already logged into — **no API key, no extra cost** beyond your subscription, all your skills/MCP/context.
- **Free voice**: Microsoft edge-tts, many languages — or plug a premium API (ElevenLabs, Cartesia, OpenAI, Rime, Deepgram) if you want.
- **One warm process**: the brain runs as a persistent daemon for the whole call — context stays cached, replies stream as it talks.

## Why it's different
Every other voice agent gives you a fresh, context-less assistant. This one **continues your session**. Ask it "where were we?" and it knows — because it's literally the same conversation, reached through a microphone instead of a keyboard.

## Quick install (one command)
```bash
curl -fsSL https://raw.githubusercontent.com/caiovicentino/claude-call/main/install.sh | bash
```
This installs everything — uv, ffmpeg, whisper.cpp, portaudio, the repo, a speech model — and a global `claude-call` command. It finishes by running `claude-call doctor`, so you immediately see **all green** plus a quick latency benchmark. Then, from any project: `claude-call`.

You still need **[Claude Code](https://docs.claude.com/claude-code)** installed and logged in (it's the brain — no API key). macOS also needs [Homebrew](https://brew.sh). Prefer to do it by hand? Follow the step-by-step below.

## Step-by-step (from zero)

### 1. Install the prerequisites
You need four things on your machine:

| Tool | For | Install |
|---|---|---|
| **Claude Code** | the brain | [docs](https://docs.claude.com/claude-code) — then run `claude` once and **log in** |
| **uv** | Python deps | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| **whisper.cpp** | local speech‑to‑text | macOS: `brew install whisper-cpp` · Linux: build (below) |
| **ffmpeg + portaudio** | audio I/O | macOS: `brew install ffmpeg portaudio` · Linux: `sudo apt install ffmpeg portaudio19-dev` |

**macOS, one line:**
```bash
brew install uv ffmpeg whisper-cpp portaudio
```

> ⚠️ **Claude Code must be logged in.** Run `claude` once and sign in. That's the brain — claude‑call uses your existing subscription, **no API key**.

**Linux whisper.cpp** (if there's no package): build it and put its binaries on your `PATH`:
```bash
git clone https://github.com/ggerganov/whisper.cpp && cd whisper.cpp
cmake -B build && cmake --build build -j --config Release
export PATH="$PWD/build/bin:$PATH"   # so whisper-server / whisper-cli are found
```

### 2. Get claude-call
```bash
git clone https://github.com/caiovicentino/claude-call
cd claude-call
./install.sh        # checks prereqs, installs python deps, downloads a whisper model
```

### 3. (optional) Make it a global command
```bash
ln -s "$PWD/call.sh" /usr/local/bin/claude-call
```

### 4. Call
Go into a project you've used with Claude Code, and run it:
```bash
cd ~/my-project
claude-call          # or:  /path/to/claude-call/call.sh
```
It greets you, **resumes that project's most recent Claude Code session**, and listens. Talk normally; pause ~1s when you finish a sentence (that's the turn detector deciding you're done). `Ctrl+C` ends the call.

The first run downloads a small Silero model and warms the whisper server. The first spoken turn loads your session context (slower; cached after that).

## Commands
| Command | What it does |
|---|---|
| `claude-call` | Start a voice call — resumes the Claude Code session in the current folder. |
| `claude-call config` | Interactive menu: voice (with live preview), style, language, model, echo, TTS provider. |
| `claude-call doctor` | Check prerequisites + model + config, and benchmark STT/TTS latency. |

## Configure

Run the interactive menu — pick your **voice** (with live preview), **speaking style**, language, brain model, echo mode and activation:
```bash
claude-call config
```
It writes your choices to `.env`. Prefer doing it by hand? Every setting is a plain env var:

### All settings (`.env` or env vars)
| Var | Default | What |
|---|---|---|
| `CALL_LANG` | `en` | Language (en, pt, es, fr, de, it, ja…). Picks a default voice + speech style. |
| `CALL_VOICE` | per-lang | Any [edge-tts voice](https://github.com/rany2/edge-tts), or a voice id for a premium provider. |
| `CALL_VOICE_RATE` | `+0%` | Speaking speed (edge only). |
| `CALL_TTS` | `edge` | Voice provider — `edge` (free) or premium (see [Premium voices](#premium-voices-optional-bring-your-own-key)). |
| `CALL_MODEL` | your default | `opus` / `sonnet` / `haiku`. Bigger = smarter & slower. |
| `CALL_CONTINUE` | `1` | Resume your most recent Claude Code session in `CALL_CWD`. |
| `CALL_CWD` | where you ran it | Which project's session to resume. |
| `CALL_WAKE` | *(empty)* | Empty = open mic (call mode). Set e.g. `claude` to require a wake word (assistant mode). |
| `CALL_ECHO_GATE` | `1` | Mute mic while it speaks (use on speakers). `0` = barge-in (use headphones). |
| `CALL_AEC` | `0` | macOS hardware echo cancellation → barge-in without headphones (see below). |
| `CALL_PERMISSION` | `--dangerously-skip-permissions` | See **Security**. |

_Full list (STT model & port, greeting, active window, premium keys) is in [`.env.example`](.env.example)._

## Premium voices (optional, bring your own key)
Free **edge-tts** is the default and sounds great. If you want the newest, most realistic voices and don't mind paying the provider, plug in an API key:

| `CALL_TTS` | Provider | Get a key / voices |
|---|---|---|
| `edge` | edge-tts (free, default) | — |
| `elevenlabs` | ElevenLabs — most realistic | [elevenlabs.io](https://elevenlabs.io) |
| `cartesia` | Cartesia Sonic — ultra low latency | [cartesia.ai](https://cartesia.ai) |
| `openai` | OpenAI TTS | voices: alloy, nova, shimmer… |
| `rime` | Rime — natural conversational | [rime.ai](https://rime.ai) |
| `deepgram` | Deepgram Aura — fast | [deepgram.com](https://deepgram.com) |

Pick it in `claude-call config` (it asks for the key + voice), or set in `.env`:
```bash
CALL_TTS=elevenlabs
CALL_TTS_API_KEY=sk-...
CALL_VOICE=<a voice id from the provider>
```
Your key lives only in your local `.env`. No key = it just uses free edge-tts.

## Modes
- **Call mode** (default): open mic, no wake word — just talk, like a phone call.
- **Assistant mode**: set `CALL_WAKE=claude` so it only answers when addressed (good for always-on in the background).

## Echo / headphones
Without headphones the mic hears the agent's own voice and loops. Three options:
- **`CALL_ECHO_GATE=1`** (default): half-duplex — mic muted while it speaks. Works on speakers; you can't interrupt mid-sentence.
- **Headphones + `CALL_ECHO_GATE=0`**: full-duplex, barge-in works (cut it off any time).
- **`CALL_AEC=1`** (macOS only): real hardware AEC via the OS Voice Processing unit (same as FaceTime) → barge-in on speakers, no headphones. Needs `./build.sh` (compiles a small Swift helper) and microphone permission for your terminal. *(Built but validate on your machine — it needs a real audio session.)*

## Latency
Each turn is one real inference over your session context. Expect a couple seconds for simple turns (replies stream as it talks), more on tool-heavy turns (it speaks a quick filler so there's no dead air). Use `CALL_MODEL=haiku` for snappier, `opus` for smarter.

## Security ⚠️
Hands-free voice can't answer permission prompts, so the default `CALL_PERMISSION=--dangerously-skip-permissions` lets the agent run tools / bash / edits **without asking**. That's powerful and potentially destructive. Only use it on machines/projects you trust. To be asked instead, set `CALL_PERMISSION=--permission-mode default` — but the call will stall whenever a prompt appears.

## Troubleshooting
- **Check everything first:** `claude-call doctor` — verifies prerequisites, your model and config, and benchmarks STT/TTS latency (tells you exactly what's missing or slow).
- **It doesn't hear me** → give your terminal app microphone permission (macOS: System Settings → Privacy & Security → Microphone), then restart the call.
- **`whisper model not found`** → `./scripts/download-model.sh small` (or point `CALL_WHISPER_MODEL` at a ggml file you have).
- **`whisper-server` not found** → install whisper.cpp (step 1), or set `CALL_WHISPER_SERVER=0` to use `whisper-cli` (slower, no server).
- **It hears its own voice / loops** → you're on speakers with barge-in on. Use headphones, keep `CALL_ECHO_GATE=1` (default), or try `CALL_AEC=1` (macOS).
- **Replies are slow** → the first turn loads your session context; set `CALL_MODEL=haiku` for snappier turns.
- **It starts fresh / "session not found"** → you launched from a directory with no prior Claude Code session. Run from a project you've used `claude` in, or set `CALL_SESSION_ID`.
- **Python 3.13 error** → claude-call pins Python 3.12 via `.python-version` (3.13 removed the `audioop` module). `uv` fetches 3.12 automatically.

## How it works (the honest version)
The brain is **not** a daemon that "thinks" continuously. LLMs are stateless: every spoken turn triggers one fresh inference over your conversation, run on Anthropic's servers — exactly what happens when you type in Claude Code. `claude-call` keeps **one `claude` process alive** for the call (stream-json in/out, `--resume <your session>`), so context stays warm and replies stream — but it's a warm, persistent *session*, not a continuous consciousness.

## Files
`call.py` (pipeline) · `brain.py` (claude daemon) · `stt.py` (whisper-server/cli) · `tts.py` (edge-tts + premium providers) · `echo_gate.py` · `session.py` (finds your session) · `config.py` · `configure.py` (settings menu) · `doctor.py` (setup check + benchmark) · `install.sh` · `aec_bridge.swift` + `extras_mac_aec.py` (optional macOS AEC).

## Credits
Built on [Pipecat](https://github.com/pipecat-ai/pipecat), [whisper.cpp](https://github.com/ggerganov/whisper.cpp), [edge-tts](https://github.com/rany2/edge-tts), and [Claude Code](https://docs.claude.com/claude-code).

Created by **Caio Vicentino**. MIT licensed.

---

### 🛠️ Built with [Cultura Builder](https://culturabuilder.com)
**A maior comunidade de builders da América Latina** — turning non-technical people into AI builders. **7,900+ builders**, 1 year strong, everything built 100% with AI. [**Come build with us → culturabuilder.com**](https://culturabuilder.com)
