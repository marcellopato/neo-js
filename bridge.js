require('dotenv').config();
const { Client, LocalAuth } = require('whatsapp-web.js');
const qrcode = require('qrcode-terminal');
const http = require('http');

let lastAgentMessage = "";
let pendingAsk = null; // { resolve, timer, command }

// Start WhatsApp Client
const client = new Client({
    authStrategy: new LocalAuth(),
    puppeteer: { 
        args: ['--no-sandbox', '--disable-setuid-sandbox'],
        headless: true
    }
});

client.on('qr', qr => qrcode.generate(qr, { small: true }));

client.on('ready', () => {
    console.log('\n[✓] Bridge do WhatsApp está ONLINE!');
    console.log('ID Logado:', client.info.wid._serialized);
});

client.on('message_create', async (msg) => {
    const isFromMe = msg.fromMe === true;
    const isGroup = msg.to.includes('@g.us') || msg.from.includes('@g.us') || msg.to.includes('@newsletter');
    
    // Self-Chat filter
    const isSelfChat = msg.to === '16174981058753@lid' || msg.to === client.info.wid._serialized;

    if (isFromMe && isSelfChat && !isGroup && msg.body !== lastAgentMessage) {
        console.log(`\n[Bridge] Mensagem recebida no chat privado: ${msg.body}`);
        
        // 1. Intercept if there's a pending permission request
        if (pendingAsk) {
            const reply = msg.body.trim().toLowerCase();
            if (reply === 'sim' || reply === 'yes' || reply === 'ok' || reply === 's') {
                console.log("[Bridge] User approved command!");
                clearTimeout(pendingAsk.timer);
                pendingAsk.resolve(true);
                lastAgentMessage = msg.body; // Prevent forwarding "sim" to the agent
                return;
            } else if (reply === 'não' || reply === 'no' || reply === 'nao' || reply === 'n') {
                console.log("[Bridge] User denied command.");
                clearTimeout(pendingAsk.timer);
                pendingAsk.resolve(false);
                lastAgentMessage = msg.body; // Prevent forwarding "não" to the agent
                await client.sendMessage(msg.to, "❌ Comando cancelado.");
                return;
            }
        }
        
        // 2. Forward to Python agent
        try {
            await forwardToAgent(msg.body, msg.to);
        } catch (err) {
            console.error('[Bridge] Error in forwardToAgent:', err);
            await client.sendMessage(msg.to, `⚠️ *Erro de comunicação com o Agente:* ${err.message}`);
        }
    }
});

async function forwardToAgent(text, chatId) {
    const postData = JSON.stringify({ message: text });
    
    const options = {
        hostname: '127.0.0.1',
        port: 5000,
        path: '/chat',
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'Content-Length': Buffer.byteLength(postData)
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
                    await client.sendMessage(chatId, agentResponse);
                } else {
                    const errDetail = body || `Status Code ${res.statusCode}`;
                    throw new Error(errDetail);
                }
            } catch (e) {
                console.error('[Bridge] Error processing agent response:', e);
                await client.sendMessage(chatId, `⚠️ *Erro no Neo:* ${e.message}`);
            }
        });
    });
    
    req.on('error', async (e) => {
        console.error('[Bridge] Connection error:', e);
        await client.sendMessage(chatId, `⚠️ *Erro de conexão com o agente:* ${e.message}`);
    });
    
    req.write(postData);
    req.end();
}

// Start HTTP Bridge Server
const server = http.createServer((req, res) => {
    if (req.method === 'POST' && req.url === '/ask') {
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
                await client.sendMessage(selfChatId, askMsg);
                
                const approved = await new Promise((resolve) => {
                    const timer = setTimeout(() => {
                        client.sendMessage(selfChatId, "⏰ *Tempo de resposta esgotado.* Comando cancelado.");
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
    } else {
        res.writeHead(404);
        res.end();
    }
});

server.listen(3303, () => {
    console.log('[✓] Servidor da Bridge rodando na porta 3303');
});

client.initialize();
