# Triuna Labs Research

[![tests](https://github.com/TriunaLabs/research/actions/workflows/tests.yml/badge.svg)](https://github.com/TriunaLabs/research/actions/workflows/tests.yml)

Research notes and articles from [Triuna Labs](https://triunalabs.com), published with the code and data behind them, so the claims can be checked.

Where an article includes measurements, the repository contains the scripts that produced them and the raw results. Reproduction instructions live alongside each article.

## Articles

| Article | Author | Published | Summary | Reproducible code |
| --- | --- | --- | --- | --- |
| [Route the Work, Not Just the Data: GPUs, CPUs, and the Rise of AI-Native SSDs](articles/ai-native-ssd/) | Paul Woll | 2026-08-18 | AI is dissolving the boundary between storage and compute. From today's SSD-backed KV-cache tiers to a proposed five-plane AI-native storage architecture, with a laptop-reproducible measurement of the data-movement waste it targets. | [benchmark](articles/ai-native-ssd/benchmark/) |
| [Sixty-five bytes: prompt caching and the shape of project state](articles/prefix-caching-project-state/) | Paul Woll | 2026-10-02 | A 51 KB project record was handed to a model twice, with one accepted change between. Sixty-five bytes were reusable as a cached prefix, because prompt caches match from the start and the revision number sits near the top. Reordering the same information by how fast it changes took that to 51.8%. | [tool and sample](articles/prefix-caching-project-state/) |

## Observations

Field notes from real working sessions: qualitative, abstracted, and published so that
reasoning they later support has a visible origin. Unlike articles, they ship with no
code, and each states plainly what it does and does not support.

| Observation | Date | Subject |
| --- | --- | --- |
| [Crossing a context boundary](observations/2026-09-03-context-boundaries/) | 2026-09-03 | What a compaction summary preserves, what it drops, and two failure modes that are not about memory at all |

## Licensing

- **Articles and prose** (Markdown content under `articles/`): [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/): share and adapt with attribution.
- **Code** (scripts, benchmarks): [MIT](LICENSE).

## About

Triuna Labs builds measured, evidence-first software. More at [triunalabs.com](https://triunalabs.com).
