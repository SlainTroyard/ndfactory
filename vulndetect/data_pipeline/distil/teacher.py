# vulndetect/data_pipeline/distil/teacher.py
"""Teacher model API wrapper — generates security audit reasoning chains via Claude.

Provides a TeacherClient class that wraps the Anthropic Python SDK with retry
logic, rate limiting, and batch concurrency support.
"""
import os
import time
import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


def estimate_tokens(text: str) -> int:
    """Rough token count estimate (4 chars ≈ 1 token)."""
    return max(1, len(text) // 4)


class TeacherClient:
    """Wrapper around Anthropic Claude API for security audit generation.

    Gracefully degrades when ANTHROPIC_API_KEY is not set: client is None
    and generate_analysis returns None instead of raising.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "claude-opus-4-20250514",
    ):
        """Initialize the teacher client.

        Args:
            api_key: Anthropic API key. If None, reads from ANTHROPIC_API_KEY env var.
            model: Claude model ID to use for generation.
        """
        self.model = model
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_calls = 0

        key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            logger.warning("ANTHROPIC_API_KEY not set; teacher calls will be skipped")
            self.client = None
            return

        try:
            import anthropic
            self.client = anthropic.Anthropic(api_key=key)
            logger.info("TeacherClient initialized with model=%s", self.model)
        except ImportError:
            logger.warning("anthropic package not installed; teacher calls will be skipped. "
                           "Install with: pip install anthropic")
            self.client = None

    def _is_available(self) -> bool:
        """Check if the client is ready for API calls."""
        return self.client is not None

    def generate_analysis(
        self,
        code_snippet: str,
        language: str = "",
        is_safe: bool = False,
        max_retries: int = 3,
    ) -> Optional[str]:
        """Generate a security audit analysis for a single code snippet.

        Args:
            code_snippet: The source code to analyze.
            language: Programming language of the code.
            is_safe: If True, use the safe-code prompt variant.
            max_retries: Number of retry attempts on API errors.

        Returns:
            The teacher model's analysis text, or None if unavailable or all retries exhausted.
        """
        if not self._is_available():
            logger.debug("TeacherClient unavailable, skipping analysis")
            return None

        # Lazy import prompts to avoid circular dependency at module level
        from vulndetect.data_pipeline.distil.prompts import (
            SECURITY_AUDIT_PROMPT,
            SECURITY_AUDIT_PROMPT_SAFE,
            TEACHER_SYSTEM_PROMPT,
        )

        prompt_template = SECURITY_AUDIT_PROMPT_SAFE if is_safe else SECURITY_AUDIT_PROMPT
        user_message = prompt_template.format(
            code_snippet=code_snippet,
            language=language or "unknown",
        )

        last_error = None
        for attempt in range(max_retries):
            try:
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=4096,
                    system=TEACHER_SYSTEM_PROMPT,
                    messages=[{"role": "user", "content": user_message}],
                )

                # Extract text from response
                output_text = ""
                for block in response.content:
                    if hasattr(block, "text"):
                        output_text += block.text

                # Track token usage
                input_tokens = getattr(response.usage, "input_tokens", 0) if hasattr(response, "usage") else 0
                output_tokens = getattr(response.usage, "output_tokens", 0) if hasattr(response, "usage") else estimate_tokens(output_text)
                self.total_input_tokens += input_tokens
                self.total_output_tokens += output_tokens
                self.total_calls += 1

                logger.debug("Analysis generated: %d input tokens, %d output tokens",
                             input_tokens, output_tokens)
                return output_text

            except Exception as e:
                last_error = e
                wait = 2 ** attempt  # 1s, 2s, 4s
                logger.warning("Teacher API error (attempt %d/%d): %s — retrying in %ds",
                               attempt + 1, max_retries, e, wait)
                time.sleep(wait)

        logger.error("Teacher API failed after %d retries: %s", max_retries, last_error)
        return None

    def generate_batch(
        self,
        samples: List[Dict],
        max_concurrent: int = 5,
    ) -> List[Dict]:
        """Generate analyses for a batch of code samples concurrently.

        Args:
            samples: List of dicts, each with at least:
                id: str,
                vulnerable_code: str (or code_snippet: str),
                language: str,
                is_safe: bool (optional, default False).
            max_concurrent: Maximum concurrent API calls.

        Returns:
            The same list of dicts, with teacher_output and teacher_tokens
            fields added to each sample.
        """
        if not self._is_available():
            logger.warning("TeacherClient unavailable, returning samples without analysis")
            for sample in samples:
                sample["teacher_output"] = None
                sample["teacher_tokens"] = 0
            return samples

        from concurrent.futures import ThreadPoolExecutor, as_completed

        logger.info("Generating analyses for %d samples (max_concurrent=%d)",
                    len(samples), max_concurrent)

        def _process_one(sample):
            code = sample.get("vulnerable_code") or sample.get("code_snippet", "")
            language = sample.get("language", "")
            is_safe = sample.get("is_safe", False)

            output = self.generate_analysis(code, language=language, is_safe=is_safe)
            sample["teacher_output"] = output
            sample["teacher_tokens"] = estimate_tokens(output) if output else 0
            return sample

        results = []
        with ThreadPoolExecutor(max_workers=max_concurrent) as executor:
            futures = {executor.submit(_process_one, s): i for i, s in enumerate(samples)}
            for future in as_completed(futures):
                try:
                    result = future.result()
                    results.append((futures[future], result))
                except Exception as e:
                    idx = futures[future]
                    logger.error("Sample %s failed: %s", samples[idx].get("id", idx), e)
                    samples[idx]["teacher_output"] = None
                    samples[idx]["teacher_tokens"] = 0
                    results.append((idx, samples[idx]))

        # Re-sort by original index
        results.sort(key=lambda x: x[0])
        ordered = [r[1] for r in results]

        succeeded = sum(1 for s in ordered if s.get("teacher_output"))
        logger.info("Batch complete: %d/%d succeeded, total tokens: %d input + %d output",
                    succeeded, len(ordered), self.total_input_tokens, self.total_output_tokens)
        return ordered

    def get_usage(self) -> Dict:
        """Return cumulative token usage statistics."""
        return {
            "total_calls": self.total_calls,
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "estimated_cost_usd": round(
                self.total_input_tokens / 1_000_000 * 15 +
                self.total_output_tokens / 1_000_000 * 75,
                2,
            ),
        }
