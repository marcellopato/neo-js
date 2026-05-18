require('dotenv').config();
const { Client, LocalAuth } = require('whatsapp-web.js');
const qrcode = require('qrcode-terminal');
const { GoogleGenAI } = require('@google/genai');
const { exec } = require('child_process');

const genAI = new GoogleGenAI({ apiKey: process.env.GEMINI_API_KEY });

const client = new Client({
    authStrategy: new LocalAuth(),
    puppeteer: { 
        args: ['--no-sandbox', '--disable-setuid-sandbox'],
        headless: true
    }
});

client.on('qr', qr => qrcode.generate(qr, { small: true }));

client.on('ready', () => {
    console.log('\n[✓] MODO DEBUG ATIVO');
    console.log('ID Logado (myId):', client.info.wid._serialized);
    console.log('--------------------------------------------');
});

client.on('message_create', async (msg) => {
    // LOG DE ABSOLUTAMENTE TUDO QUE VOCÊ ENVIA
    if (msg.fromMe) {
        console.log(`\n[LOG] Você enviou uma mensagem!`);
        console.log(`      Para (msg.to): ${msg.to}`);
        console.log(`      Corpo: ${msg.body}`);
        
        const myId = client.info.wid._serialized;
        if (msg.to === myId) {
            console.log(`      >>> ESTE É O SELF-CHAT (MATCH PERFEITO)!`);
        } else {
            console.log(`      >>> Esta mensagem foi para outra pessoa. Ignorando.`);
        }
    }
});

client.initialize();
