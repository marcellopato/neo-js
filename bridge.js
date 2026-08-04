require('dotenv').config();
const { Client, LocalAuth, MessageMedia } = require('whatsapp-web.js');
const qrcode = require('qrcode-terminal');
const http = require('http');
const fs = require('fs');
const { GoogleGenAI } = require('@google/genai');

const genAI = new GoogleGenAI({ apiKey: process.env.GEMINI_API_KEY });

let lastAgentMessage = "";
let pendingAsk = null; // { resolve, timer, command }
let isLocked = false; // Bot starts unlocked (self-chat, senha removida)
let currentQR = null;
let isConnected = false;

const TEMP_DIR = '/tmp/neo-bridge-audio'; // Temp dir for audio files
if (!fs.existsSync(TEMP_DIR)) fs.mkdirSync(TEMP_DIR, { recursive: true });

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
    webVersionCache: {
        type: 'remote',
        remotePath: 'https://raw.githubusercontent.com/wppconnect-team/wa-version/main/html/2.3000.1042542308-alpha.html',
    },
    puppeteer: { 
        executablePath: process.env.PUPPETEER_EXECUTABLE_PATH || undefined,
        args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage'],
        headless: true
    }
});

async function sendBridgeMessage(chatId, text) {
    // Guard: if WhatsApp client isn't ready yet, log warning and skip
    if (!client.info || !client.info.wid || !client.info.wid._serialized) {
        console.error(`[Bridge] Cannot send message: WhatsApp client not ready yet (chatId=${chatId})`);
        throw new Error('WhatsApp client not initialized');
    }
    const isSelfChat = chatId === client.info.wid._serialized || 
                       chatId.includes('16174981058753') || 
                       chatId.includes('228191662801065');
    if (isSelfChat) {
        lastAgentMessage = text;
    }
    return await client.sendMessage(chatId, text);
}

async function sendReaction(msg, emoji) {
    try {
        if (msg && typeof msg.react === 'function') {
            await msg.react(emoji);
        }
    } catch (e) {
        console.log(`[Bridge] Reaction ${emoji} not supported (non-critical): ${e.message}`);
    }
}

client.on('qr', qr => {
    qrcode.generate(qr, { small: true });
    currentQR = qr;
});

client.on('auth_failure', async msg => {
    console.error('\n[Bridge] FALHA NA AUTENTICAÇÃO:', msg);
    await triggerNeoAutoUpdate('Falha na autenticação (auth_failure)');
});

client.on('disconnected', async (reason) => {
    console.log('\n[Bridge] Cliente desconectado:', reason);
    await triggerNeoAutoUpdate(`Cliente desconectado (reason: ${reason})`);
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
            console.error('\n[Watchdog] ⚠️ Browser não respondeu. Acionando Auto-Healing...');
            await triggerNeoAutoUpdate('Browser congelado / watchdog timeout');
            try { await client.destroy(); } catch(err) {}
            setTimeout(() => process.exit(1), 10000);
        }
    }, 60000);
});

async function triggerNeoAutoUpdate(reason) {
    const prompt = `[ALERTA DO SISTEMA] A bridge do WhatsApp falhou ao iniciar ou se desconectou de forma anormal. Motivo: ${reason}. Isso geralmente acontece quando o WhatsApp Web atualiza e a biblioteca fica desatualizada. Por favor, execute o comando 'npm install github:pedroslopez/whatsapp-web.js#main' para atualizar a biblioteca e, em seguida, reinicie o sistema usando './start.sh'.`;
    console.log(`\n[Auto-Healing] Enviando solicitação de reparo para o Neo. Motivo: ${reason}`);
    await forwardToAgent(prompt, "system");
}

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
        body.startsWith('⏰ *Tempo de resposta') ||
        body.startsWith('💻') ||
        body.startsWith('⏳')) {
        console.log(`[Bridge] Ignorando mensagem do sistema/bridge para evitar loops: "${body}"`);
        return;
    }
    
    // Self-Chat filter: verifica dinamicamente se o contato do chat é o próprio usuário
    let isSelfChat = false;
    if (isFromMe && !isGroup) {
        try {
            const contact = await client.getContactById(msg.to);
            isSelfChat = (contact && contact.isMe === true);
        } catch (e) {
            console.error('[Bridge DEBUG] Erro ao obter contato:', e.message);
        }
        
        if (!isSelfChat) {
            isSelfChat = msg.to === client.info.wid._serialized || 
                         msg.to.includes('16174981058753') || 
                         msg.to.includes('228191662801065');
        }
    }

    if (isFromMe && isSelfChat && !isGroup) {
        if ((msg.type === 'voice' || msg.type === 'audio' || msg.type === 'ptt') && msg.hasMedia) {
             console.log('[Bridge]: Mensagem de áudio recebida! Baixando mídia...');
             await sendReaction(msg, '⏳');
             let audioMedia = null;
             try {
                 audioMedia = await withTimeout(msg.downloadMedia(), 30000, 'Tempo limite esgotado ao baixar o áudio do WhatsApp.');
                 if (audioMedia && audioMedia.data) {
                     console.log('[Bridge]: Enviando áudio para o backend Python processar...');
                     const transcription = await transcribeAudioViaBackend(audioMedia, msg.to);
                     if (transcription) {
                         console.log(`[Bridge]: Áudio transcrito: "${transcription.substring(0, 100)}..."`);
                         await sendBridgeMessage(msg.to, `🎙️ *Transcrição:* "${transcription}"`);
                         await forwardToAgent(transcription, msg.to);
                         await sendReaction(msg, '✅');
                         return;
                     } else {
                         throw new Error('Transcrição retornou vazia');
                     }
                 } else {
                     throw new Error('Falha ao baixar mídia do áudio');
                 }
             } catch (mediaErr) {
                 console.error('[Erro de áudio]:', mediaErr);
                 await sendReaction(msg, '❌');
                 // Fallback: tentar com o JS SDK direto (reuse audioMedia if downloaded)
                 try {
                     console.log('[Bridge] Tentando fallback JS SDK...');
                     const fbMedia = audioMedia && audioMedia.data ? audioMedia : await msg.downloadMedia();
                     if (fbMedia && fbMedia.data) {
                         const transcription = await transcribeAudio(fbMedia.data, fbMedia.mimetype);
                         if (transcription) {
                             await sendBridgeMessage(msg.to, `🎙️ *Transcrição:* "${transcription}"`);
                             await forwardToAgent(transcription, msg.to);
                             await sendReaction(msg, '✅');
                             return;
                         }
                     }
                 } catch (fallbackErr) {
                     console.error('[Bridge] Fallback JS SDK também falhou:', fallbackErr);
                 }
                 await sendBridgeMessage(msg.to, `⚠️ *Erro ao processar áudio:* Não foi possível transcrever. Tente enviar texto. (${mediaErr.message || 'erro'})`);
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
                    pendingAsk = null;
                    lastAgentMessage = msg.body;
                    return;
                } else if (/^n(ão|ao)$|^no$|^n$/i.test(msgLower)) {
                    console.log("[Bridge] User denied command.");
                    clearTimeout(pendingAsk.timer);
                    pendingAsk.resolve(false);
                    pendingAsk = null;
                    lastAgentMessage = msg.body;
                    await sendBridgeMessage(msg.to, "❌ Comando cancelado.");
                    return;
                }
            }
            
            // 2. Forward to Python agent (try streaming first, fallback to sync)
            try {
                await forwardToAgentStream(msg, msg.body, msg.to);
            } catch (err) {
                console.error('[Bridge] Stream error, falling back to sync:', err.message);
                try {
                    await forwardToAgent(msg.body, msg.to);
                } catch (fallbackErr) {
                    console.error('[Bridge] Sync fallback also failed:', fallbackErr);
                    await sendBridgeMessage(msg.to, `⚠️ *Erro de comunicação:* ${fallbackErr.message}`);
                }
            }
        }
    }
});

// ── Streaming helper ─────────────────────────────────────────────────────────
async function forwardToAgentStream(userMsg, text, chatId) {
    const postData = JSON.stringify({ message: text });

    return new Promise((resolve, reject) => {
        const options = {
            hostname: process.env.BACKEND_HOST || '127.0.0.1',
            port: 5000,
            path: '/chat/stream',
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Content-Length': Buffer.byteLength(postData),
                'X-Neo-Token': process.env.INTERNAL_API_KEY
            },
            timeout: 600000 // 10 minutes
        };

        const req = http.request(options, (res) => {
            if (res.statusCode !== 200) {
                let errBody = '';
                res.on('data', chunk => errBody += chunk);
                res.on('end', () => reject(new Error(errBody || `HTTP ${res.statusCode}`)));
                return;
            }

            let accumulated = '';
            let statusMsg = null;
            let processedChars = 0;
            let streamFinished = false;
            const CHUNK_INTERVAL = 120;

            // Send immediate reaction
            sendReaction(userMsg, '⏳');

            res.on('data', async (chunk) => {
                const text = chunk.toString();
                const lines = text.split('\n');
                
                for (const line of lines) {
                    if (!line.startsWith('data: ')) continue;
                    
                    try {
                        const data = JSON.parse(line.slice(6));
                        
                        if (data.status === 'thinking') {
                            sendReaction(userMsg, '💭');
                            
                        } else if (data.status === 'executing') {
                            sendReaction(userMsg, '⚡');
                            const detail = data.detail || '';
                            // Send a brief status update (avoid duplicates for same command)
                            if (detail && detail !== statusMsg) {
                                statusMsg = detail;
                                const cmdShort = detail.length > 60 ? detail.substring(0, 57) + '...' : detail;
                                await sendBridgeMessage(chatId, `💻 ${cmdShort}`);
                            }
                            
                        } else if (data.chunk) {
                            accumulated += data.chunk;
                            processedChars += data.chunk.length;
                            // Send intermediate update every CHUNK_INTERVAL chars
                            if (processedChars >= CHUNK_INTERVAL) {
                                processedChars = 0;
                                // Don't send every chunk — just update reaction to show progress
                                sendReaction(userMsg, '✍️');
                            }
                            
                        } else if (data.error) {
                            accumulated += `\n\n⚠️ ${data.error}`;
                            
                        } else if (data.done) {
                            // Stream complete — send final response
                            streamFinished = true;
                            if (accumulated) {
                                lastAgentMessage = accumulated;
                                await sendBridgeMessage(chatId, accumulated);
                                await sendReaction(userMsg, '✅');
                            }
                            resolve();
                        }
                    } catch (e) {
                        // Skip malformed JSON lines
                    }
                }
            });

            res.on('end', async () => {
                // If stream didn't finish via 'done' event but we have text
                if (!streamFinished && accumulated && lastAgentMessage !== accumulated) {
                    lastAgentMessage = accumulated;
                    await sendBridgeMessage(chatId, accumulated);
                    await sendReaction(userMsg, '✅');
                }
                resolve();
            });

            res.on('error', (e) => {
                reject(new Error(`Stream error: ${e.message}`));
            });
        });

        req.on('error', (e) => reject(new Error(`Connection error: ${e.message}`)));
        req.on('timeout', () => { req.destroy(); reject(new Error('Request timeout')); });
        
        req.write(postData);
        req.end();
    });
}

async function transcribeAudio(base64Data, mimeType) {
    const cleanMimeType = mimeType.split(';')[0].trim();
    console.log(`[Bridge]: Chamando Gemini API com MIME type: "${cleanMimeType}"`);

    try {
        const response = await genAI.models.generateContent({
            model: 'gemini-2.5-flash',
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
            !response ||
            !response.candidates ||
            !response.candidates[0] ||
            !response.candidates[0].content ||
            !response.candidates[0].content.parts ||
            !response.candidates[0].content.parts[0]
        ) {
            console.error('[Bridge/Transcribe] Resposta inválida do Gemini:', {
                hasCandidates: !!response?.candidates,
                candidatesCount: response?.candidates?.length,
                finishReason: response?.candidates?.[0]?.finishReason,
                promptFeedback: response?.promptFeedback,
            });
            throw new Error('Resposta vazia ou bloqueada do Gemini');
        }

        const text = response.candidates[0].content.parts[0].text || '';
        return text.trim();
    } catch (transcribeErr) {
        // Log completo SEM truncamento
        console.error('=== [Bridge/Transcribe] ERRO DETALHADO ===');
        console.error('Name:', transcribeErr.name);
        console.error('Message:', transcribeErr.message);
        console.error('Status:', transcribeErr.status);
        console.error('Code:', transcribeErr.code);
        console.error('MIME type:', cleanMimeType);
        console.error('Audio data length:', base64Data?.length);
        console.error('Stack trace:');
        console.error(transcribeErr.stack || '(sem stack)');
        console.error('=== FIM DO ERRO ===');
        throw transcribeErr; // Re-throw for the outer handler
    }
}

// ── Audio transcription via Python backend ──────────────────────────────────
async function transcribeAudioViaBackend(media, chatId) {
    if (!media || !media.data) throw new Error('Media data is empty');

    const postData = JSON.stringify({
        data: media.data,
        mimeType: media.mimetype || 'audio/ogg',
    });

    return new Promise((resolve, reject) => {
        const options = {
            hostname: process.env.BACKEND_HOST || '127.0.0.1',
            port: 5000,
            path: '/transcribe',
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Content-Length': Buffer.byteLength(postData),
                'X-Neo-Token': process.env.INTERNAL_API_KEY
            },
            timeout: 60000,
        };

        const req = http.request(options, (res) => {
            let body = '';
            res.on('data', chunk => body += chunk);
            res.on('end', () => {
                if (res.statusCode === 200) {
                    try {
                        const data = JSON.parse(body);
                        resolve(data.transcription || data.text || '');
                    } catch (e) {
                        reject(new Error('Invalid JSON response: ' + body.substring(0, 100)));
                    }
                } else {
                    reject(new Error(`HTTP ${res.statusCode}: ${body.substring(0, 200)}`));
                }
            });
        });

        req.on('error', (e) => reject(new Error(`Connection error: ${e.message}`)));
        req.on('timeout', () => { req.destroy(); reject(new Error('Request timeout')); });
        req.write(postData);
        req.end();
    });
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
                    const audioFile = data.audio_file;
                    lastAgentMessage = agentResponse;
                    if (chatId === "system") {
                        console.log(`\n[Neo Auto-Healing Response]: ${agentResponse}`);
                    } else {
                        await sendBridgeMessage(chatId, agentResponse);
                        
                        if (audioFile && fs.existsSync(audioFile)) {
                            console.log(`[Bridge] Enviando áudio gerado: ${audioFile}`);
                            try {
                                const media = MessageMedia.fromFilePath(audioFile);
                                await client.sendMessage(chatId, media, { sendAudioAsVoice: true });
                            } catch (err) {
                                console.error('[Bridge] Erro ao enviar áudio:', err.message);
                            }
                        }
                    }
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
                
                if (pendingAsk) {
                    clearTimeout(pendingAsk.timer);
                    pendingAsk.resolve(false);
                    pendingAsk = null;
                }
                
                if (!client.info || !client.info.wid || !client.info.wid._serialized) {
                    res.writeHead(503, { 'Content-Type': 'application/json' });
                    return res.end(JSON.stringify({ error: 'WhatsApp client not initialized' }));
                }
                const selfChatId = client.info.wid._serialized;
                const askMsg = `⚠️ *Neo solicita permissão para rodar o comando:*\n\`\`\`${command}\`\`\`\n\nResponda com *sim* ou *não*.`;
                await sendBridgeMessage(selfChatId, askMsg);
                
                const approved = await new Promise((resolve) => {
                    const timer = setTimeout(() => {
                        sendBridgeMessage(selfChatId, "⏰ *Tempo de resposta esgotado.* Comando cancelado.");
                        resolve(false);
                    }, 2 * 60 * 1000);
                    
                    pendingAsk = { resolve, timer, command };

                    // Send a reminder after 1 minute
                    setTimeout(async () => {
                        if (pendingAsk && pendingAsk.timer === timer) {
                            await sendBridgeMessage(selfChatId, "⏳ Ainda esperando sua resposta... *sim* ou *não*?");
                        }
                    }, 60 * 1000);
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

client.initialize().catch(async err => {
    console.error('\n[Bridge] Erro fatal na inicialização:', err);
    const errMsg = err?.message || err || '';
    if (typeof errMsg === 'string' && (errMsg.includes('timeout') || errMsg.includes('browser') || errMsg.includes('Evaluation failed'))) {
         await triggerNeoAutoUpdate(errMsg);
    }
});
