from __future__ import annotations
from typing import List, Literal, Optional
from pydantic import BaseModel, Field, field_validator


# --------------------------------------------------------------------------
# Finanças / Estimativas de Custos
# --------------------------------------------------------------------------

class CostEstimate(BaseModel):
    average_monthly: float = Field(description="Average monthly spending in euros, as a plain number (e.g. 180.0)")
    low: float = Field(description="Low end of the monthly range in euros, as a plain number")
    high: float = Field(description="High end of the monthly range in euros, as a plain number")
    sources: list[str] = Field(description="URLs of the pages where the figures were found")


# --------------------------------------------------------------------------
# Modelos de Clarificação (Commute & Housing Thinking) - compatíveis com erasmove
# --------------------------------------------------------------------------

class ThinkingQuestion(BaseModel):
    text: str = Field(description="The question, phrased for the student.")
    why: str = Field(description="Why the answer matters / what it changes.")
    fills: str = Field(description="The requirement key or profile field this question fills.")
    answer_type: Literal["choice", "number", "yes_no"] = "choice"
    choices: list[str] = Field(default_factory=list, description="Only for answer_type 'choice'.")
    default: str = Field(default="", description="Answer assumed if the student does not change it.")
    agent: Literal["housing", "commute"] = "housing"

    @field_validator("default", mode="before")
    @classmethod
    def _default_to_str(cls, value):
        if isinstance(value, bool):
            return "yes" if value else "no"
        return "" if value is None else str(value)

    @property
    def question(self) -> str:
        """Alias for text for compatibility."""
        return self.text


class RequirementSuggestion(BaseModel):
    key: str = Field(description="Key from the requirement catalog; nothing else.")
    level: Literal["must", "should"] = "should"
    why: str = ""


class HousingThinking(BaseModel):
    add_requirements: list[RequirementSuggestion] = Field(default_factory=list)
    questions: list[ThinkingQuestion] = Field(default_factory=list)


class CommuteThinking(BaseModel):
    questions: list[ThinkingQuestion] = Field(default_factory=list)


class GatheredQuestion(BaseModel):
    fills: str = Field(description="Unchanged 'fills' of the merged question(s).")
    text: str
    why: str


class QuestionBundle(BaseModel):
    questions: list[GatheredQuestion] = Field(description="Merged, deduplicated, ordered.")
    dropped: list[str] = Field(default_factory=list, description="Questions removed and why.")


# --------------------------------------------------------------------------
# Bureaucracy (Erasmus+ arrival checklist crew)
# --------------------------------------------------------------------------

class BureaucracyQuestion(BaseModel):
    text: str = Field(description="The question, phrased clearly for the student.")
    why: str = Field(description="Why the answer is needed / what it changes in the research.")


class BureaucracyThinking(BaseModel):
    """Returned by the Search_info task when personal information is missing."""
    questions: list[BureaucracyQuestion] = Field(
        description="At most 3 clear questions the researcher needs answered before continuing."
    )


class ChecklistItem(BaseModel):
    title: str = Field(description="Short action title (e.g. 'Register with local authorities').")
    description: str = Field(description="1–3 sentence explanation of what to do and why.")
    source: str = Field(default="", description="Official URL backing this item, or empty string.")


class BureaucracyReport(BaseModel):
    """Returned by the Create_report task when no information is missing."""
    arrival_checklist: list[ChecklistItem] = Field(
        description="Arrival 'must-do' steps from the official Erasmus+ / government sources."
    )
    transport_card_steps: list[ChecklistItem] = Field(
        description="Documents and steps required to get a public transport card in the destination city."
    )
    other_info: list[ChecklistItem] = Field(
        description="Other relevant information for incoming Erasmus+ students (health, support, orientation, etc.)."
    )

    def to_markdown(self, city: str = "", country: str = "") -> str:
        """Render the report as a Markdown string for the guide."""
        loc = f"{city}, {country}".strip(", ")
        lines = [f"## Bureaucracy & Arrival Guide — {loc}\n"]

        def _section(title: str, items: list[ChecklistItem]) -> list[str]:
            block = [f"\n### {title}\n"]
            for item in items:
                block.append(f"- **{item.title}**: {item.description}")
                if item.source:
                    block.append(f"  - Source: {item.source}")
            return block

        lines += _section("Arrival 'Must-Do' Checklist", self.arrival_checklist)
        lines += _section("Public Transport Card — Documents & Steps", self.transport_card_steps)
        lines += _section("Other Useful Information", self.other_info)
        return "\n".join(lines)
