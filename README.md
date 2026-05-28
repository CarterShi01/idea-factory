# Idea Factory

Idea Factory is an information collection and idea generation project.

The early demo focuses on collecting product launch information, organizing it into structured records, and generating startup idea candidates for further review.

This project is designed to become a lightweight AI-agent-driven idea production pipeline over time.

## Demo: mock product-to-idea pipeline

The current demo runs entirely offline against a local sample file. It does
not call any external APIs.

### Install

```bash
pip install -e .
```

### Run

```bash
idea-factory
```

This reads `data/raw/sample_products.json`, normalizes the records, generates
mock idea candidates, and writes the results to:

- `data/processed/ideas.json`
- `data/processed/ideas.md`

You can point at a different input file or output directory:

```bash
idea-factory --input data/raw/sample_products.json --output-dir data/processed
```

The pipeline is also runnable as a module:

```bash
python -m idea_factory.cli
```

### Verify the install

To confirm the package is installed and importable, run the `hello` subcommand:

```bash
python -m idea_factory hello
```

It prints `Hello from idea-factory!` and exits 0. cooool.

## Collecting external signals (opt-in, network)

The `collect` subcommand fetches real external signals and is **separate from
the offline demo pipeline above** — the default `idea-factory` run never touches
the network. Sources:

- **Hacker News** — top stories via the public Firebase API.
- **Product Hunt** — top posts via the GraphQL API. Requires a developer token
  in `PRODUCT_HUNT_TOKEN` (a local `.env` is honoured). Without a token this
  source is skipped; the others still run.
- **Domestic startup news** — 36kr / 虎嗅 RSS feeds.

```bash
# Fetch up to 10 items per source, save to data/raw/collected.json,
# and flag which existing ideas each new signal may relate to.
idea-factory collect

# Tune volume / output location, or skip the idea matching:
idea-factory collect --limit 20 --output data/raw/collected.json --no-match
```

Each collected record carries a `source` field (its 灵感来源 / inspiration
source); ideas generated from a record inherit it as `inspiration_source`.

### Scheduling (default: once per day)

Run on an interval with the built-in standard-library scheduler:

```bash
idea-factory collect --schedule --interval-hours 24
```

Or drive it from `cron` (no long-running process) — e.g. daily at 08:00:

```cron
0 8 * * * cd /path/to/idea-factory && idea-factory collect >> collect.log 2>&1
```
