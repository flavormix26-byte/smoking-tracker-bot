# 🔥 VERSI BARU - PAKAI APPLICATION - FILE: smoking_bot.py
import os
import sqlite3
import logging
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Database di /tmp agar jalan di Render
DB_PATH = "/tmp/absensi.db"

def init_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS sessions (
        user_id INTEGER,
        username TEXT,
        start_time TEXT,
        end_time TEXT
    )''')
    conn.commit()
    return conn

conn = init_db()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    username = user.username or f"user_{user_id}"
    now = datetime.now()

    c = conn.cursor()
    today = now.date().isoformat()
    c.execute("SELECT COUNT(*) FROM sessions WHERE user_id = ? AND date(start_time) = ?", (user_id, today))
    count = c.fetchone()[0]

    if count >= 3:
        await update.message.reply_text("❌ Maksimal 3x keluar/hari. Tidak bisa lagi.")
        return

    c.execute("SELECT 1 FROM sessions WHERE user_id = ? AND end_time IS NULL", (user_id,))
    if c.fetchone():
        await update.message.reply_text("⚠️ Masih dalam sesi sebelumnya. Kirim /end dulu!")
        return

    c.execute("INSERT INTO sessions (user_id, username, start_time) VALUES (?, ?, ?)",
              (user_id, username, now.isoformat()))
    conn.commit()

    deadline = now + timedelta(minutes=15)
    await update.message.reply_text(
        f"✅ Keluar #{count+1} jam {now.strftime('%H:%M')}\n"
        f"⏳ Kembali sebelum {deadline.strftime('%H:%M')}!"
    )

async def end(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    now = datetime.now()
    c = conn.cursor()

    c.execute("SELECT start_time FROM sessions WHERE user_id = ? AND end_time IS NULL", (user_id,))
    row = c.fetchone()
    if not row:
        await update.message.reply_text("⚠️ Tidak ada sesi aktif. Gunakan /start dulu.")
        return

    start_time = datetime.fromisoformat(row[0])
    minutes = int((now - start_time).total_seconds() // 60)

    c.execute("UPDATE sessions SET end_time = ? WHERE user_id = ? AND end_time IS NULL",
              (now.isoformat(), user_id))
    conn.commit()

    msg = f"⚠️ Melebihi batas! ({minutes} menit)" if minutes > 15 else f"✅ Durasi: {minutes} menit"
    await update.message.reply_text(msg)

async def riwayat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    today = datetime.now().date().isoformat()
    c = conn.cursor()
    c.execute("""
        SELECT start_time, end_time FROM sessions 
        WHERE user_id = ? AND date(start_time) = ? 
        ORDER BY start_time
    """, (user_id, today))
    rows = c.fetchall()

    if not rows:
        await update.message.reply_text("📋 Belum ada riwayat hari ini.")
        return

    text = "📋 Riwayat hari ini:\n"
    for i, (start, end) in enumerate(rows, 1):
        s = datetime.fromisoformat(start).strftime('%H:%M')
        if end:
            e = datetime.fromisoformat(end).strftime('%H:%M')
            dur = int((datetime.fromisoformat(end) - datetime.fromisoformat(start)).total_seconds() // 60)
            text += f"{i}. {s}–{e} ({dur} mnt)\n"
        else:
            text += f"{i}. {s}–MASIH DI LUAR! ⚠️\n"
    await update.message.reply_text(text)

def main():
    TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    if not TOKEN:
        logger.error("❌ TELEGRAM_BOT_TOKEN tidak ditemukan!")
        return

    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("end", end))
    app.add_handler(CommandHandler("riwayat", riwayat))
    logger.info("🚀 Bot siap menerima perintah...")
    app.run_polling()

if __name__ == "__main__":
    main()
