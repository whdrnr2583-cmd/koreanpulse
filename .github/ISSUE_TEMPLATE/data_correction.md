---
name: Data correction (DART / news / classification)
about: A filing, holder classification, or news translation looks wrong
title: "[data] "
labels: data
---

## What's wrong

<!-- One sentence. Which filing, holder, news headline. -->

## Where you saw it

- URL: <!-- e.g. https://koreanpulse.dev/today.json or specific filing receipt_no -->
- Date: <!-- 2026-MM-DD -->
- Tool / feed: [track_korean_filings / monitor_foreign_holders / monitor_activist_investors / search_korean_industry_news / /today]

## What it should say

## Source backing

<!-- Link to the DART filing, news article, or other primary source that supports the correction. -->

## Severity

- [ ] Wrong English company name (e.g. "Samsung Electronics" → wrong English form)
- [ ] Wrong holder classification (passive / activist mislabel)
- [ ] Wrong industry tag
- [ ] Wrong filing date / receipt number
- [ ] Translation accuracy issue
- [ ] Other:

## koreanpulse maintainer notes (do not edit)

DART data is upstream-driven; we don't edit the source filings. We can fix:
- our English company-name cache (immediately, KV write)
- our holder allowlist classification (allowlist update + deploy)
- our industry RSS classification (rule update)
- our translation cache for a specific Korean text (KV invalidate + retranslate)

We cannot change DART filing content or news source content.
