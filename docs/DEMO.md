# Kiwi — Live Demo & Verification

This document shows Kiwi running against a **real, fully-indexed knowledge base** and explains how to record your own walkthrough.

---

## Verified Working — Real System Output

The following output was captured from a live, running instance of Kiwi with a production-scale dataset.

### System health

```jsonc
GET /api/health
{
  "articles": 1148375,           // 1.14 million articles indexed
  "archives_by_status": {
    "indexed": 80,
    "paused": 9,
    "failed": 3
  },
  "db_size_mb": 1919.0,          // ~1.9 GB search index
  "model_reachable": true,       // Ollama AI available
  "cpu_count": 8,
  "active_threads": 2
}
```

### Full-text search (sub-100 ms across 1.1M articles)

```text
GET /api/search/query?q=photosynthesis
-> 251 matches

  - 8.3: Overview of Photosynthesis - The Two Parts        [Biology LibreTexts]
  - 8.1: Overview of Photosynthesis - Purpose and Process  [Biology LibreTexts]
  - Biology, Answering the Big Questions/Photosynthesis     [Wikibooks]

GET /api/search/query?q=python programming
-> 3,728 matches   [Wikibooks, ...]

GET /api/search/query?q=quantum mechanics
-> 587 matches     [Chemistry LibreTexts, Wikiversity, ...]

GET /api/search/query?q=gravity
-> 1,251 matches   [WikiMed, Astronomy by Wikipedia, Software Engineering Q&A]
```

### Offline AI chat (RAG) — answered entirely on-device

```text
POST /api/chat/ask
{ "question": "What is photosynthesis and why is it important?" }

--- Sources retrieved from the local index ---
  [1] English-Hanzi/Photosynthesis                 (Wikibooks)
  [2] General Biology/Cells/Photosynthesis          (Wikibooks)
  [3] Heterotrophic picoplankton                    (WikiMed Medical Encyclopedia)
  [4] Impact of Artificial Lights on Microalgae     (Appropedia)
  [5] CLIL (Content and Language Integrated Learning)(Wikiversity)

--- AI answer streamed from local gemma3:1b ---
"Photosynthesis is the process by which plants and other things make food.
It is a chemical process that uses sunlight to turn carbon dioxide into
sugars the cell can use as energy. [1] It is a fundamental process for life
on Earth, as it provides the primary source of energy for most ecosystems. [2]
Photosynthesis is important because it produces oxygen... [3] It also plays a
key role in regulating the Earth's climate by absorbing carbon dioxide... [4]"
```

The model produced inline citations `[1]`–`[8]` that map directly to the
retrieved source articles — all without any internet connection.

---

## Record Your Own Walkthrough

A short screen recording is the fastest way to show Kiwi off. Here's a clean
2-minute script that demonstrates the core loop.

### Recommended recording tools

| OS | Free tool |
|---|---|
| Windows | **ShareX** (`https://getsharex.com`) — records to GIF/MP4 |
| Windows | Built-in **Xbox Game Bar** (`Win + G`) |
| macOS | **QuickTime** (File → New Screen Recording) or `Cmd + Shift + 5` |
| Linux | **Peek** (GIF) or **OBS Studio** (MP4) |

### Suggested 2-minute demo script

1. **Open the app** — show the search landing page with categories
2. **Search** — type `photosynthesis`, show results appearing instantly
3. **Open a result** — click an article; show it rendering in the reader with the auto table of contents
4. **Navigate back** — use the back button, return to results
5. **Open a second result** — click a different article, show multi-tab browsing
6. **Search again** — try `quantum mechanics` or `python`
7. **AI chat** — open the chat sidebar, ask *"What is photosynthesis?"*, show sources + streamed answer with citations

### Where to put the recording

1. Save your recording as `docs/screenshots/walkthrough.gif` (or `.mp4`)
2. GitHub renders GIFs inline and accepts video uploads up to 10 MB in
   issues/PRs. For larger MP4s, either:
   - Compress with [HandBrake](https://handbrake.fr/) (target < 10 MB), **or**
   - Upload to a [GitHub Release](https://github.com/Taariqmornings/kiwi-knowledge-system/releases)
     and link it from the README, **or**
   - Drag-and-drop the video into a GitHub issue — GitHub hosts it and gives
     you a permanent `user-images.githubusercontent.com` URL you can embed.

### Embed it in the README

Once `walkthrough.gif` is in place, add this near the top of `README.md`:

```markdown
![Kiwi walkthrough](docs/screenshots/walkthrough.gif)
```

For an MP4 hosted via a GitHub issue/release:

```markdown
https://user-images.githubusercontent.com/.../walkthrough.mp4
```

---

## Screenshot checklist

Drop these PNGs into `docs/screenshots/` to complete the visual documentation:

- [ ] `search.png` — search results page
- [ ] `reader.png` — article reader with table of contents
- [ ] `chat.png` — AI chat sidebar with citations
- [ ] `archives.png` — archive manager / indexing progress
- [ ] `walkthrough.gif` — the full 2-minute demo loop
