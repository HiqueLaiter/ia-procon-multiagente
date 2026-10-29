import os
from crewai import Agent, Task, Crew, Process, LLM  # Adicionado o 'LLM' do CrewAI
from dotenv import load_dotenv

load_dotenv()

# -------------------------------------------------------------
# 1. FUNÇÃO AUXILIAR DE LEITURA (SIMULANDO RAG SIMPLES)
# -------------------------------------------------------------
def ler_base_conhecimento():
    caminho = os.path.join("base_conhecimento", "cdc.txt")
    try:
        with open(caminho, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return "Base de conhecimento não encontrada."

base_legal_txt = ler_base_conhecimento()

# -------------------------------------------------------------
# 2. CONFIGURAÇÃO DA CONEXÃO COM O NEMOTRON VIA vLLM
# -------------------------------------------------------------
# Certifique-se de que o vLLM está rodando no localhost na porta 8000
# -------------------------------------------------------------

nemotron_llm = LLM(
    model="openai/nvidia/nemotron-3.5-lightning-30b-a3b",
    base_url="https://integrate.api.nvidia.com/v1",
    api_key=os.environ.get("NVIDIA_API_KEY"),
    temperature=0.1
)


print("🤖 Iniciando o Sistema Multiagente IA PROCON...")

# -------------------------------------------------------------
# 3. CRIAÇÃO DOS AGENTES
# -------------------------------------------------------------

agente_triagem = Agent(
    role="Especialista em Triagem do Consumidor",
    goal="Analisar a mensagem do reclamante, extrair os fatos crus (datas, produto, local da compra) e isolar o problema central.",
    backstory="Você trabalha no balcão de entrada do PROCON. Seu trabalho é remover a carga emocional do relato e transformá-lo em uma lista técnica de acontecimentos cronológicos.",
    verbose=True,
    llm=nemotron_llm
)

agente_pesquisador = Agent(
    role="Pesquisador Jurídico do CDC",
    goal="Analisar os fatos e cruzar estritamente com os artigos disponíveis na base de conhecimento fornecida para encontrar o direito do cidadão.",
    backstory="Você é um assistente jurídico focado no Código de Defesa do Consumidor. Você é proibido de inventar leis. Você deve usar apenas os textos fornecidos a você.",
    verbose=True,
    llm=nemotron_llm
)

agente_auditor = Agent(
    role="Auditor de Compliance Jurídico",
    goal="Validar se os artigos apontados pelo pesquisador se aplicam perfeitamente às datas e fatos coletados na triagem.",
    backstory="Você é um advogado rigoroso. Se o consumidor perdeu um prazo legal ou se o artigo citado não se encaixa na situação, você deve alertar e corrigir o erro imediatamente.",
    verbose=True,
    llm=nemotron_llm
)

agente_redator = Agent(
    role="Redator e Comunicador Social do PROCON",
    goal="Escrever uma resposta clara, empática, didática e de fácil entendimento para o cidadão, explicando se ele tem direito e listando um passo a passo do que fazer.",
    backstory="Você traduz o direito complexo para pessoas comuns. Sua resposta deve ser direta, acolhedora e citar expressamente qual artigo fundamenta a ação do consumidor.",
    verbose=True,
    llm=nemotron_llm
)

# -------------------------------------------------------------
# 4. ENTRADA DA RECLAMAÇÃO DO USUÁRIO
# -------------------------------------------------------------
reclamacao_usuario = """
Olá, preciso de ajuda. No dia 05 de Outubro comprei uma jaqueta de couro por um site da internet. 
A jaqueta chegou na minha casa no dia 10 de Outubro. Só que quando experimentei, vi que ficou muito 
apertada e não gostei do caimento. No dia 12 de Outubro mandei mensagem para a loja pedindo a devolução 
e o reembolso, mas o atendente disse que roupas compradas na promoção não têm direito a devolução se 
não tiverem defeito de fábrica. Isso está certo? O que eu faço?
"""

# -------------------------------------------------------------
# 5. DEFINIÇÃO FLUXO DE TAREFAS (WORKFLOW)
# -------------------------------------------------------------

tarefa_triagem = Task(
    description=f"Analise o seguinte relato: '{reclamacao_usuario}'. Extraia: 1. Canal de compra, 2. Data de recebimento, 3. Problema alegado e 4. Prazo entre o recebimento e o pedido de devolução.",
    expected_output="Um relatório técnico listando detalhadamente apenas os dados factuais mapeados.",
    agent=agente_triagem
)

tarefa_pesquisa = Task(
    description=f"""Com base na triagem dos fatos, leia nossa base
legal e identifique os artigos aplicáveis.

IMPORTANTE:
- Compras pela internet são abrangidas pelo direito de
  arrependimento do Art. 49 do CDC.
- Não afirme que o Art. 49 exclui compras online.
- Não confunda arrependimento com defeito do produto.
- O fato de o produto estar em promoção não elimina, por si
  só, o direito de arrependimento.
- Fundamente as conclusões na base legal fornecida.
- Se faltarem informações, declare essa limitação.

BASE LEGAL DISPONÍVEL:
{base_legal_txt}""",
    expected_output="Uma seleção exata dos artigos aplicáveis ao caso com a explicação literal deles.",
    agent=agente_pesquisador
)

tarefa_auditoria = Task(
    description="Examine a triagem dos fatos e a pesquisa jurídica. Verifique se o prazo do artigo selecionado bate com a cronologia da compra e se o argumento da loja (de ser peça de promoção) faz sentido perante a lei.",
    expected_output="Um parecer de conformidade validando os artigos ideais para o caso.",
    agent=agente_auditor
)

tarefa_resposta_final = Task(
    description="Formule a orientação definitiva que será exibida ao cidadão no chat. Escreva de forma simples, diga de cara se ele está certo, explique o artigo da lei aplicável e forneça um plano de ação ('Passo 1, Passo 2...') para ele resolver o problema com a empresa.",
    expected_output="Uma mensagem estruturada em português, limpa, sem termos técnicos difíceis, referenciando o artigo da lei correspondente de forma evidente.",
    agent=agente_redator
)

# -------------------------------------------------------------
# 6. EXECUÇÃO DO PROJETO
# -------------------------------------------------------------

equipe_procon = Crew(
    agents=[agente_triagem, agente_pesquisador, agente_auditor, agente_redator],
    tasks=[tarefa_triagem, tarefa_pesquisa, tarefa_auditoria, tarefa_resposta_final],
    process=Process.sequential  # Executa uma tarefa após a outra em formato de esteira
)

resultado_final = equipe_procon.kickoff()

print("\n======================= ORIENTAÇÃO IA PROCON =======================\n")
print(resultado_final)