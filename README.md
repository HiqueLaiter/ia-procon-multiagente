# IA PROCON — Sistema Multiagente para Análise de Reclamações de Consumidores

## Sobre o projeto

O IA PROCON é um projeto acadêmico que utiliza inteligência artificial e sistemas multiagentes para auxiliar na análise de reclamações de consumidores, considerando informações fornecidas pelo usuário e uma base de conhecimento relacionada ao Código de Defesa do Consumidor (CDC).

A aplicação utiliza o framework CrewAI para organizar agentes especializados que trabalham em sequência, cada um contribuindo com uma etapa da análise.

## Objetivos

- Demonstrar a aplicação de sistemas multiagentes em um problema prático.
- Organizar a análise de reclamações em etapas especializadas.
- Consultar uma base de conhecimento sobre direitos do consumidor.
- Produzir uma resposta estruturada com base nos fatos apresentados.
- Explorar o uso de modelos de linguagem da NVIDIA.

## Como funciona

O sistema possui quatro agentes:

1. **Triagem:** organiza e identifica os principais fatos da reclamação.
2. **Pesquisa jurídica:** consulta a base de conhecimento e identifica os dispositivos legais potencialmente aplicáveis.
3. **Auditoria:** revisa a análise produzida e verifica a coerência das conclusões.
4. **Redação:** organiza o resultado final em uma resposta clara para o consumidor.

Os agentes são executados sequencialmente por meio do CrewAI.

## Tecnologias utilizadas

- **Python 3.13:** linguagem de programação.
- **CrewAI:** criação e orquestração dos agentes.
- **NVIDIA API:** acesso ao modelo de linguagem.
- **python-dotenv:** carregamento de variáveis de ambiente.
- **Git e GitHub:** controle de versão e hospedagem do código.

## Estrutura do projeto

```text
ia-procon-multiagente/
├── app.py
├── requirements.txt
├── .env                  # Criado localmente; não deve ser enviado ao Git
├── .gitignore
├── README.md
└── base_conhecimento/
    └── cdc.txt
```

## Pré-requisitos

- Windows 10 ou 11.
- Python 3.13.
- Git.
- Uma chave de API válida da NVIDIA.

## Configuração do ambiente

### 1. Clone o repositório

```powershell
git clone https://github.com/HiqueLaiter/ia-procon-multiagente.git
cd ia-procon-multiagente
```

### 2. Crie o ambiente virtual

```powershell
py -3.13 -m venv .venv
```

### 3. Ative o ambiente virtual

No PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

Se o ambiente já estiver ativado, não é necessário repetir essa etapa.

### 4. Instale as dependências

```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Caso o arquivo `requirements.txt` ainda não declare todas as dependências utilizadas, confira se ele inclui as versões necessárias do CrewAI e do python-dotenv. No ambiente utilizado durante o desenvolvimento, foi instalado o CrewAI `1.15.27`.

### 5. Configure a chave da NVIDIA

Crie um arquivo chamado `.env` na raiz do projeto e adicione:

```dotenv
NVIDIA_API_KEY=sua_chave_api_aqui
```

Substitua o valor de exemplo pela sua chave real. Não compartilhe essa chave e não envie o arquivo `.env` para o GitHub.

### 6. Execute a aplicação

Com o ambiente virtual ativado, execute:

```powershell
python app.py
```

A aplicação enviará as tarefas dos agentes ao modelo configurado e exibirá o resultado da análise no terminal. A execução depende de conexão com a internet e de uma chave de API válida.

## Base de conhecimento

O arquivo `base_conhecimento/cdc.txt` reúne os trechos e orientações legais utilizados pela aplicação como referência para a análise das reclamações.

A qualidade das respostas depende da precisão e da atualização dessa base, das instruções dadas aos agentes e das informações fornecidas pelo usuário.

## Segurança

- Mantenha a chave da NVIDIA no arquivo `.env`.
- Não publique credenciais, tokens ou outras informações secretas.
- O `.gitignore` deve excluir `.env` e o ambiente virtual `.venv/`.
- Antes de enviar alterações ao GitHub, confira os arquivos preparados para commit.

## Limitações

Este projeto tem finalidade acadêmica e demonstrativa. As respostas geradas por inteligência artificial podem conter erros ou interpretações jurídicas incorretas. O resultado não substitui a consulta à legislação atualizada nem a orientação de um profissional qualificado.

A base de conhecimento é limitada ao conteúdo efetivamente disponibilizado no projeto. Portanto, a aplicação não deve ser considerada uma fonte jurídica completa ou definitiva.

## Execução do fluxo multiagente

O fluxo geral da aplicação é:

```text
Reclamação do consumidor
          |
          v
   Agente de Triagem
          |
          v
 Agente de Pesquisa Jurídica
          |
          v
    Agente de Auditoria
          |
          v
     Agente de Redação
          |
          v
     Resposta final
```

## Status do projeto

O fluxo multiagente já foi executado localmente com sucesso utilizando o CrewAI e a API da NVIDIA. O projeto permanece sujeito a melhorias nas instruções dos agentes, na base de conhecimento e na validação das respostas jurídicas.
