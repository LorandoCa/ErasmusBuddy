import re
import asyncio
from crews.content_crew.content_crew import kickoff_bureaucracy_crew, kickoff_finances_crew

# TRANSLATE DO ENGLISH

# Letras (incluindo acentos), espaços, hífenes, apóstrofos, pontos e parênteses
PADRAO_NOME = re.compile(r"^[A-Za-zÀ-ÖØ-öø-ÿ0-9 .,'()\-]+$")

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


def _build_inputs(section: str, personal_info: dict, crews_config: dict,
                  extra_inputs: dict | None = None) -> dict:
    config = crews_config.get(section)
    if config is None:
        raise ValueError(f"Section {section!r} is missing in crews_config.json")
    inputs = {
        campo: personal_info.get(campo)
        for campo in config.get("required_fields", [])
    }
    return {**inputs, **(extra_inputs or {})}


async def run_bureaucracy(personal_info, crews_config, extra_inputs=None):
    inputs = _build_inputs("bureaucracy", personal_info, crews_config, extra_inputs)
    return await asyncio.to_thread(kickoff_bureaucracy_crew, inputs=inputs)


async def run_finances(personal_info, crews_config, extra_inputs=None):
    inputs = _build_inputs("finances", personal_info, crews_config, extra_inputs)
    return await asyncio.to_thread(kickoff_finances_crew, inputs=inputs)