"""
IA PROCON - Medição de custo (tokens, chamadas, tempo) e planilha de avaliação.

Roda cada caso N vezes, registra por agente: tokens de entrada/saída/total, chamadas e tempo,
e salva tudo a cada execução concluída. Para sozinho, com mensagem clara, se a API
devolver erro de limite (429) ou de créditos.

Uso:
    python medir.py                              # todos os casos c*.txt, 2 execuções cada
    python medir.py --repeticoes 3               # 3 execuções por caso
    python medir.py --casos casos_teste/c1_jaqueta_online.txt --rotulo v6
    python medir.py --rotulo v7                      # triagem sem raciocínio (padrão)
    python medir.py --rotulo v7 --raciocinio-completo   # raciocínio ligado em todos
    python medir.py --pausa 20                   # espera 20 s entre execuções (segurança contra o limite de 40 rpm)

Preço (opcional, em dólares por 1 milhão de tokens; a NVIDIA não publica preço oficial para este
modelo no catálogo gratuito, então NÃO há valor padrão):
    IA_PROCON_PRECO_ENTRADA=0.08   IA_PROCON_PRECO_SAIDA=0.20     (no .env)

Saídas em saidas/medicao/:
    medicao.csv     uma linha por agente por execução (separador ';', abre direto no Excel)
    avaliacao.csv   uma linha por execução, com colunas vazias para você pontuar contra o gabarito
    respostas/      a resposta final de cada execução
"""
import argparse
import csv
import os
import time
from datetime import datetime
from pathlib import Path


import app

PASTA = app.PASTA_SAIDAS / "medicao"
AGENTES = ["triagem", "pesquisa", "auditoria", "redacao"]
SINAIS_LIMITE = ("429", "rate limit", "ratelimit", "too many requests", "quota",
                 "credit", "402", "insufficient", "billing")

COLS_MEDICAO = ["data_hora", "rotulo", "caso", "execucao", "agente", "tokens_entrada",
                "tokens_saida", "tokens_total", "chamadas", "segundos", "custo_usd_estimado", "modelo"]
COLS_AVALIACAO = ["data_hora", "rotulo", "caso", "execucao", "arquivo_resposta",
                  "avisos_artigo_fora_da_base", "avisos_aspas_nao_literais", "avisos_vazamento_ou_ingles",
                  "conclusao_correta_0a2", "artigo_correto_0a2", "condicoes_nao_atendidas_tratadas_0a2",
                  "lacunas_e_incertezas_0a2", "inventou_algo_0ou1", "nota_geral_0a10", "observacoes"]


def _campo(obj, nome: str) -> int:
    """Lê um contador de um objeto ou dict; devolve 0 se não existir."""
    valor = obj.get(nome) if isinstance(obj, dict) else getattr(obj, nome, 0)
    return int(valor or 0)


def ler_uso(llm) -> dict:
    """Uso acumulado de um LLM do CrewAI. Retorna None se esta versão não expuser o método."""
    metodo = getattr(llm, "get_token_usage_summary", None)
    if metodo is None:
        return None
    resumo = metodo()
    return {
        "entrada": _campo(resumo, "prompt_tokens"),
        "saida": _campo(resumo, "completion_tokens"),
        "total": _campo(resumo, "total_tokens"),
        "chamadas": _campo(resumo, "successful_requests"),
    }


def custo(entrada: int, saida: int):
    pe, ps = os.environ.get("IA_PROCON_PRECO_ENTRADA"), os.environ.get("IA_PROCON_PRECO_SAIDA")
    if not pe or not ps:
        return ""
    return round(entrada / 1e6 * float(pe) + saida / 1e6 * float(ps), 6)


def anexar_csv(caminho: Path, colunas: list, linhas: list) -> None:
    novo = not caminho.exists()
    with caminho.open("a", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        if novo:
            w.writerow(colunas)
        for linha in linhas:
            w.writerow([linha.get(c, "") for c in colunas])


def uma_execucao(caminho_caso: Path, base: str, rotulo: str, n: int, sem_raciocinio=()) -> None:
    """Roda a equipe uma vez, mede e salva. Propaga exceções (o chamador decide se para)."""
    reclamacao = caminho_caso.read_text(encoding="utf-8")
    llms = {a: app.criar_llm(sem_raciocinio=a in sem_raciocinio, agente=a) for a in AGENTES}      # um LLM por agente => contagem separada
    marcas = {}                                        # instante em que cada tarefa terminou

    def marcador(chave):
        return lambda _saida: marcas.__setitem__(chave, time.perf_counter())

    equipe = app.montar_equipe(reclamacao, base, llms, {a: marcador(a) for a in AGENTES})

    inicio = time.perf_counter()
    resultado = equipe.kickoff()
    resposta = app.limpar_vazamentos(getattr(resultado, "raw", None) or str(resultado))

    # tempo de cada agente = diferença entre o fim de uma tarefa e o fim da anterior
    tempos, anterior = {}, inicio
    for a in AGENTES:
        fim = marcas.get(a)
        tempos[a] = round(fim - anterior, 1) if fim else ""
        anterior = fim or anterior

    agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    base_linha = {"data_hora": agora, "rotulo": rotulo, "caso": caminho_caso.stem,
                  "execucao": n, "modelo": app.MODELO}

    linhas, soma = [], {"entrada": 0, "saida": 0, "total": 0, "chamadas": 0}
    for a in AGENTES:
        uso = ler_uso(llms[a])
        if uso is None:
            uso = {"entrada": "", "saida": "", "total": "", "chamadas": ""}
        else:
            for k in soma:
                soma[k] += uso[k]
        linhas.append({**base_linha, "modelo": getattr(llms[a], "model", app.MODELO), "agente": a, "tokens_entrada": uso["entrada"],
                       "tokens_saida": uso["saida"], "tokens_total": uso["total"],
                       "chamadas": uso["chamadas"], "segundos": tempos[a],
                       "custo_usd_estimado": custo(uso["entrada"], uso["saida"]) if uso["entrada"] != "" else ""})

    # conferência cruzada com o total que o próprio CrewAI informa
    total_crew = getattr(equipe, "usage_metrics", None)
    crew_total = _campo(total_crew, "total_tokens") if total_crew is not None else None
    linhas.append({**base_linha, "agente": "TOTAL_SOMA_AGENTES", "tokens_entrada": soma["entrada"],
                   "tokens_saida": soma["saida"], "tokens_total": soma["total"], "chamadas": soma["chamadas"],
                   "segundos": round(time.perf_counter() - inicio, 1),
                   "custo_usd_estimado": custo(soma["entrada"], soma["saida"])})
    linhas.append({**base_linha, "agente": "TOTAL_CREWAI_usage_metrics",
                   "tokens_total": crew_total if crew_total is not None else "n/d"})

    if soma["total"] == 0:
        print("  ATENÇÃO: contagem por agente veio zerada. Esta versão do CrewAI/provedor pode não "
              "registrar uso por LLM. Use a linha TOTAL_CREWAI_usage_metrics como referência.")
    elif crew_total and abs(crew_total - soma["total"]) > 0.05 * crew_total:
        print(f"  ATENÇÃO: soma por agente ({soma['total']}) difere do total do CrewAI ({crew_total}) em mais de 5%.")

    # verificações automáticas e arquivo da resposta
    avisos_art = app.verificar_citacoes(resposta, base) + app.verificar_referencias(resposta, base) + app.verificar_decreto(resposta)
    avisos_aspas = app.verificar_aspas(resposta, base, reclamacao=reclamacao)
    avisos_vaz = app.verificar_vazamentos(resposta)
    (PASTA / "respostas").mkdir(parents=True, exist_ok=True)
    arq = PASTA / "respostas" / f"{rotulo}_{caminho_caso.stem}_exec{n}.md"
    arq.write_text(
        f"# {caminho_caso.name} | rótulo {rotulo} | execução {n}\n\n{resposta.strip()}\n\n"
        f"## Avisos automáticos\n\n" + ("\n".join(f"- {x}" for x in avisos_art + avisos_aspas + avisos_vaz) or "- nenhum") + "\n",
        encoding="utf-8")

    anexar_csv(PASTA / "medicao.csv", COLS_MEDICAO, linhas)
    anexar_csv(PASTA / "avaliacao.csv", COLS_AVALIACAO, [{
        **base_linha, "arquivo_resposta": arq.name,
        "avisos_artigo_fora_da_base": len(avisos_art), "avisos_aspas_nao_literais": len(avisos_aspas),
        "avisos_vazamento_ou_ingles": len(avisos_vaz)}])

    print(f"  ok: {soma['total']} tokens, {soma['chamadas']} chamadas, "
          f"{round(time.perf_counter() - inicio, 1)} s. Salvo em {arq.name}")


def main() -> None:
    p = argparse.ArgumentParser(description="Mede tokens, chamadas e tempo por agente.")
    p.add_argument("--casos", nargs="*", help="arquivos de caso (padrão: casos_teste/c*.txt)")
    p.add_argument("--repeticoes", type=int, default=2, help="execuções por caso (padrão 2)")
    p.add_argument("--rotulo", default="v7", help="nome da versão do sistema, para comparar depois")
    p.add_argument("--sem-raciocinio", default=",".join(app.SEM_RACIOCINIO_PADRAO),
                   help="agentes com raciocínio desligado, separados por vírgula (padrão: triagem)")
    p.add_argument("--raciocinio-completo", action="store_true", help="liga o raciocínio em todos os agentes (como na v6)")
    p.add_argument("--pausa", type=float, default=0, help="segundos de espera entre execuções")
    args = p.parse_args()

    casos = [Path(c) for c in args.casos] if args.casos else sorted((app.RAIZ / "casos_teste").glob("c*.txt"))
    if not casos:
        raise SystemExit("Nenhum caso encontrado.")
    desligados = () if args.raciocinio_completo else tuple(x.strip() for x in args.sem_raciocinio.split(",") if x.strip())
    invalidos = [x for x in desligados if x not in AGENTES]
    if invalidos:
        raise SystemExit(f"Agente(s) desconhecido(s): {invalidos}. Use: {', '.join(AGENTES)}")
    if desligados:
        args.rotulo = f"{args.rotulo}-sr({'+'.join(desligados)})"   # o rótulo registra a configuração
    base = app.carregar_base()
    total = len(casos) * args.repeticoes
    print(f"{total} execuções planejadas ({len(casos)} casos x {args.repeticoes}). Rótulo: {args.rotulo}")

    feitas = 0
    for caso in casos:
        for n in range(1, args.repeticoes + 1):
            print(f"[{feitas + 1}/{total}] {caso.stem}, execução {n}")
            try:
                uma_execucao(caso, base, args.rotulo, n, desligados)
                feitas += 1
            except Exception as erro:
                texto = str(erro).lower()
                if any(s in texto for s in SINAIS_LIMITE):
                    print(f"\nPARADO: a API recusou por limite ou créditos.\nDetalhe: {str(erro)[:300]}\n"
                          f"{feitas} execução(ões) já estão salvas em {PASTA}. Espere alguns minutos "
                          f"(limite de 40 por minuto) ou confira sua conta, e rode de novo só o que faltou "
                          f"com --casos.")
                    return
                print(f"  ERRO nesta execução (seguindo para a próxima): {type(erro).__name__}: {str(erro)[:300]}")
            if args.pausa:
                time.sleep(args.pausa)
    print(f"\nConcluído: {feitas}/{total}. Arquivos em {PASTA}")


if __name__ == "__main__":
    main()
