# IA PROCON – sistema multiagente com NVIDIA Nemotron

Projeto acadêmico: quatro agentes de IA (CrewAI) analisam, em sequência, a reclamação de um consumidor
usando uma base de conhecimento jurídica **local** (Código de Defesa do Consumidor completo, Decreto 7.962/2013
e orientações do projeto) e devolvem uma resposta curta, em linguagem simples.

> **Aviso.** Esta ferramenta é um protótipo educacional. Ela **não** é orientação jurídica oficial, não
> substitui o PROCON, a Defensoria Pública ou um advogado, e pode errar (veja *Limitações*). Confirme sempre
> nos textos oficiais (Planalto) e em órgão de defesa do consumidor.

## Como funciona

```
Relato do consumidor
   -> 1. Triagista            organiza fatos, datas, canal de contratação, defeito sim/não
   -> 2. Pesquisador Jurídico relaciona os fatos aos trechos da base (cita literalmente, confere condições)
   -> 3. Auditor              confere o que o Pesquisador afirmou contra os fatos e a base
   -> 4. Redator              escreve a resposta final ("você", até ~180 palavras, 4 seções)
   -> verificadores automáticos (código, sem IA): artigos/§/incisos que não existem, aspas não literais,
      palavras internas ou em inglês, "Art. N do Decreto 7.962" acima do Art. 7º
```

A comunicação entre agentes é sequencial: a saída de cada tarefa vira contexto da seguinte
(`Process.sequential` do CrewAI). Pesquisador e Auditor recebem a Lei 8.078 inteira (~20 mil tokens).

## Instalação (Windows / PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
copy .env.example .env      # depois edite o .env e coloque sua NVIDIA_API_KEY
```

A chave vem do catálogo gratuito da NVIDIA (https://build.nvidia.com). **Nunca** envie o `.env` ao repositório
(já está no `.gitignore`).

## Uso

```powershell
python chat_web.py                          # interface de chat em http://127.0.0.1:8000
python app.py casos_teste\c1_jaqueta_online.txt   # análise de um caso pelo terminal (salva em saidas/)
python medir.py --repeticoes 3 --rotulo meu-teste # mede tokens, tempo e gera planilha de avaliação
```

Variáveis opcionais (no `.env`): `IA_PROCON_MODELO`, `IA_PROCON_VERBOSE=0`, `IA_PROCON_TEMPERATURA` (padrão 0,1),
`IA_PROCON_SEM_RACIOCINIO` (padrão `todos`).

## Estrutura

| Arquivo | Função |
|---|---|
| `app.py` | monta os agentes/tarefas, roda a equipe e os verificadores |
| `prompts.py` | prompts dos 4 agentes (genéricos, sem conhecimento jurídico embutido) |
| `chat_web.py` | interface de chat simples (biblioteca padrão do Python) |
| `medir.py` | medição de tokens/tempo por agente e planilha de avaliação |
| `base_conhecimento/` | `cdc_lei_8078.txt`, `decreto_7962_2013.txt`, `orientacoes_projeto.txt` |
| `casos_teste/` | 3 casos e `gabaritos.md` (provisório) |

## Modelo e custo

Modelo: `nvidia/nemotron-3.5-lightning-30b-a3b` (30 B de parâmetros, ~3 B ativos), endpoint da NVIDIA, camada
gratuita (limite de ~40 requisições/min). É um modelo com "raciocínio"; desligá-lo
(`enable_thinking=False`) reduziu a saída em ~90% e o tempo de ~335 s para ~25–35 s por análise.

Configuração final (v10-A, 15 execuções): ~47,5 mil tokens de entrada, ~5,2 mil de saída, ~25 s por análise.
Com raciocínio só no Auditor (v10-B): ~22,5 mil tokens de saída e ~122 s.

## Como os prompts foram ajustados

Método: 3 casos (C1 compra online com arrependimento; C2 compra em loja física sem defeito, controle
negativo; C3 TV com defeito) × várias execuções, nota 0–10 contra gabarito. **Notas provisórias, atribuídas
pelo assistente de IA que apoiou o projeto, e não por avaliador humano independente**; com poucas execuções,
diferenças de ~0,5 ponto estão dentro do ruído.

| Versão | Mudança | Nota média* | Entrada (tokens) | Saída (tokens) | Tempo |
|---|---|---|---|---|---|
| v6 | prompts longos, raciocínio ligado, 3 artigos | 5,67 | – | ~60 mil | ~408 s |
| v7 | 3 artigos, só Triagem sem raciocínio | 4,78 | 15,4 mil | 43,0 mil | 289 s |
| v7 + CDC completo | base completa, só Triagem sem raciocínio | 5,67 | 46,3 mil | 57,0 mil | 335 s |
| v7 + CDC completo, todos sem raciocínio (A) | | 4,89 | 47,2 mil | 5,5 mil | 26 s |
| v7 + CDC completo, Auditor com raciocínio (B) | | 5,33 | 47,1 mil | 26,0 mil | 146 s |
| v8 | mais regras nos prompts | 4,44 | 47,9 mil | 5,5 mil | 30 s |
| v9 | prompts compactos, respostas curtas | 5,33 | 43,2 mil | 4,2 mil | 31 s |
| v9, temperatura 0 | | 4,56 | 43,3 mil | 4,3 mil | 34 s |
| v9 + Decreto 7.962 | acrescenta o decreto à base | ≈ 4,7–5 | 47,2 mil | 5,2 mil | 35 s |
| v10-canal | campo "compra fora da loja física" na Triagem | ≈ 6,7 (9 exec.) | 47,9 mil | 5,2 mil | 26 s |
| **v10-A (final)** | mesma versão, todos sem raciocínio, 15 exec. | ≈ 5,3 | 47,5 mil | 5,2 mil | 25 s |
| v10-B | v10 com raciocínio no Auditor, 15 exec. | ≈ 5,8 | 46,3 mil | 22,5 mil | 122 s |

\* notas provisórias atribuídas por IA; tokens e tempos são médias por análise (arquivo `medicao.csv`; v6 de
medição anterior, sem entrada registrada aqui).

Aprendizados: regras demais pioram um modelo de poucos parâmetros ativos (v8 vs v9); temperatura 0 não ajudou;
o modelo lia "especialmente por telefone ou a domicílio" do Art. 49 como excluindo a internet até a Triagem
passar a marcar explicitamente se a compra foi fora da loja física; adicionar mais uma fonte à base sozinho não
resolveu.

## Limitações conhecidas

- **Confiabilidade.** No caso de compra online (C1) a conclusão correta saiu em cerca de 5 de 8 execuções da
  configuração final; em C3 há erros de contagem de datas e de lógica de prazos. Não use as respostas como
  decisão.
- Cita "§ 1º" do Art. 49 (a lei só tem parágrafo único) e artigos sem relação com o caso; os verificadores
  avisam sobre existência, **não sobre o conteúdo**.
- Cita às vezes artigo inexistente do Decreto 7.962 (só tem os Arts. 1º a 7º; o verificador avisa).
- Verificadores têm limites (ex.: não conferem decreto, "parecer" como verbo gera falso positivo).
- Base: vigência conferida no Planalto apenas para os Arts. 18, 26 e 49; o restante vem do PDF do MJ (2013) e
  pode estar desatualizado (ex.: Lei 14.181/2021 não incluída). `orientacoes_projeto.txt` é texto do projeto,
  sem fonte oficial.
- Amostra pequena (3 casos, 9–15 execuções por configuração), notas por um único avaliador de IA.
- Possível melhoria: busca dos artigos relevantes (em vez da lei inteira), cálculo de datas em código, modelo
  maior ou raciocínio só no Auditor, avaliação humana, e revisão por profissional do direito.
