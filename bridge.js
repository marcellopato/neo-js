require('dotenv').config();
const { Client, LocalAuth } = require('whatsapp-web.js');
const qrcode = require('qrcode-terminal');
const http = require('http');
const { GoogleGenAI } = require('@google/genai');

const genAI = new GoogleGenAI({ apiKey: process.env.GEMINI_API_KEY });

let lastAgentMessage = "";
let pendingAsk = null; // { resolve, timer, command }
let isLocked = true; // Bot starts locked
let currentQR = null;
let isConnected = false;

function withTimeout(promise, timeoutMs, errorMessage) {
    let timeoutId;
    const timeoutPromise = new Promise((_, reject) => {
        timeoutId = setTimeout(() => {
            reject(new Error(errorMessage || 'Operação excedeu o tempo limite.'));
        }, timeoutMs);
    });
    return Promise.race([promise, timeoutPromise]).finally(() => clearTimeout(timeoutId));
}


// Start WhatsApp Client
const client = new Client({
    authStrategy: new LocalAuth(),
    puppeteer: { 
        executablePath: process.env.PUPPETEER_EXECUTABLE_PATH || undefined,
        args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage'],
        headless: true
    }
});

async function sendBridgeMessage(chatId, text) {
    const isSelfChat = chatId === client.info.wid._serialized || 
                       chatId.includes('16174981058753') || 
                       chatId.includes('228191662801065');
    if (isSelfChat) {
        lastAgentMessage = text;
    }
    return await client.sendMessage(chatId, text);
}

client.on('qr', qr => {
    qrcode.generate(qr, { small: true });
    currentQR = qr;
});

client.on('ready', () => {
    console.log('\n[✓] Bridge do WhatsApp está ONLINE!');
    console.log('ID Logado:', client.info.wid._serialized);
    currentQR = null;
    isConnected = true;

    // Watchdog para evitar travamento silencioso do Chromium/Puppeteer
    setInterval(async () => {
        try {
            if (client.pupPage) {
                await withTimeout(client.pupPage.evaluate('1'), 15000, 'Browser congelado');
            }
        } catch (e) {
            console.error('\n[Watchdog] ⚠️ Browser não respondeu. Forçando reinício para o systemd recuperar o serviço...');
            process.exit(1);
        }
    }, 60000);
});

client.on('message_create', async (msg) => {
    console.log(`[DEBUG] Msg: tipo=${msg.type}, fromMe=${msg.fromMe}, from=${msg.from}, to=${msg.to}, hasMedia=${msg.hasMedia}, body="${msg.body || ''}"`);
    const isFromMe = msg.fromMe === true;
    const isGroup = msg.to.includes('@g.us') || msg.from.includes('@g.us') || msg.to.includes('@newsletter');
    
    // Ignore system/bridge messages to prevent loops
    const body = msg.body || '';
    if (body.startsWith('🔒 Neo') || 
        body.startsWith('🔓 Neo') || 
        body.startsWith('🎙️ *Transcrição:*') || 
        body.startsWith('⚠️ *Erro') || 
        body.startsWith('❌ Comando') || 
        body.startsWith('⏰ *Tempo de resposta')) {
        console.log(`[Bridge] Ignorando mensagem do sistema/bridge para evitar loops: "${body}"`);
        return;
    }
    
    // Self-Chat filter: verifica dinamicamente se o contato do chat é o próprio usuário, e usa fallback para IDs conhecidos pois o isMe pode falhar em LIDs
    let isSelfChat = false;
    if (isFromMe && !isGroup) {
        // Tenta pela API (pode não funcionar para LIDs devido à forma como o whatsapp-web.js compara internamente)
        try {
            const contact = await client.getContactById(msg.to);
            isSelfChat = (contact && contact.isMe === true);
        } catch (e) {
            console.error('[Bridge DEBUG] Erro ao obter contato:', e.message);
        }
        
        // Se a API falhou em identificar (comum com LIDs), tenta os fallbacks de forma garantida
        if (!isSelfChat) {
            isSelfChat = msg.to === client.info.wid._serialized || 
                         msg.to.includes('16174981058753') || 
                         msg.to.includes('228191662801065');
        }
    }

    if (isFromMe && isSelfChat && !isGroup) {
        if ((msg.type === 'voice' || msg.type === 'audio' || msg.type === 'ptt') && msg.hasMedia) {
             console.log('[Bridge]: Mensagem de áudio recebida! Baixando mídia...');
             try {
                 // Limita o tempo de download a 30s para evitar travamento do Puppeteer
                 const media = await withTimeout(msg.downloadMedia(), 30000, 'Tempo limite esgotado ao baixar o áudio do WhatsApp.');
                 if (media && media.data) {
                     console.log('[Bridge]: Transcrevendo áudio com o Gemini...');
                     const transcription = await transcribeAudio(media.data, media.mimetype);
                     console.log(`[Bridge]: Áudio transcrito: "${transcription}"`);

                     // Envia a confirmação de transcrição gráfica no chat do WhatsApp
                     await sendBridgeMessage(msg.to, `🎙️ *Transcrição:* "${transcription}"`);

                     // Prossegue enviando a transcrição ao agente
                     await forwardToAgent(transcription, msg.to);
                 } else {
                     console.error('[Bridge]: Falha ao obter dados do áudio (media ou media.data está nulo/indefinido)');
                     await sendBridgeMessage(msg.to, '⚠️ *Erro ao processar áudio:* Não foi possível baixar o arquivo de mídia.');
                 }
             } catch (mediaErr) {
                 console.error('[Erro de áudio]:', mediaErr.message);
                 await sendBridgeMessage(msg.to, `⚠️ *Erro ao processar áudio:* ${mediaErr.message}`);
             }
        } else if (msg.body && msg.body !== lastAgentMessage) {
            console.log(`\n[Bridge] Mensagem recebida no chat privado: ${msg.body}`);
            
            const msgLower = msg.body.trim().toLowerCase();

            // Lock System
            if (isLocked) {
                if (msgLower === 'neo?') {
                    await sendBridgeMessage(msg.to, '🔒 Neo inativo. Informe a senha de acesso:');
                    return;
                }
                
                if (msg.body.trim() === process.env.NEO_PASSWORD) {
                    isLocked = false;
                    await sendBridgeMessage(msg.to, '🔓 Neo destravado! Pronto para os comandos.');
                    return;
                }
                // Do not respond to anything else while locked
                return;
            }

            if (msgLower === 'dormir' || msgLower === 'lock') {
                isLocked = true;
                await sendBridgeMessage(msg.to, '🔒 Neo voltou a dormir. Até a próxima!');
                return;
            }
            
            // 1. Intercept if there's a pending permission request
            if (pendingAsk) {
                if (/^sim$|^yes$|^ok$|^s$/i.test(msgLower)) {
                    console.log("[Bridge] User approved command!");
                    clearTimeout(pendingAsk.timer);
                    pendingAsk.resolve(true);
                    lastAgentMessage = msg.body; // Prevent forwarding "sim" to the agent
                    return;
                } else if (/^n(ão|ao)$|^no$|^n$/i.test(msgLower)) {
                    console.log("[Bridge] User denied command.");
                    clearTimeout(pendingAsk.timer);
                    pendingAsk.resolve(false);
                    lastAgentMessage = msg.body; // Prevent forwarding "não" to the agent
                    await sendBridgeMessage(msg.to, "❌ Comando cancelado.");
                    return;
                }
            }
            
            // 2. Forward to Python agent
            try {
                await forwardToAgent(msg.body, msg.to);
            } catch (err) {
                console.error('[Bridge] Error in forwardToAgent:', err);
                await sendBridgeMessage(msg.to, `⚠️ *Erro de comunicação com o Agente:* ${err.message}`);
            }
        }
    }
});

async function transcribeAudio(base64Data, mimeType) {
    // Remove parâmetros do MIME type (ex: "; codecs=opus") que causam INVALID_ARGUMENT no Gemini
    const cleanMimeType = mimeType.split(';')[0].trim();
    console.log(`[Bridge]: Chamando Gemini API com MIME type: "${cleanMimeType}"`);

    const response = await genAI.models.generateContent({
        model: 'gemini-2.0-flash',
        contents: [
            {
                role: 'user',
                parts: [
                    {
                        inlineData: {
                            data: base64Data,
                            mimeType: cleanMimeType
                        }
                    },
                    {
                        text: "Por favor, transcreva o áudio desta mensagem em português e retorne APENAS o texto da transcrição literal de forma limpa, sem comentários ou explicações."
                    }
                ]
            }
        ]
    });

    if (
        !response.candidates ||
        !response.candidates[0] ||
        !response.candidates[0].content ||
        !response.candidates[0].content.parts ||
        !response.candidates[0].content.parts[0]
    ) {
        throw new Error('Não foi possível obter a transcrição do Gemini (resposta vazia ou bloqueada).');
    }

    return response.candidates[0].content.parts[0].text.trim();
}

async function forwardToAgent(text, chatId) {
    const postData = JSON.stringify({ message: text });
    
    const options = {
        hostname: process.env.BACKEND_HOST || '127.0.0.1',
        port: 5000,
        path: '/chat',
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'Content-Length': Buffer.byteLength(postData),
            'X-Neo-Token': process.env.INTERNAL_API_KEY
        },
        timeout: 600000 // 10 minutes timeout
    };
    
    const req = http.request(options, (res) => {
        let body = '';
        res.on('data', chunk => body += chunk);
        res.on('end', async () => {
            try {
                if (res.statusCode === 200) {
                    const data = JSON.parse(body);
                    const agentResponse = data.response;
                    lastAgentMessage = agentResponse;
                    await sendBridgeMessage(chatId, agentResponse);
                } else {
                    const errDetail = body || `Status Code ${res.statusCode}`;
                    throw new Error(errDetail);
                }
            } catch (e) {
                console.error('[Bridge] Error processing agent response:', e);
                await sendBridgeMessage(chatId, `⚠️ *Erro no Neo:* ${e.message}`);
            }
        });
    });
    
    req.on('error', async (e) => {
        console.error('[Bridge] Connection error:', e);
        await sendBridgeMessage(chatId, `⚠️ *Erro de conexão com o agente:* ${e.message}`);
    });
    
    req.write(postData);
    req.end();
}

// Start HTTP Bridge Server
const server = http.createServer((req, res) => {
    if (req.method === 'POST' && req.url === '/ask') {
        const token = req.headers['x-neo-token'];
        if (token !== process.env.INTERNAL_API_KEY) {
            res.writeHead(401, { 'Content-Type': 'application/json' });
            return res.end(JSON.stringify({ error: 'Unauthorized' }));
        }

        let body = '';
        req.on('data', chunk => body += chunk);
        req.on('end', async () => {
            try {
                const { command } = JSON.parse(body);
                console.log(`[Bridge] Requesting approval for command: ${command}`);
                
                // Cancel existing pending ask if any
                if (pendingAsk) {
                    clearTimeout(pendingAsk.timer);
                    pendingAsk.resolve(false);
                    pendingAsk = null;
                }
                
                const askMsg = `⚠️ *Neo solicita permissão para rodar o comando:*\n\`\`\`${command}\`\`\`\n\nResponda com *sim* ou *não*.`;
                const selfChatId = client.info.wid._serialized;
                await sendBridgeMessage(selfChatId, askMsg);
                
                const approved = await new Promise((resolve) => {
                    const timer = setTimeout(() => {
                        sendBridgeMessage(selfChatId, "⏰ *Tempo de resposta esgotado.* Comando cancelado.");
                        resolve(false);
                    }, 10 * 60 * 1000); // 10 minutes timeout
                    
                    pendingAsk = { resolve, timer, command };
                });
                
                pendingAsk = null;
                res.writeHead(200, { 'Content-Type': 'application/json' });
                res.end(JSON.stringify({ approved }));
            } catch (err) {
                console.error('[Bridge] Error in /ask endpoint:', err);
                res.writeHead(500, { 'Content-Type': 'application/json' });
                res.end(JSON.stringify({ error: err.message }));
            }
        });
    } else if (req.method === 'GET' && req.url === '/status') {
        const token = req.headers['x-neo-token'];
        if (token !== process.env.INTERNAL_API_KEY) {
            res.writeHead(401, { 'Content-Type': 'application/json' });
            return res.end(JSON.stringify({ error: 'Unauthorized' }));
        }

        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ connected: isConnected, qr: currentQR }));
    } else {
        res.writeHead(404);
        res.end();
    }
});

server.listen(3303, () => {
    console.log('[✓] Servidor da Bridge rodando na porta 3303');
});

// Handle shutdown signals cleanly
const shutdown = async (signal) => {
    console.log(`[Bridge] Recebido sinal ${signal}. Fechando cliente do WhatsApp e encerrando...`);
    try {
        await client.destroy();
        console.log('[Bridge] Cliente do WhatsApp fechado com sucesso.');
    } catch (e) {
        console.error('[Bridge] Erro ao fechar cliente do WhatsApp:', e.message);
    }
    process.exit(0);
};

process.on('SIGTERM', () => shutdown('SIGTERM'));
process.on('SIGINT', () => shutdown('SIGINT'));

client.initialize();
