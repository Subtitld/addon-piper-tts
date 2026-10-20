# Piper TTS add-on for Subtitld

Lightweight neural TTS based on [Piper](https://github.com/OHF-voice/piper1-gpl)
(the GPL-3 successor to the original `rhasspy/piper`). Runs entirely offline
on CPU.

## Voices

**172 voices in 55 languages**, every voice in
[rhasspy/piper-voices](https://huggingface.co/rhasspy/piper-voices) that this
build can speak. Each downloads on first use (20–130 MB) into `models/`.

25 of them hold several speakers, 2,707 in all: `en_GB-vctk-medium` has 109,
`en_US-libritts_r-medium` 904, `de_DE-mls-medium` 236,
`de_DE-thorsten_emotional-medium` one per emotion. Their manifest entries list
the speakers, Subtitld shows them as "Speaker in this voice" next to the voice,
and the request carries the choice as `voice_speaker` (a name from the model's
`speaker_id_map`). Without one, Piper uses the model's first speaker.

Left out, because their phoneme type needs more than piper-tts 1.8.0 alone:

| Voices | Needs |
|--------|-------|
| `ja_JP-hi_fi_captain-medium` | `piper-tts[ja]`: pyopenjtalk-plus + sudachidict, ~110 MB |
| `th_TH-tsync2-medium` | `piper-tts[th]`: tltk, with scikit-learn, gensim and pandas |
| `zh_CN-chaowen-medium`, `zh_CN-xiao_ya-medium` | `piper-tts[zh]`: g2pW + transformers |
| `lt_LT-ingute-medium`, `lt_LT-reginute1-medium` | a `lithuanian` phoneme type piper-tts 1.8.0 does not know |

The voice list is generated, never hand-edited:

```bash
python tools/regen_voices.py           # rebuild from upstream voices.json
python tools/regen_voices.py --check   # exit 1 if manifest.json is stale
```

## Building

```bash
pip install piper-tts==1.8.0 pyinstaller
pyinstaller piper-addon.spec --distpath dist/
```

Releases are cut by `.github/workflows/release.yml` on a `vYY.MM.N` tag.

The resulting zip is what users (or the Subtitld catalog) install.

## Layout (post-install)

```
~/.local/share/subtitld/addons/piper-tts/
├── manifest.json
├── bin/piper-addon       # PyInstaller binary entry point
├── lib/...               # frozen Python + Piper deps
├── models/<voice>.onnx   # downloaded on first use of each voice
└── README.md
```

## Protocol

The host (Subtitld) speaks JSON-line frames over our stdin/stdout. See
`subtitld.modules.addons.protocol` for the wire spec. We support exactly one
task: `tts.synthesize`.

## License

The add-on glue (this repository's code) is MIT. Piper itself is now
GPL-3.0-or-later — the python wrapper we link against ships under that
license, which is fine because we invoke it as a separate process rather
than statically linking. Each downloaded voice has its own license —
most are CC-BY but some are CC0 or custom — listed at
<https://github.com/OHF-voice/piper1-gpl/blob/main/docs/VOICES.md>.
