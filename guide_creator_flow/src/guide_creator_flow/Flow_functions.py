import re

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
