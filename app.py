"""
IA PROCON - Sistema multiagente (protótipo acadêmico).

Uso:
    python app.py                                  # roda o caso padrão (C1)
    python app.py casos_teste/c3_tv_defeito.txt    # roda outro caso

Os textos dos prompts ficam em prompts.py. Os resultados são salvos em saidas/.
"""
import argparse
import os
import re
from datetime import datetime
from pathlib import Path

from crewai import Agent, Task, Crew, Process, LLM
from dotenv import load_dotenv

import prompts

load_dotenv()

RAIZ = Path(__file__).resolve().parent
PASTA_BASE = RAIZ / "base_conhecimento"
PASTA_SAIDAS = RAIZ / "saidas"
CASO_PADRAO = RAIZ / "casos_teste" / "c1_jaqueta_online.txt"

MODELO = os.environ.get("IA_PROCON_MODELO", "openai/nvidia/nemotron-3.5-lightning-30b-a3b")
URL_API = "https://integrate.api.nvidia.com/v1"
VERBOSE = os.environ.get("IA_PROCON_VERBOSE", "1") != "0"
# Temperatura do modelo (padrão 0.1). Para testar: $env:IA_PROCON_TEMPERATURA="0"
TEMPERATURA = float(os.environ.get("IA_PROCON_TEMPERATURA", "0.1"))

# "Art. 49", "art 49", "artigo 49", "Arts. 18" (só o primeiro número de uma lista é capturado)
# Agentes cujo raciocínio interno fica desligado. Padrão: todos (decisão final, medições v10-A x v10-B:
# ligar o raciocínio só no Auditor multiplicou o tempo por ~5 sem ganho de qualidade fora do ruído).
# Pode ser trocado sem editar o código: IA_PROCON_SEM_RACIOCINIO=triagem,pesquisa,redacao (nomes separados por vírgula)
_env = os.environ.get("IA_PROCON_SEM_RACIOCINIO", "todos").strip().lower()
SEM_RACIOCINIO_PADRAO = ("triagem", "pesquisa", "auditoria", "redacao") if _env == "todos" else tuple(
    x.strip() for x in _env.split(",") if x.strip())
AGENTES = ("triagem", "pesquisa", "auditoria", "redacao")

PADRAO_ARTIGO = re.compile(r"\bart(?:igo|s?\.?)\s*(\d+)", re.IGNORECASE)


# -------------------------------------------------------------
# Base de conhecimento
# -------------------------------------------------------------
def carregar_base() -> str:
    """Lê todos os .txt de base_conhecimento/ e marca a fonte de cada um."""
    arquivos = sorted(PASTA_BASE.glob("*.txt"))
    if not arquivos:
        raise SystemExit(f"Nenhum arquivo .txt encontrado em {PASTA_BASE}.")
    blocos = []
    for arq in arquivos:
        texto = arq.read_text(encoding="utf-8").strip()
        blocos.append(f"=== FONTE: {arq.name} ===\n{texto}\n=== FIM DA FONTE: {arq.name} ===")
    return "\n\n".join(blocos)


# -------------------------------------------------------------
# Montagem da equipe
# -------------------------------------------------------------
def preencher(texto: str, **valores: str) -> str:
    """Troca marcadores <<NOME>> pelos valores (sem usar chaves, que o CrewAI interpreta)."""
    for chave, valor in valores.items():
        texto = texto.replace(f"<<{chave}>>", valor)
    return texto


def criar_llm(sem_raciocinio: bool = False, agente: str = None) -> LLM:
    """sem_raciocinio=True pede à NVIDIA para desligar o raciocínio interno do modelo
    (chat_template_kwargs.enable_thinking=False). Validado em chamada direta com este modelo;
    dentro do CrewAI a checagem abaixo confirma que o parâmetro foi aceito pelo LLM."""
    chave = os.environ.get("NVIDIA_API_KEY")
    if not chave:
        raise SystemExit("NVIDIA_API_KEY não encontrada. Crie o arquivo .env (veja .env.example).")
    # Modelo por agente (opcional): IA_PROCON_MODELO_PESQUISA, IA_PROCON_MODELO_AUDITORIA etc.
    # Sem a variável, o agente usa MODELO. Formato igual ao de MODELO (ex.: openai/<id do catálogo>).
    modelo = (os.environ.get(f"IA_PROCON_MODELO_{agente.upper()}") if agente else None) or MODELO
    extras = {}
    if sem_raciocinio:
        extras["extra_body"] = {"chat_template_kwargs": {"enable_thinking": False}}
    llm = LLM(model=modelo, base_url=URL_API, api_key=chave, temperature=TEMPERATURA, **extras)
    if sem_raciocinio and "extra_body" not in (getattr(llm, "additional_params", None) or {}):
        raise SystemExit("O CrewAI não guardou o parâmetro extra_body em llm.additional_params; "
                         "o raciocínio NÃO seria desligado. Pare e avise para ajustarmos o método.")
    return llm


def montar_equipe(reclamacao: str, base: str, llm, callbacks: dict = None) -> Crew:
    """llm pode ser um LLM único (uso normal) ou um dict {"triagem": LLM, ...} (usado em medir.py).
    callbacks (opcional): dict {"triagem": função, ...} chamada quando cada tarefa termina."""
    callbacks = callbacks or {}

    def agente(chave: str) -> Agent:
        modelo = llm[chave] if isinstance(llm, dict) else llm
        return Agent(**prompts.AGENTES[chave], llm=modelo, verbose=VERBOSE, allow_delegation=False)

    def tarefa(chave: str, ag: Agent, contexto=None, **valores) -> Task:
        t = prompts.TAREFAS[chave]
        return Task(
            description=preencher(t["description"], **valores),
            expected_output=t["expected_output"],
            agent=ag,
            context=contexto or [],
            callback=callbacks.get(chave),
        )

    a_triagem, a_pesquisa = agente("triagem"), agente("pesquisa")
    a_auditoria, a_redacao = agente("auditoria"), agente("redacao")

    t_triagem = tarefa("triagem", a_triagem, RECLAMACAO=reclamacao.strip())
    t_pesquisa = tarefa("pesquisa", a_pesquisa, [t_triagem], BASE=base)
    t_auditoria = tarefa("auditoria", a_auditoria, [t_triagem, t_pesquisa], BASE=base)
    t_redacao = tarefa("redacao", a_redacao, [t_triagem, t_pesquisa, t_auditoria])

    return Crew(
        agents=[a_triagem, a_pesquisa, a_auditoria, a_redacao],
        tasks=[t_triagem, t_pesquisa, t_auditoria, t_redacao],
        process=Process.sequential,
    )


# -------------------------------------------------------------
# Verificação simples (feita em código, sem LLM)
# -------------------------------------------------------------
def artigos_citados(texto: str) -> set:
    return set(PADRAO_ARTIGO.findall(texto))


def verificar_citacoes(resposta: str, base: str) -> list:
    """Avisa sobre artigos citados na resposta que não aparecem na base.

    Limite conhecido: confere só o número do artigo, não parágrafos nem incisos.
    """
    fora_da_base = sorted(artigos_citados(resposta) - artigos_citados(base), key=int)
    return [f"Art. {n} aparece na resposta, mas não consta na base de conhecimento." for n in fora_da_base]


# "§ 1°", "§1º", "parágrafo único" e incisos em algarismos romanos
_ROMANO = r"(?-i:[IVX]+)"
_PAR = r"(?:§\s*(\d+)\s*[º°o]?|(par[áa]grafo\s+[úu]nico))"
REF_ARTIGO_PRIMEIRO = re.compile(
    r"\bArt(?:igo|s?\.?)\s*(\d+)\s*[º°]?"                 # Art. 26 / Art. 5º
    r"(?:\s*,?\s*(?:caput\s*,?\s*)?" + _PAR + r")?"      # , § 1°  /  parágrafo único
    r"(?:\s*,?\s*(?:inc(?:iso|\.)?\s*|(?=" + _ROMANO + r"\b))(" + _ROMANO + r")\b)?",  # , inc. II  /  , II
    re.IGNORECASE)
REF_PARAGRAFO_PRIMEIRO = re.compile(
    r"(?:§\s*(\d+)\s*[º°o]?|(par[áa]grafo\s+[úu]nico))\s+do\s+Art(?:igo|\.)?\s*(\d+)", re.IGNORECASE)


def indexar_base(base: str) -> dict:
    """Mapa {artigo: {"pu": bool, "par": {n: {incisos}}, "caput": {incisos}}} lido dos textos oficiais.

    Só lê linhas que começam com "Art. N", "§ N", "Parágrafo único" ou "I -" (formato dos arquivos da base).
    """
    indice, art, local = {}, None, None
    for linha in base.splitlines():
        t = linha.strip()
        if t.startswith("=== "):          # início ou fim de uma fonte: zera o artigo atual
            art, local = None, None
            continue
        m = re.match(r"Art\.?\s*(\d+)", t)
        if m:
            art = m.group(1)
            indice[art] = {"pu": False, "par": {}, "caput": set()}
            local = indice[art]["caput"]
            continue
        if art is None:
            continue
        m = re.match(r"§\s*(\d+)", t)
        if m:
            local = indice[art]["par"].setdefault(m.group(1), set())
            continue
        if re.match(r"Par[áa]grafo\s+[úu]nico", t, re.IGNORECASE):
            indice[art]["pu"] = True
            local = set()          # incisos do parágrafo único não são checados
            continue
        m = re.match(r"(" + _ROMANO + r")\s*-", t)
        if m and local is not None and "(vetado)" not in t.lower():
            local.add(m.group(1))
    return indice


def verificar_referencias(resposta: str, base: str) -> list:
    """Avisa quando a resposta cita parágrafo ou inciso que não existe no artigo da base.

    Ex.: "Art. 49, § 1°" (o Art. 49 só tem parágrafo único) ou "Art. 26, § 1°, II" (o § 1° não tem incisos).
    Limite: não confere o conteúdo, só se o dispositivo existe. Não checa incisos do parágrafo único.
    """
    indice = indexar_base(base)
    avisos, vistos = [], set()

    def checar(art, par, pu, inc, texto):
        chave = (art, par, bool(pu), inc)
        if chave in vistos or art not in indice:
            return
        vistos.add(chave)
        d = indice[art]
        if pu and not d["pu"]:
            avisos.append(f"Resposta cita parágrafo único do Art. {art} ({texto}), mas a base não o contém.")
        elif par and par not in d["par"]:
            avisos.append(f"Resposta cita § {par} do Art. {art} ({texto}), mas a base não contém esse parágrafo.")
        elif inc:
            alvo = d["par"].get(par) if par else (None if pu else d["caput"])
            if alvo is not None and inc.upper() not in alvo:
                onde = f"§ {par} do Art. {art}" if par else f"caput do Art. {art}"
                avisos.append(f"Resposta cita inciso {inc.upper()} ({texto}), mas a base não tem esse inciso no {onde}.")

    def do_decreto(m):
        """Referências a artigos de decreto não são conferidas aqui (só a Lei 8.078 é indexada)."""
        return "decreto" in resposta[max(0, m.start() - 30):m.end() + 40].lower()

    for m in REF_ARTIGO_PRIMEIRO.finditer(resposta):
        if not do_decreto(m):
            checar(m.group(1), m.group(2), m.group(3), m.group(4), m.group(0).strip())
    for m in REF_PARAGRAFO_PRIMEIRO.finditer(resposta):
        if not do_decreto(m):
            checar(m.group(3), m.group(1), m.group(2), None, m.group(0).strip())
    return avisos


PALAVRAS_INTERNAS = ("triagem", "auditor", "parecer", "de memória", "base legal", "base de conhecimento",
                     "base técnica", "pesquisador")
PALAVRAS_INGLES = ("the", "and", "with", "none", "happened", "leaving", "because", "however", "should", "which")


def verificar_decreto(resposta: str) -> list:
    """Avisa quando a resposta cita artigo do Decreto 7.962 acima do Art. 7º (o decreto só tem 7 artigos)."""
    avisos = []
    for m in re.finditer(r"art(?:igo|\.)?\s*(\d+)[º°o]?[^.\n]{0,40}?decreto\s*(?:n[º°o.]*\s*)?7\.?962", resposta, re.I):
        if int(m.group(1)) > 7:
            avisos.append(f"Resposta cita Art. {m.group(1)} do Decreto 7.962, que só tem os Arts. 1º a 7º.")
    return avisos


def limpar_vazamentos(resposta: str) -> str:
    """Troca expressões internas por termos neutros (mecânico, não altera o sentido)."""
    troca = {"a": "o", "da": "do", "na": "no", "à": "ao", "pela": "pelo"}
    resposta = re.sub(r"\b(a|da|na|à|pela) base legal\b",
                      lambda m: troca[m.group(1).lower()] + " material consultado", resposta, flags=re.I)
    return re.sub(r"\bbase legal\b", "material consultado", resposta, flags=re.I)


def verificar_vazamentos(resposta: str) -> list:
    """Avisa sobre palavras internas do sistema e palavras em inglês na resposta final.

    Limite: lista curta e fixa; não detecta todos os casos. "parecer" como verbo também é apontado
    (pode ser falso positivo)."""
    texto = resposta.lower()
    avisos = []
    for p in PALAVRAS_INTERNAS:
        if re.search(r"\b" + re.escape(p) + r"\b", texto):
            avisos.append(f'Palavra interna do sistema na resposta: "{p}".')
    for p in PALAVRAS_INGLES:
        if re.search(r"\b" + p + r"\b", texto):
            avisos.append(f'Possível palavra em inglês na resposta: "{p}".')
    return avisos


def _normalizar(texto: str) -> str:
    texto = texto.replace("\u00b0", "\u00ba").replace("\u201c", '"').replace("\u201d", '"')
    texto = texto.replace("\u2013", "-").replace("\u2014", "-").replace("*", "")
    return re.sub(r"\s+", " ", texto).strip().lower()


def verificar_aspas(resposta: str, base: str, minimo_palavras: int = 6, reclamacao: str = "") -> list:
    """Avisa sobre trechos entre aspas que não aparecem literalmente na base.

    Trechos que aparecem literalmente no relato do consumidor (reclamacao) são ignorados,
    pois citar o relato é legítimo.

    Pontos suspensivos dentro das aspas dividem o trecho em partes. Modelos de mensagem
    escritos entre aspas também serão apontados; nesse caso o aviso pode ser ignorado.
    """
    base_norm = _normalizar(base)
    relato_norm = _normalizar(reclamacao)
    avisos = []
    for m in re.finditer(r'[\u201c"]([^\u201d"]+)[\u201d"]', resposta):
        for parte in re.split(r"\u2026|\.\.\.|\[\.\.\.\]", m.group(1)):
            parte_norm = _normalizar(parte).strip(" .,;:")
            if (len(parte_norm.split()) >= minimo_palavras and parte_norm not in base_norm
                    and parte_norm not in relato_norm):
                avisos.append(f'Trecho entre aspas não encontrado literalmente na base: "{parte.strip()[:90]}..."')
    return avisos


# -------------------------------------------------------------
# Execução
# -------------------------------------------------------------
def analisar(reclamacao: str, etapa=None) -> tuple:
    """Roda os 4 agentes sobre o texto de uma reclamação. Devolve (resposta_final, avisos).
    etapa (opcional): função chamada com o nome do agente quando ele termina (usada pela interface web)."""
    base = carregar_base()
    llms = {a: criar_llm(sem_raciocinio=a in SEM_RACIOCINIO_PADRAO, agente=a) for a in AGENTES}
    callbacks = {a: (lambda _saida, a=a: etapa(a)) for a in AGENTES} if etapa else None
    equipe = montar_equipe(reclamacao, base, llms, callbacks)

    resultado = equipe.kickoff()
    resposta = limpar_vazamentos(getattr(resultado, "raw", None) or str(resultado))

    avisos = (verificar_citacoes(resposta, base) + verificar_referencias(resposta, base)
              + verificar_decreto(resposta)
              + verificar_aspas(resposta, base, reclamacao=reclamacao)
              + verificar_vazamentos(resposta))
    return resposta.strip() + "\n\n" + prompts.AVISO_FINAL, avisos


def executar(caminho_caso: Path) -> str:
    reclamacao = caminho_caso.read_text(encoding="utf-8")
    final, avisos = analisar(reclamacao)

    PASTA_SAIDAS.mkdir(exist_ok=True)
    carimbo = datetime.now().strftime("%Y%m%d_%H%M%S")
    destino = PASTA_SAIDAS / f"{carimbo}_{caminho_caso.stem}.md"
    corpo_avisos = "\n".join(f"- {a}" for a in avisos) or "- nenhum"
    destino.write_text(
        f"# Caso: {caminho_caso.name}\nModelo: {MODELO}\n\n## Resposta\n\n{final}\n\n"
        f"## Verificação automática de citações\n\n{corpo_avisos}\n",
        encoding="utf-8",
    )

    print("\n======================= ORIENTAÇÃO IA PROCON =======================\n")
    print(final)
    print("\n--------------- Verificação automática de citações ---------------")
    print(corpo_avisos)
    print(f"\nSalvo em: {destino}")
    return final


def main() -> None:
    parser = argparse.ArgumentParser(description="IA PROCON - análise multiagente de reclamações")
    parser.add_argument("caso", nargs="?", default=str(CASO_PADRAO), help="arquivo .txt com a reclamação")
    args = parser.parse_args()
    caminho = Path(args.caso)
    if not caminho.is_file():
        raise SystemExit(f"Arquivo não encontrado: {caminho}")
    print("Iniciando o Sistema Multiagente IA PROCON...")
    executar(caminho)


if __name__ == "__main__":
    main()
