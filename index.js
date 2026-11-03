const { Client, GatewayIntentBits, EmbedBuilder } = require('discord.js');
const Database = require('better-sqlite3');
const cron = require('node-cron');
const express = require('express');
require('dotenv').config();

// Initialize Express server for 24/7 uptime on Railway
const app = express();
const PORT = process.env.PORT || 3000;
app.get('/', (req, res) => res.send('Minecraft Lifesteal Lottery Bot is running!'));
app.listen(PORT, () => console.log(`Web server listening on port ${PORT}`));

// Initialize SQLite Database
const db = new Database('lottery.db');
db.prepare(`
  CREATE TABLE IF NOT EXISTS entries (
    userId TEXT PRIMARY KEY,
    username TEXT
  )
`).run();

// Initialize Discord Client
const client = new Client({
    intents: [
        GatewayIntentBits.Guilds,
        GatewayIntentBits.GuildMessages,
        GatewayIntentBits.MessageContent
    ]
});

client.once('ready', () => {
    console.log(`Logged in as ${client.user.tag}!`);
});

// Basic command listener
client.on('messageCreate', async message => {
    if (message.author.bot) return;

    // Type "!lottery" to enter the draw
    if (message.content === '!lottery') {
        const userId = message.author.id;
        const username = message.author.username;

        try {
            const stmt = db.prepare('INSERT OR IGNORE INTO entries (userId, username) VALUES (?, ?)');
            const info = stmt.run(userId, username);

            if (info.changes > 0) {
                message.reply('🎉 You have successfully entered the Lifesteal lottery!');
            } else {
                message.reply('⚠️ You are already entered in this lottery draw.');
            }
        } catch (error) {
            console.error(error);
            message.reply('❌ An error occurred while entering the lottery.');
        }
    }

    // Type "!entries" to check total participants
    if (message.content === '!entries') {
        const count = db.prepare('SELECT COUNT(*) as total FROM entries').get().total;
        message.reply(`🎟️ Total players entered in the lottery: **${count}**`);
    }
});

// Log in using your Discord Bot Token from environment variables
client.login(process.env.DISCORD_TOKEN);
