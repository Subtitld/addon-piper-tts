# Piper TTS add-on for Subtitld

Lightweight neural TTS based on [Piper](https://github.com/OHF-voice/piper1-gpl)
(the GPL-3 successor to the original `rhasspy/piper`). Runs entirely offline
on CPU.

## Voices

**177 voices in 59 languages**: every voice in
[rhasspy/piper-voices](https://huggingface.co/rhasspy/piper-voices) that this
build can speak, plus five curated community voices (below). Each downloads
on first use (20–130 MB) into `models/`.

26 of them hold several speakers, 2,801 in all: `en_GB-vctk-medium` has 109,
`en_US-libritts_r-medium` 904, `de_DE-mls-medium` 236,
`de_DE-thorsten_emotional-medium` one per emotion. Their manifest entries list
the speakers, Subtitld shows them as "Speaker in this voice" next to the voice,
and the request carries the choice as `voice_speaker` (a name from the model's
`speaker_id_map`). Without one, Piper uses the model's `default_speaker_id`,
which the manifest lists first (marked "recommended" when it isn't speaker 0).

Left out, because their phoneme type needs more than piper-tts 1.8.0 alone:

| Voices | Needs |
|--------|-------|
| `ja_JP-hi_fi_captain-medium` | `piper-tts[ja]`: pyopenjtalk-plus + sudachidict, ~110 MB |
| `th_TH-tsync2-medium` | `piper-tts[th]`: tltk, with scikit-learn, gensim and pandas |
| `zh_CN-chaowen-medium`, `zh_CN-xiao_ya-medium` | `piper-tts[zh]`: g2pW + transformers |
| `lt_LT-ingute-medium`, `lt_LT-reginute1-medium` | a `lithuanian` phoneme type piper-tts 1.8.0 does not know |

## Community voices

Picked from [PiperHub](https://piperhub.org)'s catalogue, which also lists
hundreds of voices this add-on leaves out: copies of the official ones, voices
of game characters and celebrities, non-commercial licences, and voices with no
stated licence or training data. A community voice gets in only when its model
card states a licence that allows commercial use, names its training data with
that data's own licence, and it synthesizes through piper-tts 1.8.0. Each is
pinned to a Hugging Face revision, and the add-on rejects a model whose sha256
differs from the one recorded. Display names end in "community".

| Voice | Language | Licence | Credit |
|-------|----------|---------|--------|
| `ta_IN-rasa_female-medium`, `ta_IN-rasa_male-medium` | Tamil | CC BY 4.0 | [tinisoft](https://huggingface.co/tinisoft/piper-ta_IN-rasa_female-medium), trained on [AI4Bharat Rasa](https://huggingface.co/datasets/ai4bharat/Rasa) |
| `si_LK-chan4lk-medium` | Sinhala | MIT (model), CC BY-SA 4.0 (data) | [chan4lk](https://huggingface.co/chan4lk/piper-tts-sinhala), trained on Google's Sinhala corpus, [OpenSLR 30](https://www.openslr.org/30/) |
| `ku-kurmanci-medium` (90 speakers) | Kurmanji Kurdish | MIT (model), CC0 (data) | [atenax](https://huggingface.co/atenax/kurmanci-tts-piper), trained on Mozilla Common Voice ([atenax/kmr_tts](https://huggingface.co/datasets/atenax/kmr_tts)) |
| `kn_IN-syspin_male-medium` | Kannada | CC BY 4.0 (data), from the lessac checkpoint | [micahchoo](https://huggingface.co/micahchoo/piper-kn), trained on [SYSPIN](https://syspin.iisc.ac.in/datasets), IISc Bengaluru |

The Kannada voice starts from the same Blizzard 2013 Lessac checkpoint as the
official `en_US-lessac` voices, and carries its terms the same way. Its author
measures it a little rough (UTMOS 3.2 against 3.8 for the real recordings).

To add one, put it in `tools/community_voices.json` with its revision, then
regenerate.

## Regenerating the list

The voice list is generated, never hand-edited:

```bash
python tools/regen_voices.py           # rebuild from voices.json + community_voices.json
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
