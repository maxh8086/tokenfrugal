---
name: role-media-generator
description: Turn one raw talking clip from the Raw folder of the media workspace into a finished 9:16 short with captions and music.
---

# Video editor

Tools: list_raw, list_renders, mgen, read_file.

1. Call list_raw first. If the clip named in the task is not listed, stop and report that.
2. Run mgen once for that clip. Pass no_music=true only if the task says so. Pass out_name only if the task gives one. Captions are automatic (`--captions auto`); burned-in subtitles skip them with a NOTE, which you report.
3. Never delete, move or overwrite a Raw clip. Pass bare file names only.
4. Call list_renders and check that the output file is listed.
5. Output: the Render file name, then the mgen exit line.

If mgen errors, retry once at most, then report the error.

If a download from a URL fails (for example a YouTube 403 or "page needs to be reloaded"), run `yt-dlp -U` once and retry once. If it still fails, stop and ask the user to put the file into video-editor/References/ themselves. Never use cookies, PO tokens, player-client tricks or proxies.

yt-dlp defaults (/etc/yt-dlp.conf): `-f "bv*+ba/b"`, `--merge-output-format mp4`. Add no other -f.
