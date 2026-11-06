---
name: role-content-analyst-rss
description: Read the saved RSS feed list and write new items on a topic to a raw JSON file. Collect only.
---

# RSS collector

Tools: get_feed, read_file, write_file.

1. Read only feeds from the saved list (read_file on the feed list in the media folder).
2. get_feed for each feed. Keep items that match the topic, up to 5 per feed.
3. For each item keep: title, feed URL, item link, date.
4. Write content/trends/raw/<YYYY-MM-DD>-rss.json as a JSON list.

Every item needs a feed URL and a link from a tool result. Do not read feeds that are not on the list. Do not score.
Output: the file path, then the item count per feed.
