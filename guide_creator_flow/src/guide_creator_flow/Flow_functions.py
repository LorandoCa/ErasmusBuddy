import re
import asyncio
from crews.content_crew.content_crew import kickoff_bureaucracy_crew, kickoff_finances_crew

# TRANSLATE DO ENGLISH

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
    inputs["extra_inputs"] = format_extra_inputs(extra_inputs)  # always present
    return inputs


async def run_bureaucracy(personal_info, crews_config, extra_inputs):
    inputs = _build_inputs("bureaucracy", personal_info, crews_config, extra_inputs)
    return await asyncio.to_thread(kickoff_bureaucracy_crew, inputs=inputs)


async def run_finances(personal_info, crews_config, extra_inputs):
    inputs = _build_inputs("finances", personal_info, crews_config, extra_inputs)
    return await asyncio.to_thread(kickoff_finances_crew, inputs=inputs)


def extract_questions(section: str, outcome) -> dict[str, str]:
    """Return the questions a crew asked, or [] if its output has none.

    The crew signals questions by wrapping them, one per line, between
    <<<QUESTIONS_START>>> and <<<QUESTIONS_END>>>. Text outside the block is ignored.
    """
    raw = getattr(outcome, "raw", outcome)  # accepts a CrewOutput or a plain string
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