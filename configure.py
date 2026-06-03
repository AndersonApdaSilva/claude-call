"""Interactive config menu for claude-call.  Run: `claude-call config`

Edits the repo's .env — voice, speaking rate, communication style, language,
brain model, echo mode and activation. Can preview voices out loud.
"""
import asyncio
import os
import platform
import re
import subprocess
import tempfile
from pathlib import Path

import edge_tts

ROOT = Path(__file__).resolve().parent
ENV = ROOT / ".env"
EXAMPLE = ROOT / ".env.example"

# Managed keys (others in .env are preserved)
DEFAULTS = {
    "CALL_LANG": "en",
    "CALL_TTS": "edge",
    "CALL_TTS_API_KEY": "",
    "CALL_TTS_MODEL": "",
    "CALL_VOICE": "",
    "CALL_VOICE_RATE": "+0%",
    "CALL_SYSTEM": "",
    "CALL_MODEL": "",
    "CALL_ECHO_GATE": "1",
    "CALL_AEC": "0",
    "CALL_WAKE": "",
    "CALL_GREETING": "",
}

# provider -> (human label, where to get a key / voices)
TTS_PROVIDERS = {
    "edge":       ("edge-tts — free, many languages (default)", ""),
    "elevenlabs": ("ElevenLabs — most realistic", "https://elevenlabs.io  (voice library + API key)"),
    "cartesia":   ("Cartesia Sonic — ultra low latency", "https://play.cartesia.ai"),
    "openai":     ("OpenAI TTS", "voices: alloy, echo, fable, onyx, nova, shimmer"),
    "rime":       ("Rime — natural conversational", "https://rime.ai"),
    "deepgram":   ("Deepgram Aura — fast", "https://deepgram.com"),
}

DEFAULT_VOICE = {
    "en": "en-US-AndrewNeural", "pt": "pt-BR-AntonioNeural", "es": "es-ES-AlvaroNeural",
    "fr": "fr-FR-HenriNeural", "de": "de-DE-ConradNeural", "it": "it-IT-DiegoNeural",
    "ja": "ja-JP-KeitaNeural",
}

STYLES = {
    "1": ("Natural call (default)", ""),
    "2": ("Short & direct", "Talk like a quick phone call. One sentence when possible. "
          "No filler, no preamble, no markdown. Just the answer, casual and human."),
    "3": ("Warm & friendly", "Talk like a close friend on the phone — warm, encouraging, a bit "
          "playful. Short and natural, contracted speech, no markdown, no assistant filler."),
    "4": ("Professional & focused", "Speak like a sharp, calm colleague on a call. Clear and "
          "concise, professional but human. No markdown, no filler, get to the point."),
    "5": ("Custom…", None),
}

SAMPLE = {
    "en": "Hey, this is how I sound on a call.",
    "pt": "Opa, é assim que eu soo numa call.",
    "es": "Hola, así es como sueno en una llamada.",
}


def load() -> dict:
    cfg = dict(DEFAULTS)
    src = ENV if ENV.exists() else EXAMPLE
    extra = {}
    if src.exists():
        for line in src.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k = k.strip()
            v = re.split(r"\s+#", v, 1)[0].strip()  # drop inline comments
            (cfg if k in DEFAULTS else extra)[k] = v
    cfg["_extra"] = extra
    return cfg


def save(cfg: dict):
    extra = cfg.pop("_extra", {})
    lines = ["# claude-call config — edit with `claude-call config`", ""]
    for k in DEFAULTS:
        lines.append(f"{k}={cfg.get(k, '')}")
    for k, v in extra.items():
        lines.append(f"{k}={v}")
    ENV.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\n  saved → {ENV}\n")


def _lang2(cfg):
    return (cfg.get("CALL_LANG") or "en")[:2]


def _voice(cfg):
    return cfg.get("CALL_VOICE") or DEFAULT_VOICE.get(_lang2(cfg), "en-US-AndrewNeural")


async def _voices_for(lang2):
    vs = await edge_tts.list_voices()
    return sorted([v for v in vs if v["Locale"].lower().startswith(lang2)], key=lambda v: v["ShortName"])


async def _synth(voice, rate, text) -> bytes:
    mp3 = bytearray()
    async for c in edge_tts.Communicate(text, voice, rate=rate or "+0%").stream():
        if c["type"] == "audio":
            mp3.extend(c["data"])
    return bytes(mp3)


def _play(mp3: bytes):
    f = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
    f.write(mp3); f.close()
    try:
        if platform.system() == "Darwin":
            subprocess.run(["afplay", f.name], check=False)
        elif subprocess.run(["which", "ffplay"], capture_output=True).returncode == 0:
            subprocess.run(["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", f.name], check=False)
        else:
            subprocess.run(["aplay", f.name], check=False)
    finally:
        try:
            os.unlink(f.name)
        except OSError:
            pass


def ask(prompt, default=""):
    try:
        v = input(prompt).strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return None
    return v or default


# ----------------------------------------------------------------- editors
def edit_language(cfg):
    print("\n  Language (affects default voice + speech style): en, pt, es, fr, de, it, ja…")
    v = ask(f"  language [{cfg['CALL_LANG']}]: ", cfg["CALL_LANG"])
    if v:
        cfg["CALL_LANG"] = v[:2]
        cfg["CALL_VOICE"] = ""  # reset to language default


def edit_provider(cfg):
    print("\n  Voice provider (TTS):")
    keys = list(TTS_PROVIDERS)
    for i, k in enumerate(keys, 1):
        label, where = TTS_PROVIDERS[k]
        tag = "  ← current" if cfg.get("CALL_TTS", "edge") == k else ""
        print(f"   {i}. {label}{tag}")
        if where:
            print(f"       {where}")
    sel = ask("  choose a number: ")
    if not (sel.isdigit() and 1 <= int(sel) <= len(keys)):
        return
    prov = keys[int(sel) - 1]
    cfg["CALL_TTS"] = prov
    if prov == "edge":
        cfg["CALL_TTS_API_KEY"] = ""
        print("  → free edge-tts. Pick a voice in 'Voice'.")
        return
    print(f"\n  {prov} is a paid API — paste your key (stored in .env):")
    k = ask("  API key: ")
    if k:
        cfg["CALL_TTS_API_KEY"] = k
    v = ask(f"  voice id for {prov} (blank = provider default): ")
    if v:
        cfg["CALL_VOICE"] = v
    m = ask("  model override (blank = default): ")
    if m:
        cfg["CALL_TTS_MODEL"] = m
    print(f"  → {prov} set. (Preview works for edge voices; premium plays on the first call.)")


def edit_voice(cfg):
    if cfg.get("CALL_TTS", "edge") != "edge":
        prov = cfg["CALL_TTS"]
        print(f"\n  Voice for {prov}. {TTS_PROVIDERS[prov][1]}")
        v = ask(f"  voice id [{cfg.get('CALL_VOICE') or 'default'}]: ", cfg.get("CALL_VOICE", ""))
        if v:
            cfg["CALL_VOICE"] = v
        return
    lang2 = _lang2(cfg)
    voices = asyncio.run(_voices_for(lang2))
    if not voices:
        print(f"  no voices found for '{lang2}'. Enter a full edge-tts voice name.")
    else:
        print(f"\n  Voices for '{lang2}':")
        for i, v in enumerate(voices, 1):
            print(f"   {i:>2}. {v['ShortName']:<28} {v['Gender']}")
    print(f"\n  current: {_voice(cfg)}")
    sel = ask("  pick a number, type a voice name, or blank to keep: ")
    if not sel:
        return
    chosen = None
    if sel.isdigit() and voices and 1 <= int(sel) <= len(voices):
        chosen = voices[int(sel) - 1]["ShortName"]
    else:
        chosen = sel
    if ask(f"  preview '{chosen}'? [y/N]: ").lower() == "y":
        try:
            _play(asyncio.run(_synth(chosen, cfg["CALL_VOICE_RATE"], SAMPLE.get(lang2, SAMPLE["en"]))))
        except Exception as e:  # noqa: BLE001
            print(f"  (preview failed: {e})")
    cfg["CALL_VOICE"] = chosen


def edit_rate(cfg):
    print("\n  Speaking rate, e.g. -10%, +0%, +15%")
    v = ask(f"  rate [{cfg['CALL_VOICE_RATE']}]: ", cfg["CALL_VOICE_RATE"])
    if v:
        cfg["CALL_VOICE_RATE"] = v if v.endswith("%") else v + "%"


def edit_style(cfg):
    print("\n  Communication style:")
    for k, (label, _) in STYLES.items():
        print(f"   {k}. {label}")
    sel = ask("  choose [1-5]: ")
    if sel not in STYLES:
        return
    label, prompt = STYLES[sel]
    if prompt is None:  # custom
        print("  Describe how it should talk on the call (one paragraph):")
        custom = ask("  > ")
        cfg["CALL_SYSTEM"] = custom or ""
    else:
        cfg["CALL_SYSTEM"] = prompt
    print(f"  style → {label}")


def edit_model(cfg):
    print("\n  Brain model:  1) default  2) opus  3) sonnet  4) haiku")
    m = {"1": "", "2": "opus", "3": "sonnet", "4": "haiku"}
    sel = ask("  choose [1-4]: ")
    if sel in m:
        cfg["CALL_MODEL"] = m[sel]


def edit_echo(cfg):
    print("\n  Audio / echo:")
    print("   1. Speakers — half-duplex (default, no headphones)")
    print("   2. Headphones — full-duplex, you can interrupt it")
    print("   3. Speakers + macOS AEC — interrupt without headphones")
    sel = ask("  choose [1-3]: ")
    if sel == "1":
        cfg["CALL_ECHO_GATE"], cfg["CALL_AEC"] = "1", "0"
    elif sel == "2":
        cfg["CALL_ECHO_GATE"], cfg["CALL_AEC"] = "0", "0"
    elif sel == "3":
        cfg["CALL_AEC"] = "1"


def edit_activation(cfg):
    print("\n  Activation:  1) Open mic (call mode)   2) Wake word (assistant mode)")
    sel = ask("  choose [1-2]: ")
    if sel == "1":
        cfg["CALL_WAKE"] = ""
    elif sel == "2":
        w = ask("  wake word (e.g. claude): ")
        cfg["CALL_WAKE"] = w or "claude"


def _summary(cfg):
    echo = "speakers" if cfg["CALL_ECHO_GATE"] == "1" and cfg["CALL_AEC"] == "0" else \
           "AEC" if cfg["CALL_AEC"] == "1" else "headphones"
    act = "open mic" if not cfg["CALL_WAKE"] else f"wake: {cfg['CALL_WAKE']}"
    style = next((l for k, (l, p) in STYLES.items() if p == cfg["CALL_SYSTEM"]), "custom") \
        if cfg["CALL_SYSTEM"] else "natural"
    prov = cfg.get("CALL_TTS", "edge")
    voice = _voice(cfg) if prov == "edge" else (cfg.get("CALL_VOICE") or f"{prov} default")
    return (f"lang={cfg['CALL_LANG']}  tts={prov}  voice={voice}  rate={cfg['CALL_VOICE_RATE']}  "
            f"style={style}  model={cfg['CALL_MODEL'] or 'default'}  audio={echo}  {act}")


def main():
    cfg = load()
    actions = {
        "1": edit_language, "2": edit_provider, "3": edit_voice, "4": edit_rate,
        "5": edit_style, "6": edit_model, "7": edit_echo, "8": edit_activation,
    }
    while True:
        print("\n" + "═" * 64)
        print("  claude-call · config")
        print("  " + _summary(cfg))
        print("═" * 64)
        print("  1) Language          5) Style")
        print("  2) Voice provider    6) Brain model")
        print("  3) Voice             7) Audio / echo")
        print("  4) Speaking rate     8) Activation")
        print("  s) Save & exit       q) Quit without saving")
        sel = ask("  > ")
        if sel is None or sel == "q":
            print("  (no changes saved)")
            return
        if sel == "s":
            save(cfg)
            return
        fn = actions.get(sel)
        if fn:
            fn(cfg)


if __name__ == "__main__":
    main()
