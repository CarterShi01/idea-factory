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
