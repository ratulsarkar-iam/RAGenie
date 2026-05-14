# Summarisation Specification

## Overview

The Summariser generates concise, abstractive summaries for stored articles using RAGenie's existing Ollama LLM via the `LangChainLLM` wrapper. No additional model downloads or external services are required. Summarisation runs automatically after each fetch (when `config.news.summarise_on_fetch=true`) and can also be triggered on demand per article via the API.

## Design Decisions

| Decision | Choice | Reason |
|---|---|---|
| Model | Existing Ollama LLM (configured in `config.llm`) | No new dependencies; uses the already-running model |
| Approach | Abstractive (prompt-based) | Better than extractive for concise, readable summaries |
| Execution | Synchronous, sequential (one article at a time) | Ollama is single-threaded; async batching adds no benefit |
| Failure mode | Store `"[Summary unavailable]"` | Keeps the UI functional even if LLM fails |

## Summariser Interface

```python
class Summariser:
    def __init__(self, llm_wrapper: LangChainLLM, max_content_chars: int = 8000): ...

    def summarise(self, article: Article) -> str:
        """
        Generate a summary for a single article.
        Returns the summary string or "[Summary unavailable]" on failure.
        """

    def summarise_pending(self, article_store: ArticleStore, limit: int = 50) -> SummarisationResult:
        """
        Batch-process all articles where is_summarised=0.
        Returns a result object with counts.
        """

@dataclass
class SummarisationResult:
    succeeded: int
    failed: int
    skipped: int   # Already summarised
```

## Prompt Template

```
You are a concise news summariser.

Read the article below and write a 3-5 sentence abstractive summary.
Focus on: who, what, when, where, and why.
Do NOT add your own opinions or commentary.
Do NOT mention that you are summarising.
Write in plain, clear English.

=== ARTICLE ===
{content}
=== END ARTICLE ===

Summary:
```

The `{content}` placeholder is replaced with `article.content[:max_content_chars]` before the prompt is sent to the LLM.

## Summarisation Flow

```python
def summarise(self, article: Article) -> str:
    content = article.content[:self.max_content_chars]
    prompt = SUMMARISE_PROMPT.format(content=content)

    for attempt in range(2):          # 1 retry
        try:
            raw = self.llm_wrapper.generate(prompt)
            summary = raw.strip()
            if summary:
                return summary
        except Exception as e:
            logger.warning(f"Summarisation attempt {attempt+1} failed: {e}")

    return "[Summary unavailable]"    # Fallback after 2 failures
```

## Batch Summarisation

```python
def summarise_pending(self, article_store: ArticleStore, limit: int = 50) -> SummarisationResult:
    pending = article_store.list_pending_summarisation(limit=limit)
    succeeded = failed = 0

    for article in pending:
        summary = self.summarise(article)
        model_name = self.llm_wrapper.model_name  # e.g. "deepseek-r1:1.5b"
        if summary != "[Summary unavailable]":
            article_store.save_summary(article.id, summary, model_name)
            succeeded += 1
        else:
            # Still save the fallback so we don't retry endlessly
            article_store.save_summary(article.id, summary, model_name)
            failed += 1

    return SummarisationResult(succeeded=succeeded, failed=failed, skipped=0)
```

## On-Demand Re-Summarisation

`POST /api/news/{article_id}/summarize` clears the existing summary (`is_summarised=0`), then calls `Summariser.summarise(article)` and stores the result. This allows users to regenerate a summary if the initial attempt failed or the LLM model has been upgraded.

## Configuration

```yaml
news:
  summarise_on_fetch: true      # Trigger batch summarisation after each fetch job
  max_content_chars: 8000       # Truncate article body before summarising
  summary_max_sentences: 5      # Informational; enforced via prompt wording
```

## Integration with NewsService

```python
# Inside NewsService.run_for_keyword():
fetch_result = self.fetcher.fetch(keyword.term, ...)
process_result = self.processor.process(fetch_result, keyword)

if self.config.news.summarise_on_fetch:
    self.summariser.summarise_pending(self.article_store)
```

## Testing Strategy

### Unit Tests (`tests/test_news_summariser.py`)
All tests mock `LangChainLLM.generate`.

- Successful generate returns clean summary, calls `article_store.save_summary`.
- LLM raises `Exception` on first attempt → retried once → second success returns summary.
- LLM fails both attempts → `"[Summary unavailable]"` stored.
- `summarise_pending` processes all `is_summarised=0` articles.
- `summarise_pending` stops after `limit` articles.
- Model name is stored correctly in the summary record.
- Empty LLM response (whitespace only) treated as failure → retry.
