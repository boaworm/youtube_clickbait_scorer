"""Analyze YouTube videos for clickbait using an LLM."""

import os
import json
import re
from typing import Optional
from openai import OpenAI
from pydantic import BaseModel


class ClickbaitAnalysis(BaseModel):
    """Result of clickbait analysis."""

    is_clickbait: bool
    clickbait_score: int  # 0 to 100
    reasoning: str


def analyze_for_clickbait(
    title: str,
    description: str,
    transcript: Optional[str],
) -> ClickbaitAnalysis:
    """
    Analyze a YouTube video for clickbait.

    Compares what the title/thumbnail promises vs what the actual content delivers.
    """
    base_url = os.getenv("ANTHROPIC_BASE_URL", "https://www.thorburn.se/llama")
    model = os.getenv("ANTHROPIC_MODEL", "qwen-henrik")
    auth_token = os.getenv("ANTHROPIC_AUTH_TOKEN", "local-bypass")

    # Use OpenAI client for llama.cpp server compatibility
    client = OpenAI(base_url=base_url, api_key=auth_token)

    content_section = transcript if transcript else "No transcript available"

    system_prompt = """You are a YouTube clickbait detector. Your job is to analyze whether a video's title makes claims that the video content does not substantiate.

Key indicators of clickbait:
- Title makes a definitive claim (e.g., "Leak confirmed", "Breaking news") but the video only contains speculation or rumors
- Title promises revelation but content is vague or inconclusive
- Presenter presents guesses, rumors, or speculation as if they were facts
- Title uses sensational language not supported by the actual content

Be strict: if the title says "confirmed" but the video only speculates, that's clickbait."""

    user_prompt = f"""Analyze this YouTube video for clickbait.

TITLE: {title}

DESCRIPTION: {description}

TRANSCRIPT: {content_section}

Respond with valid JSON only, with these fields:
- is_clickbait: boolean - is this clickbait?
- clickbait_score: integer between 0 and 100 representing the percentage likelihood this is clickbait
- reasoning: a single paragraph explaining why this is or isn't clickbait, citing specific examples from the title and content"""

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.1,
    )

    response_text = response.choices[0].message.content

    # Try to extract JSON from the response
    json_match = re.search(r"\{.*\}", response_text, re.DOTALL)
    if json_match:
        json_str = json_match.group(0)
        data = json.loads(json_str)
    else:
        data = json.loads(response_text)

    return ClickbaitAnalysis(
        is_clickbait=data.get("is_clickbait", False),
        clickbait_score=data.get("clickbait_score", 0),
        reasoning=data.get("reasoning", ""),
    )
