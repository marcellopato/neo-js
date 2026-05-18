# Neo.JS - Seu Assistente Pessoal de Pocket 🚀

O **Neo** é um agente autônomo local que faz a ponte entre o seu WhatsApp e o shell do seu sistema operacional (**Zorin OS**). Ele usa o **Gemini 2.0 Flash** como motor cognitivo para processar comandos em linguagem natural e gerenciar o seu ambiente de desenvolvimento.

## 🛠️ Habilidades Principais

- **Orquestração Docker:** Gerenciamento de containers, leitura de logs e status de serviços.
- **Desenvolvedor Sênior:** Expert em **PHP (Laravel)**, **Node.js** e **Python**.
- **Automação de Shell:** Execução de comandos bash para manutenção do sistema e organização de arquivos em `~/Documentos/www`.
- **Privacidade Total:** Filtro estrito para responder apenas no seu chat privado ("Você") e ignorar grupos ou terceiros.

## ⚙️ Tecnologias

- **Runtime:** Node.js (v22+)
- **IA:** Google Gemini SDK (`gemini-2.0-flash`)
- **WhatsApp:** `whatsapp-web.js` com autenticação local persistente.
- **Serviço:** Integrado via `systemd` para persistência (inicia com o boot do sistema).

## 🚀 Instalação e Uso

1. **Configuração:**
   Renomeie o `.env.example` para `.env` e adicione sua `GEMINI_API_KEY`.

2. **Início Manual:**
   ```bash
   npm install
   node index.js
   ```
   Escaneie o QR Code no terminal.

3. **Como Serviço (Persistence):**
   O projeto inclui um arquivo `neo.service` para ser usado com o `systemd`.

## 🛡️ Segurança

- **Modo Cauteloso:** Comandos de leitura (`ls`, `docker ps`, `cat`) são executados livremente.
- **Confirmação:** Comandos que alteram o sistema (`rm`, `apt`, `docker-compose down`) exigem um "OK" via WhatsApp antes de prosseguir.

---
*Criado para Marcello Pato - O braço direito do desenvolvedor moderno.* 🐳💻
