import re
import asyncio
import logging

try:
    from guide_creator_flow.crews.content_crew.content_crew import (
        kickoff_bureaucracy_crew,
        kickoff_finances_crew,
        kickoff_commute_crew,
        kickoff_housing_crew,
    )
except ImportError:
    from crews.content_crew.content_crew import (
        kickoff_bureaucracy_crew,
        kickoff_finances_crew,
        kickoff_commute_crew,
        kickoff_housing_crew,
    )

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Retry helper
# ---------------------------------------------------------------------------
# Keywords that signal a transient API overload (not a permanent error).
_TRANSIENT_SIGNALS = ("429", "rate limit", "overloaded", "overload", "503", "resource exhausted")

_MAX_RETRIES = 3          # maximum attempts per section runner
_BASE_BACKOFF = 10        # seconds — doubles each attempt (10 → 20 → 40)


def _is_transient(exc: Exception) -> bool:
    """Return True if the exception looks like an API rate-limit / overload."""
    msg = str(exc).lower()
    return any(sig in msg for sig in _TRANSIENT_SIGNALS)


async def _run_with_retry(fn, *args, **kwargs):
    """
    Run *fn* (a sync callable) in a thread executor, retrying up to
    _MAX_RETRIES times if the error is a transient API error.

    Args:
        fn: synchronous function to call (e.g. kickoff_commute_crew)
        *args / **kwargs: forwarded to fn
    Returns:
        whatever fn returns
    Raises:
        the last exception if all retries are exhausted
    """
    last_exc: Exception | None = None
    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            return await asyncio.to_thread(fn, *args, **kwargs)
        except Exception as exc:
            last_exc = exc
            if _is_transient(exc) and attempt < _MAX_RETRIES:
                wait = _BASE_BACKOFF * (2 ** (attempt - 1))   # 10 s, 20 s, 40 s
                logger.warning(
                    "Transient API error (attempt %d/%d): %s. Retrying in %ds…",
                    attempt, _MAX_RETRIES, exc, wait,
                )
                print(
                    f"⚠️  API overloaded (attempt {attempt}/{_MAX_RETRIES}). "
                    f"Retrying in {wait}s…"
                )
                await asyncio.sleep(wait)
            else:
                # Non-transient error or final attempt — propagate immediately
                raise
    raise last_exc  # should never be reached, but satisfies type checkers

# Letras (incluindo acentos), espaços, hífenes, apóstrofos, pontos e parênteses
PADRAO_NOME = re.compile(r"^[A-Za-zÀ-ÖØ-öø-ÿ0-9 .,'()\-]+$")

QUESTIONS_START = "<<<QUESTIONS_START>>>"
QUESTIONS_END = "<<<QUESTIONS_END>>>"

# \Z also accepts a missing END marker (e.g. the LLM output was cut off)
_QUESTIONS_BLOCK = re.compile(
    re.escape(QUESTIONS_START) + r"(.*?)(?:" + re.escape(QUESTIONS_END) + r"|\Z)",
    re.DOTALL,
)
# strips list prefixes like "- ", "* ", "1. " or "2) "
_LIST_PREFIX = re.compile(r"^\s*(?:[-*•]|\d+[.)])\s*")


def pedir_input(mensagem, min_len=2, max_len=100):
    while True:
        valor = input(mensagem).strip()
        valor = re.sub(r"\s+", " ", valor)  # remove espaços duplicados

        if not valor:
            print("❌ O campo não pode estar vazio.")
        elif len(valor) < min_len:
            print(f"❌ Tem de ter pelo menos {min_len} caracteres.")
        elif len(valor) > max_len:
            print(f"❌ Não pode ter mais de {max_len} caracteres.")
        elif not PADRAO_NOME.match(valor):
            print("❌ Contém caracteres inválidos.")
        else:
            return valor


def format_extra_inputs(extra_inputs: dict | None) -> str:
    """Turns {question: answer} into a text block the crew can read."""
    if not extra_inputs:
        return ""
    return "\n\n".join(
        f"Question: {question}\nAnswer: {answer}"
        for question, answer in extra_inputs.items()
    )


def _build_inputs(section: str, personal_info: dict, crews_config: dict,
                  extra_inputs: dict | None = None) -> dict:
    config = crews_config.get(section)
    if config is None:
        raise ValueError(f"Section {section!r} is missing in crews_config.json")
    inputs = {
        campo: personal_info.get(campo)
        for campo in config.get("required_fields", [])
    }
    # Convenient aliases for prompts that use {city} or {country}
    if "destination_city" in personal_info and "city" not in inputs:
        inputs["city"] = personal_info.get("destination_city")
    if "destination_country" in personal_info and "country" not in inputs:
        inputs["country"] = personal_info.get("destination_country")
    if "destination_university" in personal_info and "campus_names" not in inputs:
        inputs["campus_names"] = personal_info.get("destination_university")

    inputs["extra_inputs"] = format_extra_inputs(extra_inputs)  # always present
    return inputs


async def run_bureaucracy(personal_info, crews_config, extra_inputs):
    inputs = _build_inputs("bureaucracy", personal_info, crews_config, extra_inputs)
    return await asyncio.to_thread(kickoff_bureaucracy_crew, inputs=inputs)


async def run_finances(personal_info, crews_config, extra_inputs):
    inputs = _build_inputs("finances", personal_info, crews_config, extra_inputs)
    return await asyncio.to_thread(kickoff_finances_crew, inputs=inputs)


async def run_commute(personal_info, crews_config, extra_inputs):
    inputs = _build_inputs("commute", personal_info, crews_config, extra_inputs)
    return await asyncio.to_thread(kickoff_commute_crew, inputs=inputs)


async def run_housing(personal_info, crews_config, extra_inputs):
    inputs = _build_inputs("housing", personal_info, crews_config, extra_inputs)
    return await asyncio.to_thread(kickoff_housing_crew, inputs=inputs)


def extract_questions(section: str, outcome) -> list[str]:
    """Return the questions a crew asked, or [] if its output has none.

    Accepts:
    1. Structured Pydantic objects with a `.questions` list (e.g. CommuteThinking, HousingThinking).
    2. Text wrapping questions between <<<QUESTIONS_START>>> and <<<QUESTIONS_END>>>.
    """
    # 1. Check for Pydantic structured output with questions
    pyd = getattr(outcome, "pydantic", None)
    if pyd is not None and hasattr(pyd, "questions") and pyd.questions:
        extracted = []
        for q in pyd.questions:
            if hasattr(q, "text") and q.text:
                extracted.append(q.text)
            elif hasattr(q, "question") and q.question:
                extracted.append(q.question)
            elif isinstance(q, str):
                extracted.append(q)
        if extracted:
            return extracted

    # 2. Check for delimiter block in raw string output
    raw = getattr(outcome, "raw", outcome)
    if not isinstance(raw, str):
        return []

    questions = []
    for block in _QUESTIONS_BLOCK.findall(raw):
        for line in block.splitlines():
            line = _LIST_PREFIX.sub("", line).strip()
            if line:
                questions.append(line)
    return questions


def collect_user_answers(section: str, questions: list[str]) -> dict[str, str]:
    """Ask the user each question from a crew and return {question: answer}."""
    print(f"\n=== The '{section}' section needs a bit more information ===\n")

    answers = {}
    total = len(questions)
    for i, question in enumerate(questions, start=1):
        answers[question] = pedir_input(f"[{i}/{total}] {question}\n> ", max_len=300)
    return answers


def extract_content(section: str, outcome, personal_info: dict | None = None) -> str:
    """Convert a crew outcome into a Markdown string for the guide.

    Handles three cases:
    1. Pydantic model with a ``to_markdown()`` method (e.g. BureaucracyReport).
    2. Pydantic model that is *not* a report (e.g. still a BureaucracyThinking
       with questions) — returns empty string so the caller can detect failure.
    3. Raw string outcome (commute / housing Mode B).
    """
    pyd = getattr(outcome, "pydantic", None)

    # Case 1 — structured report with a to_markdown() helper
    if pyd is not None and callable(getattr(pyd, "to_markdown", None)):
        city = (personal_info or {}).get("destination_city", "")
        country = (personal_info or {}).get("destination_country", "")
        return pyd.to_markdown(city=city, country=country)

    # Case 2 — Pydantic model without to_markdown (e.g. BureaucracyThinking
    # still carrying questions after MAX_ROUNDS). Return empty so the caller
    # stores a partial placeholder instead of crashing.
    if pyd is not None:
        return ""

    # Case 3 — plain string (commute / housing raw Markdown output)
    return getattr(outcome, "raw", str(outcome))
