"""LLM-based article summariser."""
from dataclasses import dataclass
from typing import TYPE_CHECKING

from ..core.logging_config import get_logger
from .models import Article
from .article_store import ArticleStore

if TYPE_CHECKING:
    from ..llm.langchain_wrapper import LangChainLLM

logger = get_logger(__name__)

_UNAVAILABLE = "[Summary unavailable]"

_SUGGEST_PROMPT = """\
You are a news search keyword optimizer for a news aggregation system.

The user wants to track news about: "{description}"

Rules:
- Generate a concise, specific search keyword or phrase (2-6 words)
- If the user gave multiple topics with "," or "+", combine them into one focused term OR pick the primary topic
- Strip filler like "news about", "latest", "updates on", "I want to see"
- Prefer specific named entities over generic descriptions

Respond with EXACTLY this format (no extra text):
TERM: <your search keyword>
EXPLANATION: <one sentence on why this term captures the user's intent>
"""

_TRANSLATE_PROMPT = """\
You are a professional translator specializing in news content.

Translate the following news summary into {target_language}.

Rules:
- Preserve the meaning, tone, and factual accuracy
- Use natural, fluent {target_language}
- Do NOT add commentary or explanations
- Output ONLY the translated text, nothing else

=== ORIGINAL SUMMARY ===
{summary}
=== END ===

Translation:"""

_PROMPT = """\
You are a concise news summariser that works in any language.

Read the article below and write a 3-5 sentence abstractive summary.
Focus on: who, what, when, where, and why.
Do NOT add your own opinions or commentary.
Do NOT mention that you are summarising.
IMPORTANT: Write the summary in the SAME language as the article.
If the article is in Hindi, summarise in Hindi.
If the article is in Tamil, summarise in Tamil.
If the article is in Bengali, summarise in Bengali.
If the article is in English, summarise in English.
Do NOT translate to English.

=== ARTICLE ===
{content}
=== END ARTICLE ===

Summary:"""


@dataclass
class SummarisationResult:
    succeeded: int = 0
    failed: int = 0
    skipped: int = 0


class Summariser:
    def __init__(self, llm_wrapper: "LangChainLLM", max_content_chars: int = 8000):
        self._llm = llm_wrapper
        self._max_chars = max_content_chars

    def summarise(self, article: Article) -> str:
        content = article.content[: self._max_chars]
        prompt = _PROMPT.format(content=content)
        for attempt in range(2):
            try:
                raw = self._llm.generate(prompt)
                summary = (raw or "").strip()
                if summary:
                    return summary
            except Exception as e:
                logger.warning(f"Summarisation attempt {attempt + 1} failed for {article.id}: {e}")
        logger.error(f"Both summarisation attempts failed for article {article.id}")
        return _UNAVAILABLE

    def suggest_keyword(self, description: str) -> dict:
        """Use LLM to turn a natural-language description into a news search keyword."""
        prompt = _SUGGEST_PROMPT.format(description=description.strip())
        try:
            raw = (self._llm.generate(prompt) or "").strip()
            term, explanation = "", ""
            for line in raw.splitlines():
                if line.startswith("TERM:"):
                    term = line[5:].strip()
                elif line.startswith("EXPLANATION:"):
                    explanation = line[12:].strip()
            if not term:
                term = description.strip()
            return {"term": term, "explanation": explanation}
        except Exception as e:
            logger.warning(f"Keyword suggestion failed: {e}")
            return {"term": description.strip(), "explanation": ""}

    def translate_summary(self, summary: str, target_language: str) -> str:
        """Translate a summary to the target language using LLM."""
        if not summary or not target_language:
            return summary
        prompt = _TRANSLATE_PROMPT.format(summary=summary, target_language=target_language)
        try:
            translated = (self._llm.generate(prompt) or "").strip()
            return translated if translated else summary
        except Exception as e:
            logger.warning(f"Translation to {target_language} failed: {e}")
            return summary

    def summarise_pending(self, article_store: ArticleStore, limit: int = 50) -> SummarisationResult:
        pending = article_store.list_pending_summarisation(limit=limit)
        result = SummarisationResult()
        model_name = getattr(self._llm.config, "model_name", "unknown")
        for article in pending:
            summary = self.summarise(article)
            article_store.save_summary(article.id, summary, model_name)
            if summary == _UNAVAILABLE:
                result.failed += 1
            else:
                result.succeeded += 1
        logger.info(
            f"Summarisation batch: {result.succeeded} OK, {result.failed} failed out of {len(pending)}"
        )
        return result
