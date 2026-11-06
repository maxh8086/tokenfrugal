# Dhvani service consolidation

Name: dhvani (ध्वनि). Use dhvani in code and paths; ध्वनि is the display name.

## 1. Purpose

This design removes Piper from the media-generator and replaces it with HTTP calls to the existing Kokoro voice container, which is renamed to a `dhvani` service. It also separates the overloaded word "voice" into clear terms, and keeps the cloned-voice install in the image but unwired.

## 2. Components to remove or replace

| # | Component | Where it lives | Action | Replacement | Risk of change |
| --- | --- | --- | --- | --- | --- |
| 1 | Piper install block (piper-tts 1.8.0 in /opt/voice venv, en_US-lessac-medium at PIPER_VOICE_REV, `piper --help` check) | docker/media-generator/Dockerfile lines 93-109 | REMOVE | None; dhvani runs in its own container | Low: check no other build step uses /opt/voice |
| 2 | PIPER_BIN and PIPER_MODEL | docker/media-generator/render-engine/server.js lines 29-30 | REMOVE | DHVANI_URL | Low |
| 3 | Piper call, one clip per scene | server.js line 149 | REPLACE | HTTP POST to DHVANI_URL/api/kokoro/speak, save the mono 16-bit WAV, measure its length | Medium: scene timing depends on WAV length; text over 1000 characters must be split |
| 4 | PIPER_MODEL env var | docker-compose.yml line 51 | REPLACE | DHVANI_URL pointing at the dhvani service | Low |
| 5 | Docstring "narration = offline Piper" | router/media_generator_mcp.py line 242 | REPLACE | Narration via the dhvani service | Low |
| 6 | Piper rows and sentences | docs/designs/media-generator-pdf-feasibility.md (find with Grep "Piper") | REPLACE | dhvani service wording | Low |
| 7 | Piper row 5 | docs/designs/media-generator-pdf-ideas-and-code.md, Section B | REPLACE | dhvani service wording | Low |
| 8 | Piper sentences | same file, Section F | REPLACE | dhvani service wording | Low |
| 9 | Piper sentences | same file, Section G | REPLACE | dhvani service wording | Low |
| 10 | Row 8 (narration engine) | docs/designs/media-generator-missing-sections.md | REPLACE | dhvani service | Low |
| 11 | Decision 2 (licence check) | same file | REPLACE | Licence check moves to Kokoro and espeak-ng, the phonemizer dependency; espeak-ng is GPL-3.0 per the brief, licence terms to check | Medium: licence not yet checked |
| 12 | Piper reference | docs/designs/media-generator-render-engine.md line 137 | REPLACE | dhvani service | Low |
| 13 | Container folder and files | docker/voice/ | RENAME | docker/dhvani/ | Medium: Dockerfile, pin and compose paths change |
| 14 | Pin file and update script | docker/voice/voice.pin; scripts/update_voice_pin.py | RENAME | dhvani.pin; update_dhvani_pin.py | Medium: pin must be re-resolved after rename |

## 3. Components to keep

- **Kokoro engine** (`/api/kokoro/speak`, `/api/kokoro/voices`): keep. It is the core of the dhvani service.
- **Voice profile store and consent check** (record or upload a clip with a consent note, stored in /work/voices): keep. Unused until cloning is wired.
- **OpenVoice and MeloTTS install**: keep, mark as not wired (`POST /api/speak` returns 501). Decide later whether to remove this 1 GB-plus install from the image.
- **Role voice-artist**: recommend keep the name, because it manages speaker profiles, not the container. Files it touches if renamed: router/tf-roles.yaml, router/skills/role-voice-artist/SKILL.md, docs/designs/voice-artist-profile.md.

## 4. Suggested name

The name is `dhvani` (ध्वनि, meaning sound). Use `dhvani` for the container, folder docker/dhvani, image repo maxh8086/dhvani, env var DHVANI_URL, pin file dhvani.pin and script update_dhvani_pin.py.

Reason: "voice" currently means four things (the container, a speaker profile, the voice-artist role, and Piper's voice file). "Dhvani" covers synthesis and is neutral. Keep "voice profile" for a speaker clip with consent, and "voice model" for a TTS model file.

The name was chosen by the user; the rejected alternatives are dropped.

Renaming changes the pinned image name, so the pin must be re-resolved after the rename. The old image name must keep working until the render engine points at the new one.

## 5. Rename steps, in order

1. Rename docker/voice to docker/dhvani, including its files. Keep the Kokoro code unchanged.
2. Build and publish maxh8086/dhvani. Leave maxh8086/voice published until step 6.
3. Rename voice.pin to dhvani.pin and scripts/update_voice_pin.py to update_dhvani_pin.py. Re-resolve the digest from the new image.
4. Update docker-compose.yml: add DHVANI_URL and remove PIPER_MODEL.
5. Update the media-generator: remove the Piper block in the Dockerfile (lines 93-109) and lines 29-30 of server.js; change line 149 to POST to DHVANI_URL.
6. Point the render engine at maxh8086/dhvani, then retire the old image name.
7. Update the role and design docs listed in section 2 (rows 5-12), and the voice-artist files if the role is renamed.
8. Run the offline suite with `.venv/Scripts/python.exe -m unittest discover -s tests -t . -q`. tests/test_voice_kokoro_speak.py and tests/test_preflight.py reference the voice folder. Grep both for "docker/voice", "voice.pin" and "update_voice_pin" and update those strings. The affected test names are not listed here and must be read from the files before the change.

## 6. Decisions for the user

1. Approve the name dhvani (ध्वनि) for the container, folder, image and DHVANI_URL?
2. Remove OpenVoice and MeloTTS from the image now, or later?
3. Keep the voice-artist role name, or rename it?
4. Accept the espeak-ng GPL terms after checking them?
5. Approve splitting scene text longer than 1000 characters into several Kokoro requests?
