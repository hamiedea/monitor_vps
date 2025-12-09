#!/usr/bin/env python3
import asyncio
import json
import sqlite3
import logging
import re  # <-- Untuk escape markdown
from pathlib import Path
from telegram import (
    Update,
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
    CallbackQueryHandler,
)
import socket

# Konfigurasi logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# Lokasi file
BASE_DIR = Path(__file__).resolve().parent
CONFIG_FILE = BASE_DIR / "config.json"
DB_FILE = BASE_DIR / "vps_monitor_public.db"


# Fungsi untuk memuat konfigurasi
def load_config():
    if not CONFIG_FILE.is_file():
        raise SystemExit("Error: config.json tidak ditemukan.")
    with open(CONFIG_FILE) as f:
        return json.load(f)


config = load_config()
BOT_TOKEN = config.get("BOT_TOKEN")
MONITOR_INTERVAL = config.get("MONITOR_INTERVAL_SECONDS", 300)


# Fungsi inisialisasi database
def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS vps (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            ip TEXT NOT NULL,
            name TEXT NOT NULL,
            status TEXT DEFAULT 'UNKNOWN',
            UNIQUE(user_id, ip)
        );
    """
    )
    conn.commit()
    conn.close()
    logger.info("Database publik berhasil diinisialisasi.")


# ====== FUNGSI BARU: PARSE IP DAN PORT ======
def parse_ip_port(ip: str, default_port: int = 22):
    """
    Menerima:
      - "1.2.3.4"
      - "1.2.3.4:2000"
    Mengembalikan: (host, port_int)
    Jika port tidak ada / tidak valid → pakai default_port.
    """
    ip = ip.strip()

    if ":" in ip:
        # Split dari belakang supaya aman jika ada ":" lain
        host, port_str = ip.rsplit(":", 1)
        host = host.strip()
        port_str = port_str.strip()

        if port_str.isdigit():
            port = int(port_str)
            if 0 < port < 65536:
                return host, port

    # Kalau tidak ada ":" atau port tidak valid → pakai default_port
    return ip, default_port


# Fungsi cek status VPS (bisa IP dan IP:PORT)
async def check_vps(ip: str, port: int = 22, timeout: int = 3) -> bool:
    """
    ip bisa berupa:
      - "1.2.3.4"      -> akan dicek ke port 22
      - "1.2.3.4:2000" -> akan dicek ke port 2000
    """
    host, port_to_use = parse_ip_port(ip, default_port=port)

    try:
        _, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port_to_use),
            timeout=timeout,
        )
        writer.close()
        await writer.wait_closed()
        return True
    except Exception:
        return False


# FUNGSI UNTUK MENGATASI ERROR MARKDOWNV2
def escape_markdown(text: str) -> str:
    """Mengamankan semua karakter spesial untuk MarkdownV2 Telegram."""
    escape_chars = r"_*[]()~`>#+-=|{}.!"
    return re.sub(f"([{re.escape(escape_chars)}])", r"\\\1", text)


# ----- Fungsi Logika Menu Utama -----
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop("state", None)
    keyboard = [
        [KeyboardButton("➕ Tambah"), KeyboardButton("📋 Daftar")],
        [KeyboardButton("🗑️ Hapus"), KeyboardButton("Ping")],
        [KeyboardButton("❓ Bantuan")],
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(
        "Halo! Selamat datang di bot monitor VPS.\nSilakan pilih menu di bawah ini:",
        reply_markup=reply_markup,
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop("state", None)
    help_text = (
        "➕ *Tambah* - Menambah VPS baru.\n"
        "📋 *Daftar* - Menampilkan semua VPS Anda.\n"
        "🗑️ *Hapus* - Menghapus VPS dari daftar.\n"
        "Ping - Cek status VPS manual.\n"
        "❓ *Bantuan* - Menampilkan pesan ini.\n\n"
        "Gunakan tombol atau ketik /batal untuk membatalkan operasi."
    )
    await update.message.reply_text(help_text, parse_mode="Markdown")


async def daftar_vps(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop("state", None)
    user_id = update.effective_user.id
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, ip, name, status FROM vps WHERE user_id = ? ORDER BY id",
        (user_id,),
    )
    vps_list = cursor.fetchall()
    conn.close()
    if not vps_list:
        await update.message.reply_text(
            "Anda belum menambahkan VPS. Gunakan tombol '➕ Tambah'."
        )
        return

    message_parts = ["*Daftar VPS Anda:*\n"]
    for index, (vps_id, ip, name, status) in enumerate(vps_list, start=1):
        status_emoji = "🟢" if status == "UP" else ("🔴" if status == "DOWN" else "⚪️")

        safe_name = escape_markdown(name)
        safe_ip = escape_markdown(ip)
        safe_status = escape_markdown(status)

        message_parts.append(
            f"{index}\\. *{safe_name}* \\({safe_ip}\\) ID: `{vps_id}` \\- {status_emoji} {safe_status}"
        )

    message = "\n".join(message_parts)
    await update.message.reply_text(message, parse_mode="MarkdownV2")


# ----- Fungsi Logika Percakapan (Manual) -----
async def tambah_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["state"] = "tambah_vps"
    await update.message.reply_text(
        "Kirim daftar IP dan Nama VPS.\n"
        "Format: `IP NAMA` (nama bersifat opsional).\n\n"
        "Contoh:\n`1.1.1.1 VPS Kantor`\n`2.2.2.2`\n\n"
        "Gunakan tombol lain atau /batal untuk membatalkan.",
        parse_mode="Markdown",
    )


async def tambah_receive(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lines = update.message.text.strip().split("\n")

    successful_entries = []
    failed_entries = []

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    for line in lines:
        parts = line.strip().split(maxsplit=1)

        if len(parts) == 1:
            ip = parts[0]
            name = ip
        elif len(parts) == 2:
            ip, name = parts
        else:
            if line:
                failed_entries.append(f"`{line}` (format salah)")
            continue

        cursor.execute(
            "SELECT id FROM vps WHERE user_id = ? AND ip = ?", (user_id, ip)
        )
        if cursor.fetchone():
            failed_entries.append(f"`{ip}` (IP sudah terdaftar)")
            continue

        try:
            cursor.execute(
                "INSERT INTO vps (user_id, ip, name) VALUES (?, ?, ?)",
                (user_id, ip, name),
            )
            is_up = await check_vps(ip)
            status_text = "🟢 UP" if is_up else "🔴 DOWN"
            successful_entries.append(f"`{name}` ({ip}) - *{status_text}*")

        except sqlite3.IntegrityError:
            failed_entries.append(f"`{ip}` (IP sudah terdaftar)")
        except Exception as e:
            logger.error(f"Error saat insert VPS {ip} for user {user_id}: {e}")
            failed_entries.append(f"`{ip}` (error database)")

    conn.commit()
    conn.close()

    message_parts = []
    if successful_entries:
        success_message = "✅ *Berhasil menambahkan:*\n" + "\n".join(
            f"- {entry}" for entry in successful_entries
        )
        message_parts.append(success_message)

    if failed_entries:
        fail_message = "⚠️ *Gagal menambahkan:*\n" + "\n".join(
            f"- {entry}" for entry in failed_entries
        )
        message_parts.append(fail_message)

    if not message_parts:
        message = "Tidak ada input yang diproses. Pastikan formatnya benar."
    else:
        message = "\n\n".join(message_parts)

    await update.message.reply_text(message, parse_mode="Markdown")
    context.user_data.pop("state", None)


async def ping_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["state"] = "ping_vps"
    await update.message.reply_text(
        "Kirim *ID* atau *IP* dari VPS yang ingin Anda ping.\n"
        "Anda bisa mengirim beberapa sekaligus (satu per baris).\n\n"
        "Contoh:\n`1`\n`2.2.2.2`\n`3`\n\n"
        "Gunakan tombol lain atau /batal untuk membatalkan.",
        parse_mode="Markdown",
    )


# ----- PING BARU: bisa ping IP bebas & IP:PORT -----
async def ping_receive(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lines = update.message.text.strip().split("\n")

    results = []
    not_found = []

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    if len(lines) > 1:
        await update.message.reply_text(
            f"🔍 Melakukan ping ke {len(lines)} target, harap tunggu..."
        )

    for line in lines:
        raw = line.strip()
        if not raw:
            continue

        # Hilangkan spasi & backtick supaya lebih toleran
        user_input = raw.replace(" ", "").strip("`")
        if not user_input:
            continue

        ip_to_check = None
        name_to_show = None

        if user_input.isdigit():
            # Input angka → dianggap ID VPS, wajib ada di DB
            cursor.execute(
                "SELECT ip, name FROM vps WHERE id = ? AND user_id = ?",
                (int(user_input), user_id),
            )
            row = cursor.fetchone()
            if row:
                ip_to_check, name_to_show = row
            else:
                not_found.append(f"`{user_input}` (ID tidak ditemukan)")
                continue
        else:
            # Input bukan angka → dianggap IP/IP:PORT
            # Coba cari di DB dulu
            cursor.execute(
                "SELECT ip, name FROM vps WHERE user_id = ? AND ip = ?",
                (user_id, user_input),
            )
            row = cursor.fetchone()
            if row:
                ip_to_check, name_to_show = row
            else:
                # Tidak ada di DB → tetap diping sebagai IP langsung
                ip_to_check = user_input
                name_to_show = user_input

        # Sampai sini pasti punya ip_to_check & name_to_show
        is_up = await check_vps(ip_to_check)
        status_text = "🟢 UP" if is_up else "🔴 DOWN"
        results.append(f"*{name_to_show}* ({ip_to_check}) - {status_text}")

    conn.close()

    message_parts = []
    if results:
        message_parts.append(
            "✅ *Hasil Ping:*\n" + "\n".join(f"- {entry}" for entry in results)
        )

    if not_found:
        message_parts.append(
            "⚠️ *Input tidak ditemukan:*\n" + "\n".join(not_found)
        )

    if not message_parts:
        message = "Tidak ada input yang diproses."
    else:
        message = "\n\n".join(message_parts)

    await update.message.reply_text(message, parse_mode="Markdown")
    context.user_data.pop("state", None)


# ----- Fitur Hapus (Tombol Inline) -----
async def hapus_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop("state", None)
    user_id = update.effective_user.id
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, ip, name FROM vps WHERE user_id = ? ORDER BY id", (user_id,)
    )
    vps_list = cursor.fetchall()
    conn.close()
    if not vps_list:
        await update.message.reply_text("Tidak ada VPS untuk dihapus.")
        return

    keyboard = []
    message_list = ["*Pilih VPS yang ingin Anda hapus:*"]
    for index, (vps_id, ip, name) in enumerate(vps_list, start=1):
        safe_name = escape_markdown(name)
        safe_ip = escape_markdown(ip)

        message_list.append(f"{index}\\. *{safe_name}* \\({safe_ip}\\)")
        keyboard.append(
            [
                InlineKeyboardButton(
                    f"❌ Hapus {name}", callback_data=f"delete_{vps_id}"
                )
            ]
        )

    message = "\n".join(message_list)
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        message, reply_markup=reply_markup, parse_mode="MarkdownV2"
    )


async def hapus_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    vps_id = int(query.data.split("_")[1])
    conn = sqlite3.connect(DB_FILE)
    conn.execute(
        "DELETE FROM vps WHERE id = ? AND user_id = ?",
        (vps_id, query.from_user.id),
    )
    conn.commit()
    conn.close()
    await query.edit_message_text(
        text=f"✅ VPS dengan ID {vps_id} telah berhasil dihapus."
    )


# ----- Fungsi Pembatalan -----
async def batal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if "state" in context.user_data:
        context.user_data.pop("state", None)
        await update.message.reply_text("Operasi dibatalkan.")
    else:
        await update.message.reply_text("Tidak ada operasi untuk dibatalkan.")


# ----- Handler Pesan Utama (Router) -----
async def message_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    state = context.user_data.get("state")
    text = update.message.text

    command_map = {
        "➕ Tambah": tambah_start,
        "📋 Daftar": daftar_vps,
        "🗑️ Hapus": hapus_start,
        "Ping": ping_start,
        "❓ Bantuan": help_command,
    }

    if state:
        if text in command_map:
            await command_map[text](update, context)
        elif state == "tambah_vps":
            await tambah_receive(update, context)
        elif state == "ping_vps":
            await ping_receive(update, context)
    elif text in command_map:
        await command_map[text](update, context)
    else:
        await update.message.reply_text(
            "Perintah tidak dikenali. Silakan gunakan tombol menu."
        )


# ----- Proses Monitoring Otomatis -----
async def monitoring_job(context: ContextTypes.DEFAULT_TYPE):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    vps_list = cursor.execute(
        "SELECT id, user_id, ip, name, status FROM vps"
    ).fetchall()
    for vps_id, user_id, ip, name, old_status in vps_list:
        is_up = await check_vps(ip)
        new_status = "UP" if is_up else "DOWN"
        if new_status != old_status:
            conn.execute(
                "UPDATE vps SET status = ? WHERE id = ?", (new_status, vps_id)
            )
            conn.commit()
            logger.info(
                f"Status {name} ({ip}) milik user {user_id} berubah: {old_status} -> {new_status}"
            )
            message = ""
            if new_status == "DOWN":
                message = f"🔴 *VPS DOWN*\nNama: {name}\nIP: {ip}"
            elif old_status != "UNKNOWN":
                message = f"🟢 *VPS KEMBALI UP*\nNama: {name}\nIP: {ip}"
            if message:
                try:
                    await context.bot.send_message(
                        chat_id=user_id, text=message, parse_mode="Markdown"
                    )
                except Exception as e:
                    logger.error(f"Gagal kirim notifikasi ke {user_id}: {e}")
    conn.close()


# ----- Fungsi Utama -----
def main():
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN tidak ditemukan di config.json.")
    init_db()
    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("batal", batal))
    application.add_handler(CallbackQueryHandler(hapus_button))
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, message_router)
    )

    job_queue = application.job_queue
    job_queue.run_repeating(
        monitoring_job, interval=MONITOR_INTERVAL, first=10
    )
    logger.info("Bot Publik berhasil dijalankan dengan versi final yang stabil...")
    application.run_polling()


if __name__ == "__main__":
    main()
