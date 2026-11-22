"""
Diagnóstico de tokens: de onde vem a saída inflada (~14 mil tokens na Triagem)?

Faz UMA chamada direta à API da NVIDIA com o prompt da Triagem (sem CrewAI) e mostra:
  - o campo usage bruto devolvido pela API (inclusive detalhes, se existirem)
  - quantos caracteres vieram em reasoning_content (raciocínio) e em content (resposta)
Assim dá para ver se os tokens de saída são "pensamento" do modelo ou texto escrito.

Uso:
    python diagnostico_tokens.py                      # caso C1, modo normal
    python diagnostico_tokens.py casos_teste/c3_tv_defeito.txt
    python diagnostico_tokens.py --sem-raciocinio     # EXPERIMENTAL: tenta desligar o raciocínio

Observação: o prompt é montado como system (papel/objetivo/histórico) + user (tarefa e formato).
O CrewAI monta de forma parecida, mas não idêntica; use os números como ordem de grandeza.
O parâmetro de --sem-raciocinio (chat_template_kwargs/enable_thinking) vem da documentação de
outros modelos Nemotron da NVIDIA e NÃO foi confirmado para este modelo: se a API recusar ou ignorar,
o script informa.
"""
import argparse
import os
import time
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

import app
import prompts

load_dotenv()


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("caso", nargs="?", default=str(app.CASO_PADRAO))
    p.add_argument("--sem-raciocinio", action="store_true")
    args = p.parse_args()

    chave = os.environ.get("NVIDIA_API_KEY")
    if not chave:
        raise SystemExit("NVIDIA_API_KEY não encontrada no .env.")
    modelo = app.MODELO.removeprefix("openai/")
    reclamacao = Path(args.caso).read_text(encoding="utf-8").strip()

    ag = prompts.AGENTES["triagem"]
    tarefa = prompts.TAREFAS["triagem"]
    sistema = f"{ag['role']}\n{ag['backstory']}\nObjetivo: {ag['goal']}"
    usuario = app.preencher(tarefa["description"], RECLAMACAO=reclamacao) + \
        "\n\nFormato esperado:\n" + tarefa["expected_output"]

    extra = {"chat_template_kwargs": {"enable_thinking": False}} if args.sem_raciocinio else None
    cliente = OpenAI(base_url=app.URL_API, api_key=chave, timeout=600)
    conteudo, raciocinio, uso, fim = "", "", None, None
    n_cont = n_rac = 0
    t0 = ultimo = time.perf_counter()
    print(f"Chamando {modelo} ({'sem raciocínio, experimental' if args.sem_raciocinio else 'modo padrão'})... "
          "Ctrl+C mostra o que já chegou.")
    try:
        # streaming: mostra progresso e separa raciocínio de resposta conforme chegam
        fluxo = cliente.chat.completions.create(
            model=modelo, temperature=0.1, extra_body=extra, stream=True,
            stream_options={"include_usage": True},
            messages=[{"role": "system", "content": sistema}, {"role": "user", "content": usuario}])
        for pedaco in fluxo:
            if getattr(pedaco, "usage", None):
                uso = pedaco.usage
            if not pedaco.choices:
                continue
            d = pedaco.choices[0].delta
            rc = getattr(d, "reasoning_content", None) or (getattr(d, "model_extra", None) or {}).get("reasoning_content")
            if rc:
                raciocinio += rc; n_rac += 1
            if d.content:
                conteudo += d.content; n_cont += 1
            if pedaco.choices[0].finish_reason:
                fim = pedaco.choices[0].finish_reason
            if time.perf_counter() - ultimo > 10:
                ultimo = time.perf_counter()
                print(f"  {ultimo - t0:.0f} s | raciocínio: {len(raciocinio)} car. | resposta: {len(conteudo)} car.")
    except KeyboardInterrupt:
        print("\nInterrompido por você; resultado PARCIAL abaixo.")
    except Exception as e:
        print(f"Erro da API: {type(e).__name__}: {str(e)[:400]}")
    seg = time.perf_counter() - t0

    print(f"\nTempo: {seg:.1f} s | finish_reason: {fim}")
    print(f"usage bruto: {uso}")
    print(f"Caracteres em reasoning_content (raciocínio): {len(raciocinio)}")
    print(f"Caracteres em content (resposta): {len(conteudo)}")
    if uso is None:
        print("A API não enviou usage no streaming (ou foi interrompido). Compare os caracteres: "
              "~3,5 caracteres por token em português é uma estimativa grosseira.")
    print(f"Início do raciocínio: {raciocinio[:200]!r}")
    print(f"Início da resposta: {conteudo[:200]!r}")


if __name__ == "__main__":
    main()
