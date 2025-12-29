# main.py
import os
import sqlite3
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# Buat/koneksi database SQLite
def init_db():
    conn = sqlite3.connect('absensi.db', check_same_thread=False)
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

async def start_smoking(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    username = user.username or f"user_{user_id}"
    now = datetime.now()

    # Hitung sesi hari ini
    today = now.date().isoformat()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM sessions WHERE user_id = ? AND date(start_time) = ?", (user_id, today))
    count = c.fetchone()[0]

    if count >= 3:
        await update.message.reply_text("❌ Anda sudah keluar merokok 3x hari ini. Tidak bisa lagi.")
        return

    # Cek apakah ada sesi aktif (belum /end)
    c.execute("SELECT start_time FROM sessions WHERE user_id = ? AND end_time IS NULL", (user_id,))
    if c.fetchone():
        await update.message.reply_text("⚠️ Anda masih dalam sesi sebelumnya. Gunakan /end dulu!")
        return

    # Simpan sesi baru
    c.execute("INSERT INTO sessions (user_id, username, start_time) VALUES (?, ?, ?)",
              (user_id, username, now.isoformat()))
    conn.commit()

    deadline = now + timedelta(minutes=15)
    await update.message.reply_text(
        f"✅ Keluar merokok ke-{count + 1} hari ini: *{now.strftime('%H:%M')}*\n"
        f"⏳ Batas waktu kembali: *{deadline.strftime('%H:%M')}* (15 menit)\n\n"
        f"Jangan lupa kirim /end saat kembali!",
        parse_mode="Markdown"
    )

async def end_smoking(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    now = datetime.now()
    c = conn.cursor()

    # Cari sesi aktif
    c.execute("SELECT start_time FROM sessions WHERE user_id = ? AND end_time IS NULL", (user_id,))
    row = c.fetchone()

    if not row:
        await update.message.reply_text("⚠️ Tidak ada sesi aktif. Gunakan /start dulu saat keluar.")
        return

    start_time = datetime.fromisoformat(row[0])
    duration = now - start_time
    minutes = int(duration.total_seconds() // 60)

    # Tutup sesi
    c.execute("UPDATE sessions SET end_time = ? WHERE user_id = ? AND end_time IS NULL",
              (now.isoformat(), user_id))
    conn.commit()

    if minutes > 15:
        await update.message.reply_text(
            f"⚠️ *MELEBIHI BATAS!*\nDurasi: *{minutes} menit*\nBatas: 15 menit.",
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text(
            f"✅ Kembali tepat waktu!\nDurasi: *{minutes} menit*.",
            parse_mode="Markdown"
        )

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

    text = "📋 *Riwayat hari ini*:\n"
    for i, (start, end) in enumerate(rows, 1):
        start_dt = datetime.fromisoformat(start)
        if end:
            end_dt = datetime.fromisoformat(end)
            dur = int((end_dt - start_dt).total_seconds() // 60)
            text += f"{i}. {start_dt.strftime('%H:%M')}–{end_dt.strftime('%H:%M')} ({dur} mnt)\n"
        else:
            text += f"{i}. {start_dt.strftime('%H:%M')}–*MASIH DI LUAR!* ⚠️\n"

    await update.message.reply_text(text, parse_mode="Markdown")

# Handler untuk perintah tidak dikenal
async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("gunakan: /start, /end, atau /riwayat")

def main():
    TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    if not TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN belum diatur!")
    
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start_smoking))
    app.add_handler(CommandHandler("end", end_smoking))
    app.add_handler(CommandHandler("riwayat", riwayat))
    app.add_handler(CommandHandler("help", lambda u, c: u.message.reply_text(
        "Perintah:\n/start → mulai keluar\n/end → kembali\n/riwayat → lihat riwayat hari ini"
    )))
    app.add_handler(CommandHandler("unknown", unknown))

    app.run_polling()

if __name__ == "__main__":
    main()
