require('dotenv').config();
const { Client, LocalAuth } = require('whatsapp-web.js');
const qrcode = require('qrcode-terminal');
const { GoogleGenAI } = require('@google/genai');
const { exec } = require('child_process');

const genAI = new GoogleGenAI({ apiKey: process.env.GEMINI_API_KEY });

const SYSTEM_PROMPT = `Você é o Neo, o assistente pessoal de IA do Marcello.
Você vive no Zorin OS dele e tem acesso ao terminal.

PERSONALIDADE:
- Parceiro, sênior e descontraído. Use emojis como 🚀, 🐳 ou 💻 ocasionalmente.
- Seu foco principal é ajudar Marcello com seus projetos em ~/Documentos/www.
- Você é expert em PHP, Node.js, Python e Docker.

REGRAS DE OPERAÇÃO:
1. SEGURANÇA (MUITO IMPORTANTE): 
   - Comandos de LEITURA (ls, cat, docker ps, logs) podem ser rodados livremente ('execute').
   - Comandos de ALTERAÇÃO (rm, mv, docker-compose up/down, apt install) EXIGEM que você primeiro peça permissão ('reply'). Explique o que vai fazer e espere um "ok".
2. PRIVACIDADE ABSOLUTA:
   - Você SÓ responde no chat privado do Marcello consigo mesmo (Self-Chat).
   - Ignora grupos, newsletters e conversas com QUALQUER outra pessoa.
3. FORMATO: Responda APENAS com JSON.

{
  "thought": "Seu raciocínio interno.",
  "action_type": "reply" | "execute",
  "action_content": "texto ou comando"
}`;

let lastAgentMessage = "";
const history = [{ role: 'user', parts: [{ text: SYSTEM_PROMPT }] }];

const client = new Client({
    authStrategy: new LocalAuth(),
    puppeteer: { 
        args: ['--no-sandbox', '--disable-setuid-sandbox'],
        headless: true
    }
});

client.on('qr', qr => qrcode.generate(qr, { small: true }));

client.on('ready', () => {
    console.log('\n[✓] Neo está ONLINE!');
    console.log('ID Logado:', client.info.wid._serialized);
});

client.on('message_create', async (msg) => {
    // CAPTURA DE SEGURANÇA:
    // O ID do 'Self-Chat' (Você) pode ser diferente do ID logado (ex: termina em @lid).
    // Identificamos que no seu caso o Self-Chat é: 16174981058753@lid
    
    const isFromMe = msg.fromMe === true;
    const isGroup = msg.to.includes('@g.us') || msg.from.includes('@g.us') || msg.to.includes('@newsletter');
    
    // Filtro Estrito: 
    // 1. Mensagem enviada por você (fromMe)
    // 2. Destino é o ID do Self-Chat (conhecido via debug: 16174981058753@lid)
    // 3. NÃO é grupo
    // 4. Não é a própria resposta do Neo
    const isSelfChat = msg.to === '16174981058753@lid' || msg.to === client.info.wid._serialized;

    if (isFromMe && isSelfChat && !isGroup && msg.body !== lastAgentMessage) {
        console.log(`\n[Neo]: Comando recebido no chat privado: ${msg.body}`);
        await processTurn(`[USER]: ${msg.body}`, msg.to);
    }
});

async function processTurn(inputData, chatId, retryCount = 0) {
    try {
        history.push({ role: 'user', parts: [{ text: inputData }] });

        const response = await genAI.models.generateContent({
            model: 'gemini-2.0-flash',
            contents: history,
            generationConfig: { responseMimeType: 'application/json', temperature: 0.2 }
        });

        let replyText = response.candidates[0].content.parts[0].text;
        replyText = replyText.replace(/```json\n?/, '').replace(/```\n?$/, '').trim();

        const data = JSON.parse(replyText);
        history.push({ role: 'model', parts: [{ text: replyText }] });

        if (data.action_type === 'reply') {
            lastAgentMessage = data.action_content;
            await client.sendMessage(chatId, data.action_content);
        } else if (data.action_type === 'execute') {
            console.log(`[Neo]: Executando -> ${data.action_content}`);
            exec(data.action_content, { timeout: 30000, maxBuffer: 1024 * 1024 }, async (error, stdout, stderr) => {
                const out = error ? `Erro: ${error.message}` : stdout;
                await processTurn(`[SYSTEM]: ${out}`, chatId);
            });
        }
    } catch (err) {
        if (err.message.includes('429') && retryCount < 2) {
            setTimeout(() => processTurn(inputData, chatId, retryCount + 1), 3000);
        } else {
            console.error('[Erro]:', err.message);
        }
    }
}

client.initialize();
