"""CrewAI planning crew for TradeTix product and technical specifications.

Run this script before implementation work to have a small autonomous team
research an idea, review it for legal risk, and draft a technical spec.
"""

from __future__ import annotations

import os
import sys

from crewai import Agent, Crew, Process, Task
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI


load_dotenv()


DEFAULT_BRIEF = (
    "Research and plan a high-impact TradeTix feature that improves trust, "
    "conversion, buyer safety, seller reliability, or operational efficiency."
)


def build_llm() -> ChatOpenAI:
    """Create the shared OpenAI chat model used by every crew member."""
    return ChatOpenAI(
        model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        temperature=float(os.getenv("AI_AGENTS_TEMPERATURE", "0.3")),
    )


def build_crew(product_brief: str) -> Crew:
    """Build the TradeTix planning crew and its sequential workflow."""
    llm = build_llm()

    chief_marketing_officer = Agent(
        role="Chief Marketing Officer",
        goal=(
            "Identify commercially strong TradeTix product ideas that improve "
            "market positioning, user adoption, trust, and revenue."
        ),
        backstory=(
            "You are an experienced marketplace CMO who understands ticketing, "
            "consumer trust, marketplace liquidity, conversion funnels, and "
            "growth experiments. You turn vague goals into sharp product angles."
        ),
        llm=llm,
        verbose=True,
        allow_delegation=False,
    )

    legal_advisor = Agent(
        role="Legal Advisor",
        goal=(
            "Review marketplace product ideas for legal, regulatory, privacy, "
            "consumer protection, payments, and ticketing compliance risks."
        ),
        backstory=(
            "You are a pragmatic technology and marketplace legal advisor. You "
            "spot risk early, explain mitigations clearly, and preserve product "
            "velocity without hand-waving compliance obligations."
        ),
        llm=llm,
        verbose=True,
        allow_delegation=False,
    )

    senior_developer = Agent(
        role="Senior Full-Stack QA Engineer",
        goal=(
            "Convert approved product concepts into implementation-ready "
            "technical specifications with architecture, API, data, QA, and "
            "release considerations."
        ),
        backstory=(
            "You are a senior full-stack engineer with strong QA instincts. You "
            "think in Django APIs, frontend behavior, background jobs, security, "
            "observability, regression risk, and test plans before code is written."
        ),
        llm=llm,
        verbose=True,
        allow_delegation=False,
    )

    marketing_task = Task(
        description=(
            "Using this TradeTix planning brief, propose one product or platform "
            "idea worth implementing next:\n\n"
            f"{product_brief}\n\n"
            "Explain the target user, customer pain, business upside, success "
            "metrics, launch angle, and the smallest useful MVP."
        ),
        expected_output=(
            "A concise product proposal with target audience, pain point, MVP, "
            "business value, go-to-market angle, and measurable success metrics."
        ),
        agent=chief_marketing_officer,
    )

    legal_review_task = Task(
        description=(
            "Review the marketing proposal for legal and operational risk. "
            "Call out issues related to ticket resale rules, refunds, buyer and "
            "seller protection, payment handling, data privacy, advertising "
            "claims, fraud prevention, and required user disclosures. Recommend "
            "specific mitigations and say whether the idea is safe to spec."
        ),
        expected_output=(
            "A legal risk review with severity, required mitigations, wording or "
            "policy changes, and a clear go/no-go recommendation."
        ),
        agent=legal_advisor,
        context=[marketing_task],
    )

    developer_human_in_the_loop = True
    technical_spec_task = Task(
        description=(
            "Create an implementation-ready technical specification based on "
            "the marketing proposal and legal review. Include architecture, "
            "backend changes, frontend behavior, data model or migration needs, "
            "API contracts, security concerns, failure modes, observability, "
            "rollout plan, and QA test plan. Ask the human operator for approval "
            "before producing the final answer."
        ),
        expected_output=(
            "A complete technical specification in Markdown with acceptance "
            "criteria and a focused test plan."
        ),
        agent=senior_developer,
        context=[marketing_task, legal_review_task],
        human_input=developer_human_in_the_loop,
    )

    return Crew(
        agents=[
            chief_marketing_officer,
            legal_advisor,
            senior_developer,
        ],
        tasks=[
            marketing_task,
            legal_review_task,
            technical_spec_task,
        ],
        process=Process.sequential,
        verbose=True,
    )


def main() -> None:
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError(
            "OPENAI_API_KEY is not set. Add it to your environment or backend/.env "
            "before running the TradeTix planning crew."
        )

    product_brief = " ".join(sys.argv[1:]).strip() or DEFAULT_BRIEF
    crew = build_crew(product_brief)
    result = crew.kickoff()

    print("\n\n=== TradeTix Crew Final Output ===\n")
    print(result)


if __name__ == "__main__":
    main()
