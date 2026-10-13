# 🤖 IA PROCON - Sistema Multiagente com NVIDIA Nemotron

Este é um projeto de estudo e implementação de um **Sistema Multiagente de IA (IA PROCON)** focado em Direitos do Consumidor. A arquitetura utiliza o framework **CrewAI** integrado ao modelo **NVIDIA Nemotron v3/v4** para interpretar reclamações, buscar bases legais locais, auditar prazos/conformidade e gerar uma resposta didática com plano de ação para o cidadão.

---

## 🏢 Arquitetura dos Agentes

O sistema é dividido em uma esteira sequencial de 4 agentes especializados:
1. **Triagista:** Remove a carga emocional do relato e extrai os fatos puros e cronológicos.
2. **Pesquisador Jurídico:** Cruza os fatos estritamente com a base de conhecimento legal fornecida.
3. **Auditor de Compliance:** Valida prazos contratuais e confere se a fundamentação jurídica está 100% correta.
4. **Redator Social:** Traduz o jargão jurídico para uma linguagem simples, acolhedora e fornece um passo a passo prático para o consumidor.

---

## 🛠️ Pré-requisitos e Instalação

Para rodar este projeto na sua máquina local, certifique-se de ter o **Python 3.10+** instalado e siga os passos abaixo:

### 1. Clonar o Repositório
```bash
git clone https://github.com
cd ia-procon-multiagente
```

### 2. Criar e Ativar o Ambiente Virtual (venv)
* **Windows:**
  ```bash
  python -m venv venv
  .\venv\Scripts\activate
  ```
* **Linux/Mac:**
  ```bash
  python3 -m venv venv
  source venv/bin/activate
  ```

### 3. Instalar as Dependências
```bash
pip install crewai litellm
```

### 4. Configurar as Chaves de API
1. Crie um arquivo chamado `.env` na raiz do projeto.
2. Acesse o [NVIDIA Build](https://nvidia.com), gere sua chave gratuita (`nvapi-...`) e insira no arquivo:
   ```text
   NVIDIA_API_KEY=sua_chave_aqui
   ```

---

## 🚀 Como Executar

Com o ambiente virtual ativado e a chave configurada no arquivo `.env`, execute o comando:
```bash
python app.py
```
O console exibirá o log do CrewAI mostrando a interação e a linha de raciocínio de cada agente em tempo real até a impressão do parecer final.
