# Neo.JS - Seu Assistente Pessoal Sênior de Backpocket 🚀🐳🎙️

![GitHub repo size](https://img.shields.io/github/repo-size/marcellopato/neo-js?style=for-the-badge&color=25D366)
![GitHub stars](https://img.shields.io/github/stars/marcellopato/neo-js?style=for-the-badge&color=eab308)
![GitHub forks](https://img.shields.io/github/forks/marcellopato/neo-js?style=for-the-badge&color=fb923c)
![GitHub last commit](https://img.shields.io/github/last-commit/marcellopato/neo-js?style=for-the-badge&color=007aff)
![GitHub license](https://img.shields.io/github/license/marcellopato/neo-js?style=for-the-badge&color=5865F2)
![GitHub open issues](https://img.shields.io/github/issues/marcellopato/neo-js?style=for-the-badge&color=ef4444)

O **Neo** é um assistente pessoal autônomo local que conecta o seu WhatsApp diretamente ao shell do seu sistema operacional (**macOS** ou **Linux**). Ele é orgulhosamente impulsionado pela **Gemini Family** (utilizando o **Gemini 2.5 Flash** para máxima velocidade e economia), rodando sobre o **Google Antigravity SDK** como motor cognitivo para processar linguagem natural, escrever código, gerenciar arquivos e infraestrutura Docker.

> 🎙️ **Voz:** Envie um áudio (PTT) no WhatsApp para si mesmo e o Neo transcreve e executa automaticamente.
> 🖥️ **Desktop:** Interface nativa em Go+Wails com ícone na bandeja do sistema para Linux/Zorin OS.
> 🧠 **Memória RAG:** Contexto semântico inteligente — o Neo lembra apenas do que é relevante, não de tudo.

### 👾 Aparência (Estilo Minecraft)

| Avatar do App / Tray | Corpo Inteiro |
|:---:|:---:|
| <img src="neo_head.png" width="180" /> | <img src="neo_full_body.png" width="180" /> |

---

## 💸 Economia Absurda (Powered by Gemini 2.5 Flash)

O Neo foi projetado para extrair o máximo de autonomia com o mínimo de custo. Ao adotar o **Gemini 2.5 Flash** no coração do Antigravity SDK, conseguimos derrubar o custo de operação para frações de centavos, tornando-o imbatível quando comparado a soluções como OpenClaw ou OpenDevin.

| Plataforma / Agente | Custo Médio por Ciclo Autônomo Completo (Pensar, Codar, Testar) |
|---|---|
| OpenClaw (GPT-4o) | ~ R$ 1,50 a R$ 2,50 |
| Agent Padrão (Gemini 1.5 Pro) | ~ R$ 0,15 a R$ 0,30 |
| **Neo.JS (Gemini 2.5 Flash)** | **~ R$ 0,02 (Dois Centavos!)** |

Isso significa que você tem um Engenheiro de Software autônomo à sua disposição no WhatsApp, capaz de criar e executar scripts inteiros, cobrando quase nada pelo serviço.

---

## 🏗️ Arquitetura

A arquitetura do Neo roda **nativamente**, sem depender de Docker, com serviços independentes:

```mermaid
graph TD
    User([Você / WhatsApp]) <-->|WhatsApp Web Protocol| Bridge[neojs-bridge]
    Daemon([Desktop App\nGo + Wails]) <-->|HTTP POST /chat| Backend[neojs-backend]
    Bridge <-->|HTTP POST /chat| Backend
    Backend <-->|Google Antigravity SDK| GeminiAPI[Google Gemini API]
    Backend <-->|fastembed local\nzero API cost| Qdrant[neojs-qdrant\nQdrant Vector DB]
    Backend <-->|run_command / view_file| OS[Local OS / Terminal]
    Qdrant <-->|Persistência vetorial| Volume[./qdrant_data]
```

### Como a memória funciona (RAG para diálogos)

Em vez de enviar **todo o histórico** da conversa a cada mensagem (crescimento quadrático de tokens 📈), o Neo usa uma abordagem **RAG (Retrieval-Augmented Generation)**:

```
ABORDAGEM TRADICIONAL (cara):
Msg 10 → [system] + msg1 + msg2 + ... + msg10  ← ~10.000 tokens

ABORDAGEM RAG DO NEO (eficiente):
Msg 10 → [system] + [top-3 turns relevantes] + msg10  ← ~2.000 tokens constantes
```

Cada turno de conversa é vetorizado **localmente** com `fastembed` (modelo `BAAI/bge-small`, roda dentro do Docker, sem custo de API) e armazenado no **Qdrant**. A cada nova mensagem, os 3 turnos semanticamente mais relevantes são recuperados e injetados como contexto.

### Serviços

| Serviço | Tecnologia | Porta | Função |
|---|---|---|---|
| `neojs-backend` | Python + FastAPI + Antigravity SDK | `5000` | Núcleo cognitivo do Neo |
| `neojs-bridge` | Node.js + whatsapp-web.js | `3303` | Bridge WhatsApp Web |
| `neojs-qdrant` | Qdrant (Rust) | `6333` / `6334` | Memória vetorial + Dashboard |
| `daemon` (optional) | Go + Wails | — | App desktop Linux/Zorin OS |

### Controle de custo de tokens

- **Sessão do Agent:** reseta automaticamente a cada **10 trocas**, evitando acúmulo de contexto
- **Embeddings locais:** `fastembed` roda offline dentro do container, **zero custo de API**
- **Score threshold:** turnos com relevância < 0.5 são ignorados (não poluem o contexto)
- **Limite de chars:** payload de cada turno armazenado é limitado a 1.000 chars

### 🔍 Qdrant Dashboard

Quando o Neo estiver rodando, acesse `http://localhost:6333/dashboard` para visualizar em tempo real os diálogos vetorizados, pontos armazenados e fazer buscas semânticas na memória do Neo.

### 🖥️ Daemon Desktop & Tray (Linux/Zorin OS)

Um **Daemon Desktop** nativo em Go e Wails adiciona uma camada de interface gráfica:

- **Instância Única:** Impede processos duplicados usando sockets Unix.
- **Menu da Bandeja:** Ícone ao lado do relógio para abrir o chat, configurações ou encerrar.
- **Fechar em Background:** O botão `X` oculta a janela sem matar o processo.
- **Configuração de API Key:** Adicione sua chave Gemini de forma segura pela UI.
- **Atalhos Globais:** Configure hotkeys globais pela interface.
- **Entrada por Voz:** Clique no microfone no chat para enviar comandos por áudio — transcrição automática via Gemini.

---

## 🛠️ Habilidades Principais

- **🎙️ Comandos por Voz:** Grave um áudio (PTT) no WhatsApp ou no app desktop — o Neo transcreve e executa.
- **🧠 Memória Semântica RAG:** Lembra conversas relevantes via busca vetorial no Qdrant (sem enviar tudo ao LLM).
- **⚙️ Execução Nativa:** Leve e rápido, roda diretamente no Linux, macOS e Windows sem depender de Docker.
- **💻 Engenharia de Software:** Expert sênior em PHP (Laravel), Node.js/TypeScript, Python e Flutter/Dart.
- **🛡️ Auto-Reparo (Self-Healing):** A bridge do WhatsApp atua como um sensor. Se o WhatsApp Web for atualizado e quebrar a conexão, o Neo detecta a falha, atualiza sua própria biblioteca (`whatsapp-web.js`) e reinicia de forma 100% autônoma!
- **🗜️ Headroom Proxy Integrado:** Otimização avançada de tokens interceptando a comunicação da SDK e comprimindo os prompts antes de chegar no Google Gemini, garantindo máxima economia no longo prazo.
- **🔒 Privacidade:** Processa apenas mensagens do Self-Chat (você para você mesmo).

---

## 💻 Instalação & Setup

### 🔑 Obtendo sua API Key do Gemini

#### 1. Google AI Studio (Grátis com limites)
1. Acesse [Google AI Studio](https://aistudio.google.com/) e faça login.
2. Clique em **Get API Key** > **Create API Key**.
3. Copie a chave (começa com `AIzaSy`).

> ⚠️ Chaves gratuitas têm limites de requisições por minuto. Para uso contínuo, recomendamos ativar faturamento.

#### 2. Google Cloud Console (Faturamento Ativo — Recomendado)
1. Acesse o [Google Cloud Console](https://console.cloud.google.com/).
2. Crie/selecione um projeto e ative o **Faturamento (Billing)**.
3. Vá em **APIs & Services > Library**, ative a **Generative Language API**.
4. Vá em **APIs & Services > Credentials** > **+ Create Credentials > API Key**.
5. *(Recomendado)* Restrinja a chave para a Generative Language API.

---

### 🚀 Instalação Rápida

```bash
git clone https://github.com/marcellopato/neo-js.git && cd neo-js && node install.js
```

O instalador interativo configura o `.env`, detecta versões antigas e oferece migração automática.

### 🔧 Instalação Manual

```bash
# 1. Configure o ambiente
cp .env.example .env
# Edite .env e preencha as variáveis como GEMINI_API_KEY

# 2. Inicie o sistema
# O script abaixo cuidará de instalar as dependências de Node e Python e iniciar os processos.
# No Linux / macOS:
chmod +x start.sh
./start.sh

# No Windows (PowerShell):
# Certifique-se de ter Node.js e Python instalados.
python -m venv venv
.\venv\Scripts\pip install -r requirements.txt
npm install
# Inicie o backend:
start /B .\venv\Scripts\python agent.py
# Inicie a bridge:
node bridge.js
```

---

## 🔄 Migração da versão anterior

Se você estava usando uma versão anterior (sem Docker ou com ChromaDB), rode:

```bash
chmod +x migrate.sh && ./migrate.sh
```

O script remove caches antigos (caso existam) e prepara o ambiente para rodar nativamente.

---

## 🚀 Rodando o Neo

```bash
./start.sh
```

Isso inicia o backend em background e a bridge (Node.js) em foreground.
No primeiro uso, o QR Code do WhatsApp Web aparecerá direto no seu terminal para você escanear.

**No Windows:**
```powershell
start /B .\venv\Scripts\python agent.py
node bridge.js
```

Para acessar o **Dashboard de Memória Vetorial**:
```
http://localhost:6333/dashboard
```

---

## 📦 Requisitos

- **Node.js** (v18+)
- **Python** (v3.10+)
- **Chave de API do Gemini** (Google AI Studio ou Google Cloud)

> Para o **Daemon Desktop** (Linux/Zorin OS): requer o binário `daemon` compilado com Go + Wails. Consulte `daemon/README.md`.

---

## 🤝 Contribuidores

O Neo.JS é uma iniciativa open-source e prospera graças à comunidade. Sinta-se à vontade para abrir Issues, enviar Pull Requests e sugerir novas integrações. 

- **Marcello Pato** - Idealizador e desenvolvedor principal.
- **Comunidade** - Junte-se a nós para transformar o Neo no agente de IA mais acessível do mundo!

---

*Desenvolvido com carinho para simplificar e turbinar a vida de desenvolvedores modernos.* 🚀💻
