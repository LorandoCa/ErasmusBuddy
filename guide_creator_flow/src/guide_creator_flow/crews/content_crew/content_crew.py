from pathlib import Path

from crewai.project import load_crew

AGENTS_DIR = Path(__file__).resolve().parent / "agents"

CREW_FILES = {
    "bureaucracy": AGENTS_DIR / "bureaucracy" / "Report_crew" / "crew_bureaucracy.jsonc",
    "bureaucracy_repair": AGENTS_DIR / "bureaucracy" / "Feedback_crew" / "crew_bureaucracy_repair.jsonc",
}


def kickoff_crew(crew_name: str, inputs: dict):
    if crew_name not in CREW_FILES:
        raise ValueError(f"Crew desconhecida: {crew_name!r}. Opções: {list(CREW_FILES)}")

    crew_path = CREW_FILES[crew_name]
    print(crew_path, crew_path.exists())  # diagnóstico, podes remover depois

    crew, default_inputs = load_crew(crew_path)
    return crew.kickoff(inputs={**default_inputs, **inputs})


def kickoff_bureaucracy_crew(inputs: dict):
    return kickoff_crew("bureaucracy", inputs)


def kickoff_bureaucracy_crew_repair(inputs: dict):
    return kickoff_crew("bureaucracy_repair", inputs)