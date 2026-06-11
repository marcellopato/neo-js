# Neo.JS - Seu Assistente Pessoal Sênior de Backpocket 🚀🐳🎙️

![GitHub repo size](https://img.shields.io/github/repo-size/marcellopato/neo-js?style=for-the-badge&color=25D366)
![GitHub last commit](https://img.shields.io/github/last-commit/marcellopato/neo-js?style=for-the-badge&color=007aff)
![GitHub license](https://img.shields.io/github/license/marcellopato/neo-js?style=for-the-badge&color=5865F2)
![GitHub open issues](https://img.shields.io/github/issues/marcellopato/neo-js?style=for-the-badge&color=ef4444)

O **Neo** é um assistente pessoal autônomo local que conecta o seu WhatsApp diretamente ao shell do seu sistema operacional (**macOS** ou **Linux**). Ele é totalmente compatível com o **Antigravity CLI**, utilizando o **Google Antigravity SDK** com **Gemini** como motor cognitivo para processar linguagem natural, analisar código, gerenciar arquivos, comandos e infraestrutura Docker.

> 🎙️ **Voz:** Envie um áudio (PTT) no WhatsApp para si mesmo e o Neo transcreve e executa automaticamente.
> 🖥️ **Desktop:** Interface nativa em Go+Wails com ícone na bandeja do sistema para Linux/Zorin OS.
> 🧠 **Memória RAG:** Contexto semântico inteligente — o Neo lembra apenas do que é relevante, não de tudo.

### 👾 Aparência (Estilo Minecraft)

| Avatar do App / Tray | Corpo Inteiro |
|:---:|:---:|
| <img src="neo_head.png" width="180" /> | <img src="neo_full_body.png" width="180" /> |

---

## 🏗️ Arquitetura

A arquitetura do Neo é **Dockerizada**, orquestrada via `docker-compose`, com 4 serviços independentes:

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
- **🐳 Orquestração Docker:** Gerencia containers, lê logs, executa comandos no terminal.
- **💻 Engenharia de Software:** Expert sênior em PHP (Laravel), Node.js/TypeScript, Python e Flutter/Dart.
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
# Edite .env e preencha: GEMINI_API_KEY, INTERNAL_API_KEY, NEO_PASSWORD

# 2. Suba os containers
./start.sh

# 3. Escaneie o QR Code do WhatsApp
docker compose logs -f bridge
```

---

## 🔄 Migração da versão anterior

Se você estava usando uma versão anterior (sem Docker ou com ChromaDB), rode:

```bash
chmod +x migrate.sh && ./migrate.sh
```

O script remove caches incompatíveis e reinicializa o Docker. Você precisará escanear o QR Code novamente.

---

## 🚀 Rodando o Neo

```bash
./start.sh
```

Isso sobe todos os containers em modo daemon. Para verificar o status:

```bash
docker compose ps
```

Para ver logs em tempo real:

```bash
docker compose logs -f backend   # Agente Python
docker compose logs -f bridge    # WhatsApp Bridge
```

Para acessar o **Dashboard de Memória Vetorial**:
```
http://localhost:6333/dashboard
```

---

## 📦 Requisitos

- **Docker** + **Docker Compose** (v2+)
- **Node.js** (apenas para o `install.js` inicial)
- **Chave de API do Gemini** (Google AI Studio ou Google Cloud)

> Para o **Daemon Desktop** (Linux/Zorin OS): requer o binário `daemon` compilado com Go + Wails. Consulte `daemon/README.md`.

---

*Desenvolvido com carinho para simplificar e turbinar a vida de desenvolvedores modernos.* 🚀💻
