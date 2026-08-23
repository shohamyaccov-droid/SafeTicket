"""CrewAI marketing outreach crew for TradeTix lead generation.

Required environment variables before running:
- OPENAI_API_KEY: read from the environment by langchain-openai.
- SERPER_API_KEY: read from the environment by SerperDevTool for web search.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from crewai import Agent, Crew, Process, Task
from crewai_tools import SerperDevTool
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI


load_dotenv()


DEFAULT_MARKET = (
    "Israeli ticket-exchange buyers and sellers looking for concerts and "
    "music events happening soon."
)
OUTPUT_FILE = Path(__file__).with_name("facebook_campaign.md")


def build_llm() -> ChatOpenAI:
    """Create the shared OpenAI chat model used by the outreach crew."""
    # OPENAI_API_KEY is read automatically from the environment.
    return ChatOpenAI(model="gpt-4o", temperature=0.7)


def build_crew(target_market: str) -> Crew:
    """Build the sequential Event Scout -> Community Marketer workflow."""
    llm = build_llm()
    search_tool = SerperDevTool()

    event_scout_agent = Agent(
        role="Lead Event & Concert Researcher",
        goal=(
            "Identify the top 3 highest-demand or sold-out concerts and music "
            "events happening soon."
        ),
        backstory=(
            "An expert at scanning entertainment news, social media buzz, and "
            "ticket platforms to find events where supply is low and demand is "
            "extremely high."
        ),
        tools=[search_tool],
        llm=llm,
        verbose=True,
        allow_delegation=False,
    )

    community_marketer_agent = Agent(
        role="Social Media Growth Hacker",
        goal=(
            "Draft viral, high-conversion Facebook posts and responses tailored "
            "for ticket-exchange groups to funnel buyers/sellers to TradeTix."
        ),
        backstory=(
            "A master of organic marketing who knows exactly how to pitch "
            "TradeTix as the ultimate safe, scam-free solution, including its "
            "secure 2-round negotiation system, without sounding like a corporate bot."
        ),
        llm=llm,
        verbose=True,
        allow_delegation=False,
    )

    scout_task = Task(
        description=(
            "Search the web and find 3 hot, high-demand upcoming music events "
            f"or concerts for this target audience:\n\n{target_market}\n\n"
            "Prioritize sold-out, nearly sold-out, trending, resale-heavy, or "
            "high-buzz events happening soon. Output a structured list with each "
            "event name, date, venue, city/country, demand signal, and source URLs."
        ),
        expected_output=(
            "A structured list of exactly 3 hot upcoming music events or "
            "concerts, including dates, venues, demand rationale, and sources."
        ),
        agent=event_scout_agent,
    )

    marketing_task = Task(
        description=(
            "Review the found events and write 3 distinct, ready-to-copy Facebook "
            "posts or comments in Hebrew, one for each event. The target audience "
            "is Israeli Facebook ticket-exchange groups. Each post must mention "
            "the specific event, speak naturally to buyers and sellers, explain "
            "why TradeTix is the safest way to buy or sell for that event, and "
            "highlight scam prevention plus the secure 2-round negotiation system. "
            "Make the copy engaging, direct, and community-native rather than corporate."
        ),
        expected_output=(
            "A formatted Markdown campaign file in Hebrew with 3 event-specific, "
            "ready-to-copy Facebook posts/comments."
        ),
        agent=community_marketer_agent,
        context=[scout_task],
        output_file=str(OUTPUT_FILE),
    )

    return Crew(
        agents=[event_scout_agent, community_marketer_agent],
        tasks=[scout_task, marketing_task],
        process=Process.sequential,
        verbose=True,
    )


def main() -> None:
    # Set OPENAI_API_KEY for the LLM and SERPER_API_KEY for Serper web search.
    # Keep API keys in your shell or backend/.env rather than hardcoding them.
    missing_keys = [
        key for key in ("OPENAI_API_KEY", "SERPER_API_KEY") if not os.getenv(key)
    ]
    if missing_keys:
        raise RuntimeError(
            "Missing required environment variable(s): "
            f"{', '.join(missing_keys)}. Set them in your shell or backend/.env."
        )

    target_market = " ".join(sys.argv[1:]).strip() or DEFAULT_MARKET
    crew = build_crew(target_market)
    result = crew.kickoff()

    print("\n\n=== TradeTix Marketing Outreach Final Output ===\n")
    print(result)
    print(f"\nMarkdown output written to: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
