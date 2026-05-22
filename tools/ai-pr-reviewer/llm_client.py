from openai import OpenAI

from config import (
    MODEL,
    MAX_CALLS_PER_RUN,
    MAX_OUTPUT_TOKENS,
    REQUEST_TIMEOUT_SECONDS,
)

from output_validator import validate_review_output
from prompt_loader import load_prompt
from review_contract import REVIEW_OUTPUT_SCHEMA, ReviewOutput, SanitizedReviewInput
from sanitizer import render_review_input

client = OpenAI(timeout=REQUEST_TIMEOUT_SECONDS)
_calls_this_run = 0


def call_llm(prompt_name: str, review_input: SanitizedReviewInput) -> ReviewOutput:
    global _calls_this_run
    if _calls_this_run >= MAX_CALLS_PER_RUN:
        raise RuntimeError(f"LLM call limit reached for this run: {MAX_CALLS_PER_RUN}")
    _calls_this_run += 1

    system_prompt = load_prompt(prompt_name)

    response = client.responses.create(
        model=MODEL,
        instructions=system_prompt,
        input=render_review_input(review_input),
        max_output_tokens=MAX_OUTPUT_TOKENS,
        text={
            "format": {
                "type": "json_schema",
                "name": "pr_review",
                "strict": True,
                "schema": REVIEW_OUTPUT_SCHEMA,
            }
        },
    )

    return validate_review_output(response.output_text)
