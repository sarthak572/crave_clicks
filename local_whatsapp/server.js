const fs = require('fs');
const { Client, LocalAuth } = require('whatsapp-web.js');
const qrcode = require('qrcode-terminal');
const express = require('express');
const bodyParser = require('body-parser');

const app = express();
app.use(bodyParser.json());

// A single hardcoded Chrome path only works on the machine it was written on.
// Check the common install locations for Chrome or Edge (both Chromium-based
// and supported by puppeteer) so this also works on a client's PC. Chrome or
// Edge must be installed - puppeteer's own bundled browser is not downloaded
// as part of this project, to keep it small.
function findBrowserExecutable() {
    const candidates = [
        `${process.env['PROGRAMFILES']}\\Google\\Chrome\\Application\\chrome.exe`,
        `${process.env['PROGRAMFILES(X86)']}\\Google\\Chrome\\Application\\chrome.exe`,
        `${process.env['LOCALAPPDATA']}\\Google\\Chrome\\Application\\chrome.exe`,
        `${process.env['PROGRAMFILES(X86)']}\\Microsoft\\Edge\\Application\\msedge.exe`,
        `${process.env['PROGRAMFILES']}\\Microsoft\\Edge\\Application\\msedge.exe`,
    ];
    for (const candidate of candidates) {
        try {
            if (candidate && fs.existsSync(candidate)) return candidate;
        } catch (e) {
            // Ignore and try the next candidate.
        }
    }
    return null;
}

const browserExecutable = findBrowserExecutable();
if (!browserExecutable) {
    console.error(
        'Could not find Chrome or Edge installed on this PC. ' +
        'Install Google Chrome or Microsoft Edge, then start the WhatsApp server again.'
    );
    process.exit(1);
}

const client = new Client({
    authStrategy: new LocalAuth(),
    puppeteer: { executablePath: browserExecutable },
});

let events = [];
let eventIdCounter = Date.now();

let currentQrImage = null;
let isReady = false;

const QRCode = require('qrcode');

client.on('qr', async (qr) => {
    qrcode.generate(qr, { small: true });
    console.log('Scan the QR code above with WhatsApp to log in.');
    try {
        currentQrImage = await QRCode.toDataURL(qr);
    } catch (err) {
        console.error("QR Code generation failed", err);
    }
});

client.on('ready', () => {
    isReady = true;
    currentQrImage = null;
    console.log('Client is ready!');
});

app.get('/pos/status', (req, res) => {
    res.json({ ready: isReady, qr: currentQrImage });
});

// The Express server starts accepting requests right away, but Chrome/WhatsApp
// Web takes several seconds after client.initialize() to actually load and
// expose window.AuthStore. Calling requestPairingCode() before that finishes
// crashes inside whatsapp-web.js with a confusing "Cannot read properties of
// undefined (reading 'PairingCodeLinkUtils')" error. Wait for the page to
// really be ready first, so we can give a clear message instead.
async function waitForAuthStore(timeoutMs = 25000) {
    const start = Date.now();
    while (Date.now() - start < timeoutMs) {
        try {
            if (client.pupPage) {
                const ready = await client.pupPage.evaluate(
                    () => !!(window.AuthStore && window.AuthStore.PairingCodeLinkUtils)
                );
                if (ready) return true;
            }
        } catch (e) {
            // Page is still navigating/loading - keep waiting.
        }
        await new Promise((resolve) => setTimeout(resolve, 300));
    }
    return false;
}

app.post('/pos/request_pairing_code', async (req, res) => {
    const { phone } = req.body;
    if (!phone) {
        return res.status(400).json({ error: 'phone is required' });
    }
    try {
        const ready = await waitForAuthStore();
        if (!ready) {
            return res.status(503).json({
                error: 'WhatsApp is still starting up. Wait a few seconds and try again.',
            });
        }
        const code = await client.requestPairingCode(phone);
        res.json({ code: code });
    } catch (err) {
        console.error("Pairing code error", err);
        res.status(500).json({ error: err.toString() });
    }
});

client.on('message', async msg => {
    // Only record messages the customer sent to us. whatsapp-web.js also has
    // 'message_create', which fires for our own outgoing messages too (e.g. the
    // auto-ack and status updates the POS sends) - recording those here as
    // "incoming" created a feedback loop: every message we sent got treated as
    // a new customer order, which (with auto-ack on) triggered another message,
    // forever, burying real customer messages.
    // Only handle direct 1-to-1 chats. Without this, any message posted in a
    // WhatsApp group this number belongs to (staff group, supplier group,
    // family group, etc.) - or a broadcast/channel/status update - was being
    // recorded as a "new customer order" too, flooding Online Orders with
    // unrelated noise and burying real customer messages under it.
    const isDirectChat = msg.from && !/@(g\.us|broadcast|newsletter)$/.test(msg.from);

    if (msg.body && !msg.fromMe && isDirectChat) {
        try {
            let pushname = "Customer";
            try {
                const contact = await msg.getContact();
                pushname = contact ? (contact.pushname || contact.name || "Customer") : "Customer";
            } catch (e) {
                // Ignore
            }

            let safePhone = "unknown";
            if (msg.from) {
                safePhone = msg.from.split('@')[0].split(':')[0];
            }

            events.push({
                event_id: eventIdCounter++,
                message_id: (msg.id && msg.id._serialized) || Date.now().toString(),
                index: 0,
                from: safePhone,
                name: pushname,
                text: msg.body,
                items: null
            });
            if (events.length > 1000) {
                events.shift();
            }
        } catch (err) {
            console.error('Error processing message:', err.stack);
        }
    }
});

client.initialize();

app.get('/pos/events', (req, res) => {
    const after = parseInt(req.query.after || '0', 10);
    const newEvents = events.filter(e => e.event_id > after);
    const lastId = newEvents.length > 0 ? newEvents[newEvents.length - 1].event_id : after;
    res.json({ events: newEvents, last_id: lastId });
});

app.get('/debug', (req, res) => {
    res.json({ events: events, info: client.info });
});

app.post('/pos/send', async (req, res) => {
    const { phone, text } = req.body;
    if (!phone || !text) {
        return res.status(400).json({ error: 'phone and text are required' });
    }
    try {
        let chatId = phone.includes('@') ? phone : phone + '@c.us';
        
        // Strip any device IDs for a safe comparison
        let myBaseNumber = "";
        if (client.info && client.info.wid && client.info.wid.user) {
            myBaseNumber = client.info.wid.user.split(':')[0];
        }
        
        let targetBase = phone.split(':')[0].split('@')[0];

        // If they are messaging themselves, handle the specific WID
        if (myBaseNumber && targetBase === myBaseNumber) {
            chatId = client.info.wid._serialized;
        } else {
            // Otherwise try to safely resolve the registered number ID
            try {
                const registered = await client.getNumberId(phone);
                if (registered) {
                    chatId = registered._serialized;
                } else if (!phone.includes('@')) {
                    // Not a normal registered phone number. This can happen
                    // for a customer whose account hides their number: their
                    // incoming message arrives tagged with a WhatsApp "LID"
                    // instead of a phone number, and that's what we stored as
                    // their "phone". Try addressing the chat by that LID
                    // directly rather than giving up.
                    chatId = `${phone}@lid`;
                }
            } catch (e) {
                console.log("Could not resolve number ID for", phone);
            }
        }
        
        // WhatsApp's newer accounts use a private "LID" instead of the phone
        // number internally. The first time we message someone, WhatsApp Web's
        // local chat store has no entry for them yet, and sendMessage() can
        // fail with "No LID for user". Fetching the chat first makes WhatsApp
        // Web create that entry (and resolve the LID) before we try to send.
        try {
            await client.getChatById(chatId);
        } catch (e) {
            console.log("Could not pre-load chat for", chatId, e.toString());
        }

        await client.sendMessage(chatId, text);
        res.json({ success: true });
    } catch (error) {
        res.status(500).json({ error: error.toString() });
    }
});

const PORT = 3000;
app.listen(PORT, () => {
    console.log(`Local WhatsApp server listening on port ${PORT}`);
});
