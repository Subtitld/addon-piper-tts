#!/usr/bin/env python3
"""Regenerate `manifest.json`'s `voices` and `languages` from rhasspy/piper-voices.

Upstream's `voices.json` is the authoritative list of what exists on the
voice host the add-on downloads from. Hand-maintaining a copy here is how the
manifest fell 19 voices behind and ended up with guessed sizes, so this script
rebuilds the list from it instead:

    python tools/regen_voices.py              # fetch voices.json + speaker maps
    python tools/regen_voices.py --check      # CI: fail if manifest is stale

Multi-speaker voices get a `speakers` list read from each voice's own
`.onnx.json` (`speaker_id_map`), the speaker Piper uses when none is asked for
(`default_speaker_id`, usually 0) first, then by index. Subtitld shows it as a
separate "Speaker in this voice" choice next to the voice. Voices whose
phoneme type this build has no front end for are left out
(`UNSUPPORTED_PHONEME_TYPES`).

Community voices, curated in `tools/community_voices.json`, are appended
after the official ones. Each is pinned to a Hugging Face revision; its
manifest entry carries the download URLs and the model's sha256 under
`source`, plus its `license` and `credit`.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MANIFEST = REPO_ROOT / 'manifest.json'
COMMUNITY = REPO_ROOT / 'tools' / 'community_voices.json'
VOICES_BASE = 'https://huggingface.co/rhasspy/piper-voices/resolve/main'

# Phoneme types this build cannot speak, read from each voice's own config so
# a new upstream voice of the same kind stays out too. Keep a reason with each,
# and drop the entry once the reason is gone.
UNSUPPORTED_PHONEME_TYPES = {
    # Not a PhonemeType in piper-tts 1.8.0: PiperConfig raises ValueError.
    'lithuanian': 'unknown to piper-tts 1.8.0',
    # piper-tts[ja]: pyopenjtalk-plus + sudachidict, ~110 MB of wheels for
    # one voice; not worth doubling every platform's download.
    'japanese': 'needs pyopenjtalk-plus + sudachidict (~110 MB)',
    # piper-tts[th]: tltk, which pulls scikit-learn, gensim and pandas.
    'thai': 'needs tltk (scikit-learn, gensim, pandas)',
    # piper-tts[zh]: g2pW + transformers. Today's Chinese voices are espeak.
    'pinyin': 'needs g2pW + transformers',
}


def _fetch_json(url: str, attempts: int = 3) -> dict:
    # Hugging Face's CDN occasionally stalls a read; one stall shouldn't
    # cost a 30-config run.
    for attempt in range(attempts):
        try:
            with urllib.request.urlopen(url, timeout=60) as resp:
                return json.load(resp)
        except (TimeoutError, OSError):
            if attempt == attempts - 1:
                raise
    raise AssertionError('unreachable')


def _display_name(entry: dict) -> str:
    lang = entry['language']
    name = ' '.join(w.capitalize() for w in entry['name'].split('_'))
    return f"{name} ({lang['name_english']}, {lang['country_english']}, {entry['quality']})"


def _config(entry: dict) -> dict:
    config_file = next(f for f in entry['files'] if f.endswith('.onnx.json'))
    return _fetch_json(f'{VOICES_BASE}/{urllib.parse.quote(config_file)}')


# Speaker names that are opaque hashes (Common Voice client ids, as in the
# Kurmanji voice) mean nothing in a list; those get "Speaker <index>".
_HASH_NAME = re.compile(r'^[0-9a-f]{32,}$')


def _speakers(config: dict) -> list[dict]:
    """Speaker names, the model's default first (Subtitld shows the first one
    as what you get without choosing, and the add-on then sends no speaker,
    so Piper falls back to `default_speaker_id`), the rest by index."""
    id_map = config.get('speaker_id_map') or {}
    default = config.get('default_speaker_id') or 0
    ordered = sorted(id_map.items(), key=lambda kv: (kv[1] != default, kv[1]))
    speakers = []
    for name, index in ordered:
        speaker = {'id': name}
        if _HASH_NAME.match(name):
            speaker['display_name'] = f'Speaker {index}'
        if index == default and default != 0:
            speaker['display_name'] = f"{speaker.get('display_name', name)} (recommended)"
        speakers.append(speaker)
    return speakers


def _community_voice(entry: dict) -> dict | None:
    """Manifest entry for a curated community voice, from its pinned revision."""
    repo, revision, model = entry['repo'], entry['revision'], entry['model']
    info = _fetch_json(f'https://huggingface.co/api/models/{repo}/revision/{revision}?blobs=true')
    files = {s['rfilename']: s for s in info['siblings']}
    config_file = entry.get('config', model + '.json')
    base = f'https://huggingface.co/{repo}/resolve/{revision}'
    config = _fetch_json(f'{base}/{urllib.parse.quote(config_file)}')
    phoneme_type = config.get('phoneme_type', 'espeak')
    if phoneme_type in UNSUPPORTED_PHONEME_TYPES:
        print(f"  skipped {entry['id']}: {phoneme_type}", file=sys.stderr)
        return None
    size = files[model]['size'] + files[config_file]['size']
    voice = {
        'id': entry['id'],
        'language': entry['language'],
        'display_name': entry['display_name'],
        'quality': entry['quality'],
        'size_mb': round(size / (1024 * 1024)),
        'source': {
            'model_url': f'{base}/{urllib.parse.quote(model)}',
            'config_url': f'{base}/{urllib.parse.quote(config_file)}',
            'sha256': files[model]['lfs']['sha256'],
        },
        'license': entry['license'],
        'credit': entry['credit'],
    }
    speakers = _speakers(config)
    if len(speakers) > 1:
        voice['speakers'] = speakers
    return voice


def build_voices(upstream: dict) -> list[dict]:
    with ThreadPoolExecutor(max_workers=16) as pool:
        configs = dict(zip(upstream, pool.map(_config, upstream.values())))

    voices = []
    for voice_id in sorted(upstream):
        entry, config = upstream[voice_id], configs[voice_id]
        phoneme_type = config.get('phoneme_type', 'espeak')
        if phoneme_type in UNSUPPORTED_PHONEME_TYPES:
            print(f'  skipped {voice_id}: {phoneme_type} '
                  f'({UNSUPPORTED_PHONEME_TYPES[phoneme_type]})', file=sys.stderr)
            continue
        size = sum(f['size_bytes'] for f in entry['files'].values())
        voice = {
            'id': voice_id,
            'language': entry['language']['code'].replace('_', '-').lower(),
            'display_name': _display_name(entry),
            'quality': entry['quality'],
            'size_mb': round(size / (1024 * 1024)),
        }
        speakers = _speakers(config)
        if len(speakers) > 1:
            voice['speakers'] = speakers
        voices.append(voice)

    curated = json.loads(COMMUNITY.read_text(encoding='utf-8'))['voices']
    with ThreadPoolExecutor(max_workers=8) as pool:
        community = [v for v in pool.map(_community_voice, curated) if v]
    clash = {v['id'] for v in community} & {v['id'] for v in voices}
    if clash:
        raise SystemExit(f'community voice ids clash with official ones: {sorted(clash)}')
    return voices + community


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--check', action='store_true',
                        help='exit 1 if manifest.json differs from upstream')
    args = parser.parse_args()

    upstream = _fetch_json(f'{VOICES_BASE}/voices.json')
    voices = build_voices(upstream)
    languages = sorted({v['language'] for v in voices})

    manifest = json.loads(MANIFEST.read_text(encoding='utf-8'))
    stale = manifest.get('voices') != voices or manifest.get('languages') != languages
    if args.check:
        if stale:
            print('manifest.json is stale; run tools/regen_voices.py', file=sys.stderr)
            return 1
        return 0

    manifest['voices'] = voices
    manifest['languages'] = languages
    MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + '\n',
                        encoding='utf-8')
    n_speakers = sum(len(v.get('speakers') or [1]) for v in voices)
    print(f'{len(voices)} voices, {n_speakers} speakers, {len(languages)} languages')
    return 0


if __name__ == '__main__':
    sys.exit(main())
