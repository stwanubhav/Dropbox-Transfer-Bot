import os
import re
import time
import asyncio
import queue
import psutil
from io import BytesIO
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    CallbackQueryHandler,
    filters
)
from dropbox import Dropbox
from dropbox.files import CommitInfo, UploadSessionCursor, WriteMode
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from google.auth.transport.requests import Request as GoogleRequest
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials
import requests
import mimetypes
import uuid
from urllib.parse import urlparse

# Constants
TELEGRAM_TOKEN = 'bot_token_form_bot_father'
DROPBOX_ACCESS_TOKEN = None
TEMP_DOWNLOAD_DIR = 'temp_downloads'
CHUNK_SIZE = 8 * 1024 * 1024  # 4MB for Dropbox upload chunks
DOWNLOAD_CHUNK_SIZE = 4 * 1024 * 1024  # 64KB for download chunks
SCOPES = ['https://www.googleapis.com/auth/drive.readonly']
GDRIVE_AUTH_LINK = None
transfer_queue = queue.Queue()
current_transfer = None
transfer_speeds = {}
oauth_flow = None
application = Application.builder().token(TELEGRAM_TOKEN).build()

class TransferStatus:
    def __init__(self, chat_id, message_id, file_name, file_size, transfer_type):
        self.chat_id = chat_id
        self.message_id = message_id
        self.file_name = file_name
        self.file_size = file_size
        self.transfer_type = transfer_type
        self.start_time = time.time()
        self.last_update = time.time()
        self.last_bytes = 0
        self.completed_bytes = 0

def ensure_gdrive_credentials():
    global oauth_flow
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(GoogleRequest())
        else:
            oauth_flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json',
                SCOPES,
                redirect_uri='urn:ietf:wg:oauth:2.0:oob'
            )
            auth_url, _ = oauth_flow.authorization_url(prompt='consent')
            return auth_url
    return creds

async def gdrive_auth_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global GDRIVE_AUTH_LINK
    auth_result = ensure_gdrive_credentials()
    if isinstance(auth_result, str):
        GDRIVE_AUTH_LINK = auth_result
        await update.message.reply_text(
            "🔐 Please authenticate your Google Drive:\n\n1. Click the button below.\n2. Approve access.\n3. Copy the code and send it as /code <paste_code_here>.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Authorize Google Drive", url=GDRIVE_AUTH_LINK)]
            ])
        )
    else:
        await update.message.reply_text("✅ Already authenticated with Google Drive.")

async def gdrive_code_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global oauth_flow
    if not oauth_flow:
        await update.message.reply_text("⚠️ Please use /auth first to start authentication.")
        return
    if not context.args:
        await update.message.reply_text("❌ Usage: /code <authorization_code>")
        return
    try:
        code = context.args[0]
        oauth_flow.fetch_token(code=code)
        with open('token.json', 'w') as token_file:
            token_file.write(oauth_flow.credentials.to_json())
        await update.message.reply_text("✅ Google Drive authentication complete.")
    except Exception as e:
        await update.message.reply_text(f"❌ Failed to authenticate: {e}")

async def download_gdrive_file(file_id, status):
    try:
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
        service = build('drive', 'v3', credentials=creds)
        file_metadata = service.files().get(fileId=file_id, fields='name,size').execute()
        status.file_name = file_metadata['name']
        status.file_size = int(file_metadata.get('size', 0))
        request = service.files().get_media(fileId=file_id)
        fh = BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            chunk_status, done = downloader.next_chunk()
            if chunk_status:
                status.completed_bytes = chunk_status.progress() * status.file_size
                await update_progress(status)
        os.makedirs(TEMP_DOWNLOAD_DIR, exist_ok=True)
        temp_path = os.path.join(TEMP_DOWNLOAD_DIR, status.file_name)
        with open(temp_path, 'wb') as f:
            f.write(fh.getvalue())
        return temp_path
    except Exception as e:
        raise Exception(f"GDrive API download error: {str(e)}")

async def download_direct_link(url, status):
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': '*/*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Referer': 'https://drive.google.com/',
            'Origin': 'https://drive.google.com',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-site',
        }

        # First make a HEAD request to check if download is allowed
        with requests.head(url, headers=headers, allow_redirects=True, timeout=30) as r:
            r.raise_for_status()
            final_url = r.url
            
            # Check if this is a Google video URL
            if 'video-downloads.googleusercontent.com' in final_url:
                # Need to add special cookies for Google URLs
                cookies = {
                    'DRIVE_STREAM': '1',
                    'NID': '511=your_actual_nid_cookie_here'  # This needs to be obtained
                }
                headers.update({
                    'Cookie': '; '.join([f'{k}={v}' for k, v in cookies.items()])
                })
            
            content_type = r.headers.get('content-type', 'application/octet-stream')
            content_length = int(r.headers.get('content-length', 0))
            
            # Generate filename
            filename = None
            if 'content-disposition' in r.headers:
                content_disposition = r.headers['content-disposition']
                filename_match = re.search(r'filename\*?=(?:"([^"]+)"|([^;\s]+))', content_disposition, re.IGNORECASE)
                if filename_match:
                    filename = filename_match.group(1) or filename_match.group(2)
                    filename = re.sub(r'[\\/*?:"<>|]', "_", filename).strip()
            
            if not filename:
                parsed = urlparse(url)
                filename = os.path.basename(parsed.path)
                if not filename or '.' not in filename:
                    extension = mimetypes.guess_extension(content_type) or '.bin'
                    filename = f"download_{uuid.uuid4().hex[:8]}{extension}"
                else:
                    filename = re.sub(r'[\\/*?:"<>|]', "_", filename)
            
            status.file_name = filename
            status.file_size = content_length if content_length > 0 else 0
            
            # Download the file with streaming
            os.makedirs(TEMP_DOWNLOAD_DIR, exist_ok=True)
            temp_path = os.path.join(TEMP_DOWNLOAD_DIR, filename)
            
            with requests.get(final_url, headers=headers, stream=True, timeout=30) as r:
                r.raise_for_status()
                with open(temp_path, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=DOWNLOAD_CHUNK_SIZE):
                        if chunk:
                            f.write(chunk)
                            status.completed_bytes += len(chunk)
                            await update_progress(status)
            
            return temp_path       
    except Exception as e:
        raise Exception(f"Direct download error: {str(e)}")

def extract_gdrive_file_id(url):
    patterns = [
        r"id=([a-zA-Z0-9_-]{25,})",
        r"/d/([a-zA-Z0-9_-]{25,})",
        r"file/d/([a-zA-Z0-9_-]{25,})",
        r"open\?id=([a-zA-Z0-9_-]{25,})"
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None

def is_downloadable(url):
    try:
        # Basic URL validation
        if not re.match(r'^https?://', url, re.IGNORECASE):
            return False
            
        # Check Google video pattern
        if 'video-downloads.googleusercontent.com' in url:
            return True
            
        # Check common file extensions
        extensions = [
            '.mp4', '.mkv', '.avi', '.mov', '.webm', '.flv', '.wmv',
            '.mp3', '.wav', '.flac', '.aac', '.ogg',
            '.zip', '.rar', '.7z', '.tar', '.gz',
            '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
            '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp',
            '.exe', '.dmg', '.pkg', '.deb', '.rpm',
            '.txt', '.csv', '.json', '.xml'
        ]
        
        url_lower = url.lower()
        if any(url_lower.endswith(ext) for ext in extensions):
            return True
            
        return False
        
    except:
        return False

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message_text = update.message.text.strip()
    
    # Check if it's a Google Drive link
    file_id = extract_gdrive_file_id(message_text)
    if file_id:
        if not DROPBOX_ACCESS_TOKEN:
            await update.message.reply_text("❌ Set Dropbox API token first.")
            return
        transfer_queue.put((update, context, file_id, False))
        await update.message.reply_text(f"📥 Queued. Position: {transfer_queue.qsize()}")
        return
    
    # Check if it's a direct download link
    if is_downloadable(message_text):
        if not DROPBOX_ACCESS_TOKEN:
            await update.message.reply_text("❌ Set Dropbox API token first.")
            return
        transfer_queue.put((update, context, message_text, True))
        await update.message.reply_text(f"📥 Queued. Position: {transfer_queue.qsize()}")
        return
    
    await update.message.reply_text("❌ Please send a valid Google Drive link or direct download URL.")

async def upload_to_dropbox(file_path, status):
    dbx = Dropbox(DROPBOX_ACCESS_TOKEN)
    file_size = os.path.getsize(file_path)
    status.file_size = file_size
    status.transfer_type = "upload"
    with open(file_path, 'rb') as f:
        if file_size <= CHUNK_SIZE:
            dbx.files_upload(f.read(), f'/{status.file_name}', mode=WriteMode('overwrite'))
            status.completed_bytes = file_size
            await update_progress(status)
        else:
            session_start = dbx.files_upload_session_start(f.read(CHUNK_SIZE))
            cursor = UploadSessionCursor(session_id=session_start.session_id, offset=f.tell())
            commit = CommitInfo(path=f'/{status.file_name}', mode=WriteMode('overwrite'))
            while f.tell() < file_size:
                if (file_size - f.tell()) <= CHUNK_SIZE:
                    dbx.files_upload_session_finish(f.read(CHUNK_SIZE), cursor, commit)
                else:
                    dbx.files_upload_session_append_v2(f.read(CHUNK_SIZE), cursor)
                    cursor.offset = f.tell()
                status.completed_bytes = f.tell()
                await update_progress(status)
    os.remove(file_path)

async def update_progress(status):
    now = time.time()
    delta_time = now - status.last_update + 1e-6
    speed = (status.completed_bytes - status.last_bytes) / delta_time
    status.last_bytes = status.completed_bytes
    status.last_update = now

    progress = status.completed_bytes / status.file_size if status.file_size else 0
    bar_blocks = int(progress * 20)
    bar = "▩" * bar_blocks + "□" * (20 - bar_blocks)

    speed_kb = speed / 1024
    eta = (status.file_size - status.completed_bytes) / (speed + 1e-6)

    # System metrics
    cpu = psutil.cpu_percent()
    ram = psutil.virtual_memory().percent

    # Formatting
    def fmt(b):
        for unit in ['B', 'KB', 'MB', 'GB']:
            if b < 1024:
                return f"{b:.2f} {unit}"
            b /= 1024
        return f"{b:.2f} TB"

    current_size = fmt(status.completed_bytes)
    total_size = fmt(status.file_size)
    progress_percent = progress * 100
    eta_str = f"{int(eta)}s" if eta < 60 else f"{int(eta/60)}m {int(eta%60)}s"

    if status.transfer_type == "download":
        title = "╭────── DOWNLOADING ──────〄"
        engine = f"├ CPU: {cpu:.1f}% | RAM: {ram:.1f}%"
    else:
        title = "╭────── UPLOADING ──────〄"
        engine = f"├ Engine: stw_hypx"
    
    msg = (
        f"{title}\n"
        f"│\n"
        f"├ 📁File: {status.file_name[:30]}...\n"
        f"├ Size: {current_size} / {total_size}\n"
        f"│\n"
        f"├ Progress: {progress_percent:.2f}%\n"
        f"│\n"
        f"├ 🚀Speed: {speed_kb:.2f} KB/s\n"
        f"│\n"
        f"├⏱️ ETA: {eta_str}\n"
        f"│\n"
        f"{engine}\n"
        f"│\n"
        f"╰─[{bar}]"
    )
    try:
        await application.bot.edit_message_text(
            chat_id=status.chat_id,
            message_id=status.message_id,
            text=msg
        )
    except:
        pass

async def process_transfer(update, context, file_id_or_url, is_direct_download=False):
    global current_transfer
    chat_id = update.effective_chat.id
    msg = await update.message.reply_text("🔄 Starting...")
    status = TransferStatus(chat_id, msg.message_id, "", 0, "download")
    
    try:
        if is_direct_download:
            file_path = await download_direct_link(file_id_or_url, status)
        else:
            file_path = await download_gdrive_file(file_id_or_url, status)
        
        status.transfer_type = "upload"
        status.completed_bytes = 0
        await upload_to_dropbox(file_path, status)
        await context.bot.send_message(chat_id=chat_id, text=f"✅ Done: {status.file_name}")
    except Exception as e:
        await context.bot.send_message(chat_id=chat_id, text=f"❌ Failed: {str(e)}")
    finally:
        current_transfer = None

async def process_queue():
    global current_transfer
    while True:
        if not transfer_queue.empty() and current_transfer is None:
            item = transfer_queue.get()
            update, context, file_id_or_url, is_direct = item
            current_transfer = file_id_or_url
            await process_transfer(update, context, file_id_or_url, is_direct)
            transfer_queue.task_done()
        await asyncio.sleep(1)

async def api_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global DROPBOX_ACCESS_TOKEN
    if context.args:
        DROPBOX_ACCESS_TOKEN = context.args[0]
        await update.message.reply_text("✅ Dropbox token saved.")
    else:
        await update.message.reply_text("❌ Usage: /api <DROPBOX_TOKEN>")

async def storage_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not DROPBOX_ACCESS_TOKEN:
        await update.message.reply_text("❌ Dropbox token not set.")
        return
    try:
        dbx = Dropbox(DROPBOX_ACCESS_TOKEN)
        usage = dbx.users_get_space_usage()
        used = usage.used
        total = usage.allocation.get_individual().allocated
        def fmt(b):
            for unit in ['B','KB','MB','GB']:
                if b < 1024:
                    return f"{b:.2f} {unit}"
                b /= 1024
            return f"{b:.2f} TB"
        await update.message.reply_text(f"📦 Dropbox Storage:\nUsed: {fmt(used)}\nFree: {fmt(total - used)}\nTotal: {fmt(total)}")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if q.data == "queue_status":
        await q.edit_message_text(f"📊 Queue size: {transfer_queue.qsize()}\nCurrent: {current_transfer if current_transfer else 'None'}")
    elif q.data == "cancel_all":
        while not transfer_queue.empty():
            transfer_queue.get()
            transfer_queue.task_done()
        await q.edit_message_text("✅ Queue cleared.")
    elif q.data == "set_api":
        await q.edit_message_text("Send /api <TOKEN> to set Dropbox access token.")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("Set Dropbox API", callback_data='set_api')],
        [InlineKeyboardButton("Authenticate Google Drive", switch_inline_query_current_chat='/auth')],
        [InlineKeyboardButton("Queue Status", callback_data='queue_status')],
        [InlineKeyboardButton("Cancel All", callback_data='cancel_all')]
    ]
    markup = InlineKeyboardMarkup(keyboard)
    status = "✅ Ready" if DROPBOX_ACCESS_TOKEN else "❌ Not Set"
    await update.message.reply_text(f"🚀 Bot is live!\nStatus: {status}", reply_markup=markup)

async def on_startup(app):
    app.create_task(process_queue())

def main():
    os.makedirs(TEMP_DOWNLOAD_DIR, exist_ok=True)
    app = Application.builder().token(TELEGRAM_TOKEN).post_init(on_startup).build()
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('api', api_command))
    app.add_handler(CommandHandler('storage', storage_command))
    app.add_handler(CommandHandler('auth', gdrive_auth_command))
    app.add_handler(CommandHandler('code', gdrive_code_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.run_polling()

if __name__ == '__main__':
    main()
