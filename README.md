# grokfeed

Terminal feed reader for Hacker News and Reddit.

## Install

```bash
pip install -e .
```

## Run

```bash
grokfeed
```

## Keys

| Key | Action |
|-----|--------|
| `j` / `↓` | Move down |
| `k` / `↑` | Move up |
| `Enter` | Open story in browser |
| `r` | Refresh feed |
| `Tab` | Cycle source filter |
| `q` | Quit |

## Config

`~/.grokfeed/config.toml` — created on first run.

```toml
subreddits = ["programming", "python", "machinelearning"]
hn_story_count = 30
reddit_post_count = 15
```
