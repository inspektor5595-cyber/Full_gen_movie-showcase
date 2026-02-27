#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VoicePro ULTIMATE v28 (MERGED STABLE VERSION):
──────────────────────────────────────────────────────────────────────────────
• CORE: Логика взята из твоего рабочего скрипта (el11_15).
• CONFIG: Подключен config.py для управления из одного места.
• LOGIC: Текст -> Герои -> Рендер Героев -> Промпты -> Итоговые кадры.
"""

import os
import sys
import shutil
import tempfile
import subprocess
import threading
import time
import re
import random
import json
import base64
import urllib3
import requests
from datetime import datetime, timedelta
from queue import Queue, Empty
from concurrent.futures import ThreadPoolExecutor

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def parse_user_input(text):
    """Парсит строку '1 3 5-7' в список [1, 3, 5, 6, 7]"""
    indices = set()
    for part in text.replace(',', ' ').split():
        if '-' in part:
            try:
                start, end = map(int, part.split('-'))
                indices.update(range(start, end + 1))
            except: pass
        else:
            try: indices.add(int(part))
            except: pass
    return sorted(list(indices))

# === 🛠️ ГЛОБАЛЬНЫЙ КЭШ ДЛЯ "УМНОЙ" ЗАГРУЗКИ ===
uploaded_assets_cache = {}  # Тут храним ID уже загруженных файлов
assets_lock = threading.Lock() # Чтобы потоки не мешали друг другу

def get_lazy_asset_id(bot, path, category):
    """
    Проверяет, был ли файл уже загружен. 
    Если да — отдает ID мгновенно. 
    Если нет — грузит на сервер прямо сейчас.
    """
    if not path or not os.path.exists(path): return None
    
    # 1. Быстрая проверка в памяти (без запросов к серверу)
    with assets_lock:
        if path in uploaded_assets_cache:
            return uploaded_assets_cache[path]

    # 2. Если нет — грузим (только нужный файл!)
    fname = os.path.basename(path)
    # print(f"   ⬆️ [Smart Load] Подгружаю референс: {fname}...") # Можно раскомментить для отладки
    
    try:
        mid = bot.upload(path, category)
        if mid:
            with assets_lock:
                uploaded_assets_cache[path] = mid
            return mid
    except: 
        pass
    
    return None

# ─────────────────────────────────────────────────────────────────────────────
# ⚙️ ЗАГРУЗКА НАСТРОЕК ИЗ CONFIG.PY
# ─────────────────────────────────────────────────────────────────────────────
try:
    import config as CFG
    # Маппинг переменных из конфига в локальные переменные скрипта
    SENTENCES_PER_CHUNK    = CFG.SENTENCES_PER_CHUNK
    GENERATE_AUDIO         = CFG.GENERATE_AUDIO
    GENERATE_HEROES_TEXT   = CFG.GENERATE_HEROES_TEXT
    GENERATE_HEROES_IMAGES = CFG.GENERATE_HEROES_IMAGES
    GENERATE_SCENES_TEXT   = CFG.GENERATE_SCENES_TEXT
    GENERATE_SCENES_IMAGES = CFG.GENERATE_SCENES_IMAGES
    DEFAULT_THREADS        = CFG.THREADS_IMAGES
    USER_RATIO             = CFG.USER_RATIO
    MODEL_NAME_IMG         = CFG.MODEL_NAME_IMG
    REVIEW_ASSETS          = CFG.REVIEW_ASSETS
    
    # Пути
    OUTPUT_DIRECTORY_BASE  = CFG.RESULT_BASE
    SUBJECTS_DIR_NAME      = CFG.SUBJECTS_DIR_NAME
    SCENES_DIR_NAME        = CFG.SCENES_DIR_NAME
    STYLES_DIR_NAME        = CFG.STYLES_DIR_NAME
    
    # ElevenLabs
    STANDARD_VOICE_ID      = CFG.VOICE_ID
    VOICE_SIMILARITY       = CFG.VOICE_SIMILARITY
    VOICE_STABILITY        = CFG.VOICE_STABILITY
    VOICE_SPEED            = CFG.VOICE_SPEED
    SILENCE_SEC            = CFG.SILENCE_SEC
    
    # Proxy
    USE_PROXY              = CFG.USE_PROXY
    PROXY_ROTATION_MODE    = CFG.PROXY_ROTATION_MODE
    PROXY_LOGIN            = CFG.PROXY_LOGIN
    PROXY_PASSWORD         = CFG.PROXY_PASSWORD
    PROXY_HOST             = CFG.PROXY_HOST
    
    GEMINI_MODEL           = CFG.GEMINI_MODEL

   
    SYS_PROMPT_IMG_CFG     = CFG.GEMINI_SYS_PROMPT_IMG  # <--- ДЛЯ КАРТИНОК
    SYS_PROMPT_VID_CFG     = CFG.GEMINI_SYS_PROMPT_VID  # <--- ДЛЯ ВИДЕО

    SYS_PROMPT_SUBJECTS_CFG = CFG.GEMINI_SYS_PROMPT_SUBJECTS
    SYS_PROMPT_SCENES_CFG   = CFG.GEMINI_SYS_PROMPT_SCENES
    # ==========================

    print("✅ [el11_15] Настройки загружены из config.py")

except ImportError:
    print("❌ Файл config.py не найден! Запустите main.py.")
    sys.exit(1)

# ─────────────────────────────────────────────────────────────────────────────
#              ВНУТРЕННЯЯ ЛОГИКА И ПУТИ
# ─────────────────────────────────────────────────────────────────────────────
if USER_RATIO == "16:9":
    ASPECT_RATIO = "IMAGE_ASPECT_RATIO_LANDSCAPE"
else:
    ASPECT_RATIO = "IMAGE_ASPECT_RATIO_PORTRAIT"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
INPUT_TEXT_FILE        = os.path.join(BASE_DIR, "script.txt")
CSV_FILE_PATH          = os.path.join(BASE_DIR, "base.txt")
GEMINI_KEYS_FILE       = os.path.join(BASE_DIR, "api_keys.txt")
COOKIES_FILE           = os.path.join(BASE_DIR, "cookies.txt")
VIDEO_STYLE_FILE       = os.path.join(BASE_DIR, "video_style.txt")

# Глобальные переменные путей (будут обновлены при создании сессии)
SUBJECTS_DIRECTORY     = os.path.join(BASE_DIR, SUBJECTS_DIR_NAME)
STYLES_DIRECTORY       = os.path.join(BASE_DIR, STYLES_DIR_NAME)
SCENES_DIRECTORY       = os.path.join(BASE_DIR, SCENES_DIR_NAME)

prompts_storage = {}
video_prompts_storage = {}
prompts_lock = threading.Lock()

# Файлы заглушки
DEFAULT_SUBJECT = CFG.DEFAULT_SUBJECT
DEFAULT_STYLE   = CFG.DEFAULT_STYLE
REALISM_REFERENCE = CFG.REALISM_REFERENCE

# ─────────────────────────────────────────────────────────────────────────────
#                НАСТРОЙКИ PROXY
# ─────────────────────────────────────────────────────────────────────────────
proxies = {}
rotate_lock = threading.Lock()
last_rotate_ts = 0.0
ROTATE_ENDPOINT = "https://gw.dataimpulse.com:777/api/rotate_ip"
MIN_ROTATE_SEC = 31

def init_proxy():
    global proxies
    if not USE_PROXY:
        proxies = {}
        return
    if PROXY_ROTATION_MODE == "PORT":
        port = str(random.randint(10000, 19999))
        print(f"🌍 [PROXY] Mode: PORT ROTATION (Start Port: {port})")
    else:
        port = "10000" # Default for API mode
        print(f"🌍 [PROXY] Mode: API LINK ROTATION")
    
    url = f"http://{PROXY_LOGIN}:{PROXY_PASSWORD}@{PROXY_HOST}:{port}"
    proxies = {"http": url, "https": url}

def rotate_proxy():
    global proxies, last_rotate_ts
    if not USE_PROXY: return
    with rotate_lock:
        if PROXY_ROTATION_MODE == "PORT":
            new_port = str(random.randint(10000, 19999))
            print(f"♻️ [PROXY] Смена порта -> {new_port}")
            url = f"http://{PROXY_LOGIN}:{PROXY_PASSWORD}@{PROXY_HOST}:{new_port}"
            proxies = {"http": url, "https": url}
            time.sleep(1)
        elif PROXY_ROTATION_MODE == "API":
            now = time.time()
            if now - last_rotate_ts < MIN_ROTATE_SEC: return
            try:
                requests.get(ROTATE_ENDPOINT, params={"port": "10000"}, auth=(PROXY_LOGIN, PROXY_PASSWORD), timeout=10)
            except: pass
            last_rotate_ts = time.time()
            time.sleep(5)

init_proxy()

# ElevenLabs Constants
DEFAULT_MIN_BYTES = 1024
COMMON_HEADERS = {"User-Agent": "Mozilla/5.0...","Origin": "https://elevenlabs.io"}
REQUEST_TIMEOUT = 20
FIREBASE_API_KEY = "AIzaSyBSsRE_1Os04-bxpd5JTLIniy3UK4OqKys" # Хардкод для работы хака

# ─────────────────────────────────────────────────────────────────────────────
#                           AUDIO CORE
# ─────────────────────────────────────────────────────────────────────────────
csv_lock = threading.Lock()
reserved_keys = set()

def get_or_create_session(force_id=None):
    """
    Если force_id передан — возвращает пути к этой сессии.
    Если нет — создает новую (N+1).
    """
    global SUBJECTS_DIRECTORY, SCENES_DIRECTORY

    if not os.path.exists(OUTPUT_DIRECTORY_BASE): os.makedirs(OUTPUT_DIRECTORY_BASE)
    
    if force_id:
        session_str = str(force_id)
        print(f"♻️ ИСПОЛЬЗУЮ СУЩЕСТВУЮЩУЮ СЕССИЮ: {session_str}")
    else:
        existing_dirs = []
        for d in os.listdir(OUTPUT_DIRECTORY_BASE):
            full_p = os.path.join(OUTPUT_DIRECTORY_BASE, d)
            if os.path.isdir(full_p) and d.isdigit(): existing_dirs.append(int(d))
        next_num = max(existing_dirs) + 1 if existing_dirs else 1
        session_str = str(next_num)
        print(f"✨ СОЗДАЮ НОВУЮ СЕССИЮ: {session_str}")

    # Пути
    new_session_path = os.path.join(OUTPUT_DIRECTORY_BASE, session_str)
    
    # Создаем папки (makedirs с exist_ok=True не сломается, если папки уже есть)
    os.makedirs(new_session_path, exist_ok=True)
    os.makedirs(os.path.join(new_session_path, "audio"), exist_ok=True)
    os.makedirs(os.path.join(new_session_path, "images"), exist_ok=True)
    os.makedirs(os.path.join(new_session_path, "videos"), exist_ok=True)

    # Обновляем глобальные пути к ассетам
    # ВАЖНО: Если мы продолжаем сессию 12, мы должны искать героев в subjects/12
    # Но в начале скрипта SUBJECTS_DIRECTORY указывает на 'subjects'.
    # Нам нужно правильно склеить путь.
    
    base_subj = os.path.join(BASE_DIR, "subjects") # Жесткая привязка к корню
    base_scen = os.path.join(BASE_DIR, "scenes")
    
    SUBJECTS_DIRECTORY = os.path.join(base_subj, session_str)
    SCENES_DIRECTORY = os.path.join(base_scen, session_str)
    
    os.makedirs(SUBJECTS_DIRECTORY, exist_ok=True)
    os.makedirs(SCENES_DIRECTORY, exist_ok=True)

    print(f"   📂 Result:   {new_session_path}")
    
    return new_session_path

def _load_rows():
    rows = []
    if not os.path.exists(CSV_FILE_PATH): return rows
    with open(CSV_FILE_PATH, encoding="utf-8") as f:
        for line in f:
            parts = line.strip().split(':')
            if len(parts) >= 2: rows.append({"API": parts[0].strip(), "Refresh": parts[1].strip(), "Date": parts[2].strip() if len(parts)>2 else ""})
    return rows

def _save_rows(rows):
    tmp = CSV_FILE_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        for row in rows:
            line = f"{row['API']}:{row['Refresh']}"
            if row["Date"]: line += f":{row['Date']}"
            f.write(line + "\n")
    shutil.move(tmp, CSV_FILE_PATH)

def get_free_user_credentials():
    with csv_lock:
        rows = _load_rows()
        limit = datetime.now().date() - timedelta(days=31)
        candidates = [row for row in rows if row["API"] not in reserved_keys and (not row["Date"] or datetime.strptime(row["Date"], "%d.%m.%Y").date() <= limit)]
        if not candidates: return None
        row = candidates[0] 
        reserved_keys.add(row["API"])
        return row

def mark_api_key_exhausted(api_key):
    with csv_lock:
        rows = _load_rows()
        for row in rows:
            if row["API"] == api_key: row["Date"] = datetime.now().strftime("%d.%m.%Y"); break
        _save_rows(rows)
    reserved_keys.discard(api_key)

def get_access_token(refresh_token):
    headers = COMMON_HEADERS.copy()
    headers["Content-Type"] = "application/x-www-form-urlencoded"
    try:
        resp = requests.post(f"https://securetoken.googleapis.com/v1/token?key={FIREBASE_API_KEY}", data={"grant_type": "refresh_token", "refresh_token": refresh_token}, headers=headers, proxies=proxies, timeout=REQUEST_TIMEOUT)
        if resp.status_code == 200: 
            return resp.json().get("id_token") or resp.json().get("access_token")
    except: pass
    return None

def text_to_speech(access_token, text, out_file, voice_id, *args):
    """Генерация аудио. Молча обрабатывает лимиты и ловит только строгую цензуру."""
    url = f"https://api.us.elevenlabs.io/v1/text-to-speech/{voice_id}/stream"
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json", **COMMON_HEADERS}
    
    # Защита от отсутствия настроек
    sim = getattr(CFG, 'VOICE_SIMILARITY', 0.75) if 'CFG' in globals() else 0.75
    stab = getattr(CFG, 'VOICE_STABILITY', 0.50) if 'CFG' in globals() else 0.50
    spd = getattr(CFG, 'VOICE_SPEED', 1.0) if 'CFG' in globals() else 1.0
    
    payload = {"text": text, "model_id": "eleven_multilingual_v2", "voice_settings": {"similarity_boost": sim, "stability": stab}, "generation_config": {"speed": spd}}
    
    try:
        r = requests.post(url, json=payload, headers=headers, proxies=proxies, timeout=25, stream=True)
        if r.status_code == 200:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as t:
                for chunk in r.iter_content(chunk_size=1024):
                    if chunk: t.write(chunk)
                tmp = t.name
            try:
                silence_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3").name
                subprocess.run(["ffmpeg", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono", "-t", str(SILENCE_SEC), "-q:a", "9", silence_file, "-y"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                concat_file = tempfile.NamedTemporaryFile(delete=False, mode="w").name
                with open(concat_file, "w") as f: f.write(f"file '{tmp}'\nfile '{silence_file}'\n")
                subprocess.run(["ffmpeg", "-f", "concat", "-safe", "0", "-i", concat_file, "-c", "copy", out_file, "-y"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
                os.remove(tmp); os.remove(silence_file); os.remove(concat_file)
                return "success"
            except: return "error"
        
        err_text = r.text.lower()
        
        # 1. СТРОГАЯ ЦЕНЗУРА (отправляем сигнал на рерайт)
        if r.status_code == 400 and ("policy" in err_text or "profanity" in err_text or "unacceptable" in err_text): 
            return "bad_text"
            
        # 2. СГОРЕЛ КЛЮЧ ИЛИ ЛИМИТЫ (выкидываем ключ молча)
        if r.status_code in [401, 402, 429] or "quota" in err_text or "limit" in err_text: 
            return "quota_exceeded"
            
        # 3. ВСЁ ОСТАЛЬНОЕ (глюки сети)
        rotate_proxy()
        return "network_retry"
    except:
        rotate_proxy()
        return "network_retry"

def emergency_rewrite_audio_text(bad_text):
    """Резервный рерайт текста ТОЛЬКО при реальной цензуре ElevenLabs."""
    key = get_gemini_key()
    if not key: return bad_text
    print(f"   🕵️ Цензура заблокировала текст. Отправляю в Gemini на рерайт...")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={key}"
    sys_prompt = (
        "The following text was blocked by a strict text-to-speech system. "
        "NEUTRALIZE the text so it passes censorship, but preserve the original language and length. "
        "Output ONLY the neutralized text with no apologies.\n\n"
        f"TEXT: '{bad_text}'"
    )
    safety = [
        {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}
    ]
    try:
        r = requests.post(url, json={"contents": [{"parts": [{"text": sys_prompt}]}], "safetySettings": safety}, proxies=proxies, timeout=20)
        if r.status_code == 200:
            return r.json()["candidates"][0]["content"]["parts"][0]["text"].strip().replace("\n", " ")
    except: pass
    return bad_text

def worker_audio(task_queue, out_dir):
    """Многопоточный воркер аудио."""
    while True:
        try: task = task_queue.get_nowait()
        except Empty: break
        
        # Распаковываем умную задачу
        chunk_idx = task[0]
        text = task[1]
        is_first = task[2]
        fails = task[3] if len(task) > 3 else 0
            
        file_name = f"{chunk_idx+1:04d}.mp3"
        final_path = os.path.join(out_dir, file_name)
        
        # --- ЛОГИКА ДЛЯ ДОПОЛНИТЕЛЬНЫХ КАДРОВ ---
        if not is_first:
            if not os.path.exists(final_path):
                open(final_path, 'w').close() # Создаем файл-маркер весом 0 байт
            task_queue.task_done()
            continue
            
        if os.path.exists(final_path) and os.path.getsize(final_path) > 1024:
            task_queue.task_done(); continue
            
        creds = get_free_user_credentials()
        if not creds:
            print(f"🛑 [Audio {chunk_idx+1}] Нет свободных ключей в базе!"); task_queue.put(task); task_queue.task_done(); return
        
        api_key, token = creds["API"], get_access_token(creds["Refresh"])
        if not token:
            rotate_proxy(); reserved_keys.discard(api_key); task_queue.put(task); task_queue.task_done(); continue
            
        res = text_to_speech(token, text, final_path, STANDARD_VOICE_ID, chunk_idx)
        
        if res == "success":
            print(f"✅ [Audio {chunk_idx+1}] Готово")
            reserved_keys.discard(api_key)
        elif res == "quota_exceeded":
            # Молча сжигаем ключ и возвращаем задачу в очередь
            mark_api_key_exhausted(api_key)
            task_queue.put(task)
        elif res == "bad_text":
            reserved_keys.discard(api_key)
            if fails < 2:
                new_text = emergency_rewrite_audio_text(text)
                task_queue.put((chunk_idx, new_text, fails + 1))
            else:
                # Если после двух рерайтов всё равно бан — ставим тишину, чтобы скрипт не завис навсегда
                print(f"⚠️ [Audio {chunk_idx+1}] Текст безнадежен. Ставлю тишину.")
                open(final_path, 'w').close() 
        else:
            # Сетевая ошибка - просто пробуем еще раз
            reserved_keys.discard(api_key)
            task_queue.put(task)
            time.sleep(1)
            
        task_queue.task_done()

def split_text_into_smart_chunks(full_text, n_sentences):
    text = full_text.replace("\r\n", " ").replace("\n", " ").strip()
    raw_sentences = re.split(r'(?<=[.!?])\s+(?=[A-ZА-ЯЁ]|$)', text)
    final_chunks = []; current_chunk = []
    for sent in raw_sentences:
        if not sent.strip(): continue
        current_chunk.append(sent.strip())
        if len(current_chunk) >= n_sentences:
            final_chunks.append(" ".join(current_chunk)); current_chunk = []
    if current_chunk: final_chunks.append(" ".join(current_chunk))
    return final_chunks

def split_text_by_visual_cues(full_text):
    """Умная нарезка текста на основе визуальных сцен через Gemini."""
    print("\n--- [GEMINI] Умная нарезка текста по визуальным сценам... ---")
    key = get_gemini_key()
    if not key:
        print("   ❌ Нет ключа API. Откат к нарезке по точкам.")
        return split_text_into_smart_chunks(full_text, SENTENCES_PER_CHUNK)

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={key}"
    
    # Просим нейросеть вставить тег [CUT] там, где должна смениться картинка
    sys_prompt = (
        "You are an expert film director and video editor.\n"
        "TASK: Split the provided script into a sequence of visual camera shots.\n\n"
        "CRITICAL RULES:\n"
        "1. Insert the exact token `[CUT]` whenever the visual focus changes (e.g., from 'the son' to 'the father', or from a wide landscape to a close-up action).\n"
        "2. IGNORE grammar! You can insert `[CUT]` right in the middle of a sentence if the camera needs to show a different subject.\n"
        "3. DO NOT alter, translate, or remove ANY original words. ONLY insert `[CUT]` between the original words.\n"
        "4. Return ONLY the modified text with `[CUT]` tokens."
    )
    
    try:
        r = requests.post(url, json={"contents": [{"parts": [{"text": sys_prompt + "\n\nTEXT:\n" + full_text}]}]}, proxies=proxies, timeout=60)
        if r.status_code == 200:
            raw_text = r.json()["candidates"][0]["content"]["parts"][0]["text"]
            
            # Очищаем от мусора и разбиваем текст по нашему тегу
            clean_text = raw_text.replace("```text", "").replace("```", "").strip()
            chunks = [c.strip() for c in clean_text.split("[CUT]") if c.strip()]
            
            if len(chunks) > 1:
                print(f"   ✅ Сценарий разбит на {len(chunks)} визуальных кадров!")
                return chunks
            else:
                print("   ⚠️ Gemini не нашел мест для склейки.")
    except Exception as e:
        print(f"   ❌ Ошибка ИИ-нарезки: {e}")
        
    print("   ⚠️ Откат к базовой нарезке по предложениям.")
    return split_text_into_smart_chunks(full_text, SENTENCES_PER_CHUNK)

def prepare_smart_chunks(full_text):
    print("\n--- [GEMINI] Умная раскадровка (1 озвучка = N картинок)... ---")
    key = get_gemini_key()
    if not key:
        print("   ❌ Нет ключа API. Откат к обычной нарезке.")
        ch = split_text_into_smart_chunks(full_text, SENTENCES_PER_CHUNK)
        return ch, [(c, True) for c in ch]

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={key}"
    
    sys_prompt = (
        "You are an expert film director.\n"
        "TASK: Analyze the provided text and break it down into a chronological sequence of sentences. Then, for EACH sentence, define 1, 2, or 3 visual shots that represent the action.\n"
        "CRITICAL RULES:\n"
        "1. You MUST include EVERY SINGLE SENTENCE from the original text in order. Do not skip any words.\n"
        "2. If a sentence has multiple characters or changing actions (e.g., 'son played, father smoked'), give it 2 or 3 distinct visual shots. If it's a simple scene, 1 shot is enough.\n"
        "OUTPUT FORMAT: Return ONLY a valid JSON array of objects. Example:\n"
        "[\n"
        "  {\"sentence\": \"The son played in the sand, while the father smoked.\", \"shots\": [\"Son playing in sandbox\", \"Father smoking on balcony\"]},\n"
        "  {\"sentence\": \"A car drove by.\", \"shots\": [\"A black car drives past the house\"]}\n"
        "]"
    )
    
    try:
        r = requests.post(url, json={"contents": [{"parts": [{"text": sys_prompt + "\n\nTEXT:\n" + full_text}]}]}, proxies=proxies, timeout=90)
        raw_text = r.json()["candidates"][0]["content"]["parts"][0]["text"]
        match = re.search(r'\[.*\]', raw_text, re.DOTALL)
        if match:
            data = json.loads(match.group(0))
            
            visual_chunks = []
            audio_tasks = []
            
            for item in data:
                sentence = item.get("sentence", "")
                shots = item.get("shots", [])
                if not sentence or not shots: continue
                
                for i, shot in enumerate(shots):
                    visual_chunks.append(shot)
                    if i == 0:
                        audio_tasks.append((sentence, True)) # Для первого кадра - реальная озвучка всего предложения
                    else:
                        audio_tasks.append(("", False))      # Для остальных кадров - пустой маркер
                        
            if visual_chunks:
                print(f"   ✅ Текст разбит на {len(data)} фраз для диктора и {len(visual_chunks)} визуальных кадров!")
                return visual_chunks, audio_tasks
    except Exception as e:
        print(f"   ❌ Ошибка ИИ-нарезки: {e}")
        
    print("   ⚠️ Откат к базовой нарезке по предложениям.")
    ch = split_text_into_smart_chunks(full_text, SENTENCES_PER_CHUNK)
    return ch, [(c, True) for c in ch]

# ─────────────────────────────────────────────────────────────────────────────
#                           GEMINI CORE
# ─────────────────────────────────────────────────────────────────────────────
def get_gemini_key():
    if os.path.exists(GEMINI_KEYS_FILE):
        with open(GEMINI_KEYS_FILE, "r") as f: keys = [l.strip() for l in f if l.strip()]
        return random.choice(keys) if keys else None
    return None

def create_subjects(text, style_text):
    print(f"\n--- [GEMINI] Анализ героев под стиль... ---")
    try:
        base_prompt = SYS_PROMPT_SUBJECTS_CFG.format(text=text[:30000])
    except:
        base_prompt = f"{SYS_PROMPT_SUBJECTS_CFG}\n\nTEXT:\n{text[:30000]}"

    # Внедряем стиль прямо в мозг Gemini перед генерацией описания
    if style_text:
        sys_prompt = f"CRITICAL CONTEXT: The overall visual style of this story is '{style_text}'. You MUST adapt the physical descriptions (clothes, vibe, accessories) of the characters to strictly fit this exact style.\n\n{base_prompt}"
    else:
        sys_prompt = base_prompt

    for attempts in range(1, 11): 
        key = get_gemini_key() 
        if not key: return ""
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={key}"

        try:
            r = requests.post(url, json={"contents": [{"parts": [{"text": sys_prompt}]}]}, proxies=proxies, timeout=(5, 90))
            # ... (остальной код функции остается без изменений)
            
            if r.status_code == 429:
                print(f"   ⏳ 429 (Лимит). Жду 5с... | ", end='', flush=True)
                time.sleep(5)
                continue
            elif r.status_code != 200:
                print(f"   ❌ {r.status_code} | ", end='', flush=True)
                time.sleep(2)
                continue

            res_json = r.json()
            if "candidates" in res_json and res_json["candidates"]:
                raw_text = res_json["candidates"][0]["content"]["parts"][0]["text"]
                print(f"   ✅ Gemini ответил ({len(raw_text)} символов)")
                return raw_text

            print("⚠️ Empty | ", end='', flush=True)
            time.sleep(2)

        except Exception as e:
            print(f"🔥 Fail ({type(e).__name__}) | ", end='', flush=True)
            time.sleep(3)

    print(f"\n❌ Не удалось получить ответ после 10 попыток")
    return ""

def save_subjects(text):
    if not text: 
        print("❌ [GEMINI] Ответ пустой!")
        return
    
    # DEBUG: Показываем сырой ответ, чтобы видеть ошибки
    print(f"DEBUG RAW RESPONSE:\n{text[:200]}...\n") 

    lines = text.split('\n')
    count = 0
    seen_names = set()
    
    if not os.path.exists(SUBJECTS_DIRECTORY): os.makedirs(SUBJECTS_DIRECTORY)

    for line in lines:
        clean_line = line.replace('*', '').replace('#', '').strip()
        if not clean_line or len(clean_line) < 5: continue

        # Логика: ищем разделитель (двоеточие ИЛИ тире)
        parts = []
        if ":" in clean_line:
            parts = clean_line.split(":", 1)
        elif " - " in clean_line:
            parts = clean_line.split(" - ", 1)
        
        if len(parts) == 2:
            name_raw = parts[0].strip()
            desc = parts[1].strip()
            
            # Очистка имени
            safe_name = re.sub(r'[^a-zA-Z0-9]', "", name_raw)
            if len(safe_name) > 20: safe_name = safe_name[:20]
            
            if not safe_name: continue
            if safe_name in seen_names: continue
            
            seen_names.add(safe_name)
            target_path = os.path.join(SUBJECTS_DIRECTORY, f"{safe_name}.txt")
            with open(target_path, "w", encoding="utf-8") as f: f.write(desc)
            count += 1
            print(f"   👤 Hero saved: {safe_name}")

    if count == 0:
        print("⚠️ Gemini вернул текст, но скрипт не смог найти имена. Создаю 'DefaultCharacter'.")
        with open(os.path.join(SUBJECTS_DIRECTORY, "DefaultCharacter.txt"), "w", encoding="utf-8") as f:
            f.write("A generic person, neutral appearance")
        count = 1

    print(f">>> Итог: {count} героев.")

def create_scenes(text, style_text):
    print("\n--- [GEMINI] Анализ локаций под стиль... ---")
    try:
        base_prompt = SYS_PROMPT_SCENES_CFG.format(text=text[:30000])
    except:
        base_prompt = f"{SYS_PROMPT_SCENES_CFG}\n\nTEXT:\n{text[:30000]}"

    if style_text:
        sys_prompt = f"CRITICAL CONTEXT: The overall visual style of this story is '{style_text}'. You MUST adapt all environmental descriptions (architecture, lighting, textures, atmosphere) to strictly fit this exact style.\n\n{base_prompt}"
    else:
        sys_prompt = base_prompt

    for attempts in range(1, 11):
        key = get_gemini_key()
        if not key: return ""
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={key}"
        
        try:
            r = requests.post(url, json={"contents": [{"parts": [{"text": sys_prompt}]}]}, proxies=proxies, timeout=(5, 90))
            # ... (остальной код функции остается без изменений)
            if r.status_code == 429:
                print(f"   ⏳ 429 | ", end='', flush=True)
                time.sleep(5)
                continue
            if r.status_code == 200:
                return r.json()["candidates"][0]["content"]["parts"][0]["text"]
        except: pass
        time.sleep(2)
    return ""

def save_scenes(text):
    if not text: return
    lines = text.split('\n')
    count = 0
    
    if not os.path.exists(SCENES_DIRECTORY): os.makedirs(SCENES_DIRECTORY)

    for line in lines:
        clean_line = line.replace('*', '').replace('#', '').strip()
        if not clean_line: continue

        parts = []
        if ":" in clean_line:
            parts = clean_line.split(":", 1)
        elif " - " in clean_line:
            parts = clean_line.split(" - ", 1)

        if len(parts) == 2:
            name_raw = parts[0].strip()
            desc = parts[1].strip()
            
            safe_name = re.sub(r'[^a-zA-Z0-9]', "", name_raw)
            if len(safe_name) > 30: safe_name = safe_name[:30]
            if not safe_name: continue
            
            target_path = os.path.join(SCENES_DIRECTORY, f"{safe_name}.txt")
            with open(target_path, "w", encoding="utf-8") as f: f.write(desc)
            count += 1
            print(f"   🏠 Scene saved: {safe_name}")
            
    # ФОЛЛБЭК: Если ничего не нашел, создаем дефолт
    if count == 0:
        print("⚠️ Локации не найдены. Создаю 'DefaultScene'.")
        with open(os.path.join(SCENES_DIRECTORY, "DefaultScene.txt"), "w", encoding="utf-8") as f:
            f.write("Simple minimal background, abstract style")
        count = 1

    print(f">>> Итог: {count} локаций.")

def load_subjects():
    subs = {}
    if os.path.exists(SUBJECTS_DIRECTORY):
        for f in os.listdir(SUBJECTS_DIRECTORY):
            if f.endswith(".txt"):
                name = os.path.splitext(f)[0]
                with open(os.path.join(SUBJECTS_DIRECTORY, f), "r", encoding="utf-8") as file: subs[name] = file.read().strip()
    return subs

def generate_prompts_batch(chunks_batch, prev_chunks_batch, ctx, subjects_list, scenes_list, style_text):
    subj_str = ", ".join(subjects_list) if subjects_list else "None"
    scene_str = ", ".join(scenes_list) if scenes_list else "None"

    batch_text = ""
    for i, (curr, prev) in enumerate(zip(chunks_batch, prev_chunks_batch)):
        # Сделали разделители более явными, чтобы Gemini видел таймлайн
        batch_text += f"--- SCENE {i+1} ---\nPREVIOUS NARRATIVE: '{prev}'\nCURRENT NARRATIVE: '{curr}'\n\n"

    try:
        base_instruction = SYS_PROMPT_IMG_CFG.format(subj=subj_str, scene=scene_str)
    except:
        base_instruction = SYS_PROMPT_IMG_CFG

    style_instruction = f"CRITICAL VISUAL STYLE: The overall style of the story is '{style_text}'. You MUST adapt the lighting, mood, color palette, and atmosphere in your descriptions to strictly fit this exact style.\n\n" if style_text else ""

    sys_prompt = (
        f"{base_instruction}\n\n"
        f"{style_instruction}"
        f"STORY CONTEXT:\n{ctx}\n\n"
        f"=== BATCH REQUEST ({len(chunks_batch)} SEQUENTIAL SCENES) ===\n"
        f"CRITICAL: The following scenes happen ONE IMMEDIATELY AFTER THE OTHER. You MUST maintain strict visual continuity. If characters (like 'five girls') are in Scene 1, they must still be visibly described in Scene 2 unless the text says they left. Track who is in the scene!\n\n"
        f"{batch_text}"
        "INSTRUCTION: Analyze each scene and write a highly visual description for it. Ensure logical transition and character persistence between scenes.\n"
        f"CRITICAL: You MUST use the EXACT character names ({subj_str}) and location names ({scene_str}) in EVERY description.\n"
        "OUTPUT FORMAT: Return ONLY a valid JSON array of strings. Example: [\"Description 1\", \"Description 2\"]. Do not add any conversational text."
    )

    attempts = 0
    # БЕСКОНЕЧНЫЙ ЦИКЛ - скрипт не пойдет дальше, пока не получит идеальный массив
    while True:
        attempts += 1
        key = get_gemini_key()
        if not key:
            time.sleep(2)
            continue
            
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={key}"
        
        try:
            r = requests.post(url, json={"contents": [{"parts": [{"text": sys_prompt}]}]}, proxies=proxies, timeout=(5, 90))
            
            if r.status_code == 429:
                print(f"   ⏳ 429 | ", end='', flush=True)
                time.sleep(5)
                continue
            if r.status_code != 200:
                print(f"   ❌ {r.status_code} | ", end='', flush=True)
                time.sleep(2)
                continue

            res_json = r.json()
            if "candidates" in res_json and res_json["candidates"]:
                raw_text = res_json["candidates"][0]["content"]["parts"][0]["text"]
                
                # УМНЫЙ ПАРСИНГ: Ищем массив [ ... ] через регулярку, игнорируя любой текст до и после
                match = re.search(r'\[.*\]', raw_text, re.DOTALL)
                if match:
                    clean_json = match.group(0)
                    try:
                        results = json.loads(clean_json)
                        if isinstance(results, list) and len(results) == len(chunks_batch):
                            return results
                        else:
                            print(f"⚠️ Mismatch ({len(results)}/{len(chunks_batch)}) | ", end='', flush=True)
                    except:
                        print(f"⚠️ JSON Parse Error | ", end='', flush=True)
                else:
                    print(f"⚠️ No JSON array found | ", end='', flush=True)
            else:
                print("⚠️ Empty | ", end='', flush=True)

        except Exception as e:
            print(f"🔥 Fail ({type(e).__name__}) | ", end='', flush=True)
            
        # Если Gemini тупит больше 10 раз - даем ему остыть дольше
        if attempts > 10:
            print("💤 Долгая пауза (15с)... | ", end='', flush=True)
            time.sleep(15)
        else:
            time.sleep(3)

def generate_smart_video_action(current_chunk, visual_description):
    """
    Генерирует видео-промпт, используя инструкцию из CONFIG.PY.
    """
    key = get_gemini_key()
    if not key: return "Cinematic motion"
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={key}"
    
    sys_prompt = (
        f"{SYS_PROMPT_VID_CFG}\n\n"
        f"SCRIPT/AUDIO CONTEXT: '{current_chunk}'\n"
        f"VISUAL CONTEXT (Image): '{visual_description}'\n\n"
        "OUTPUT THE VIDEO PROMPT NOW:"
    )
    
    try:
        r = requests.post(url, json={"contents": [{"parts": [{"text": sys_prompt}]}]}, proxies=proxies, timeout=15)
        text = r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
        return text.replace("\n", " ").replace('"', '').replace("Video prompt:", "")
    except: return "Cinematic slow motion"


def generate_video_prompts_batch(chunks_batch, prev_chunks_batch, img_prompts_batch, video_style_text):

    batch_text = ""
    for i, (curr, prev, img_prompt) in enumerate(zip(chunks_batch, prev_chunks_batch, img_prompts_batch)):
        batch_text += f"--- SCENE {i+1} ---\nPREVIOUS NARRATIVE: '{prev}'\nCURRENT NARRATIVE: '{curr}'\nIMAGE TO ANIMATE: '{img_prompt}'\n\n"

    sys_prompt = (
        "You are an expert AI video animation director and continuity editor. Your task is to take a static IMAGE DESCRIPTION and create a MOTION PROMPT for an AI video generator (like Grok).\n\n"
        "CRITICAL RULES:\n"
        "1. ZERO PROPER NOUNS: You must NEVER use specific character names. Replace them entirely with generic visual nouns (e.g., use 'five women', 'the man', 'the group'). AI video generators don't know your specific characters.\n"
        "2. MOTION CONTINUITY: These scenes are strictly sequential! If characters are 'running forward' in Scene 1, they should maintain logical physical momentum in Scene 2. Ensure smooth camera transitions between cuts.\n"
        "3. FOCUS ON ACTION: Describe HOW the camera moves (e.g., 'slow pan right', 'cinematic tracking shot') and WHAT animates (e.g., 'flickering lights', 'hair blowing in the wind', 'rain falling').\n"
        f"4. MANDATORY STYLE: You MUST start every single prompt with this exact style phrase: '{video_style_text}'.\n\n"
        f"=== BATCH REQUEST ({len(chunks_batch)} SEQUENTIAL SCENES) ===\n"
        f"{batch_text}"
        "INSTRUCTION: Write the generic video animation prompt for each scene based on the IMAGE DESCRIPTION. Focus strictly on continuous visual movement and camera action.\n"
        "OUTPUT FORMAT: Return ONLY a valid JSON array of strings. Example: [\"[Style] Five women run through a dark street, camera tracks backward\", \"[Style] The group stops at a door, sparks fly, slow zoom in\"]. Do not add any conversational text."
    )

    # ИСПОЛЬЗУЕМ FOR: Строго 15 попыток
    for attempts in range(1, 16):
        key = get_gemini_key()
        if not key:
            time.sleep(2)
            continue
            
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={key}"
        
        try:
            r = requests.post(url, json={"contents": [{"parts": [{"text": sys_prompt}]}]}, proxies=proxies, timeout=(5, 90))
            
            if r.status_code == 429:
                print(f"   ⏳ VID 429 | ", end='', flush=True)
                time.sleep(5)
                continue
            if r.status_code != 200:
                print(f"   ❌ VID {r.status_code} | ", end='', flush=True)
                time.sleep(3)
                continue

            res_json = r.json()
            if "candidates" in res_json and res_json["candidates"]:
                raw_text = res_json["candidates"][0]["content"]["parts"][0]["text"]
                
                match = re.search(r'\[.*\]', raw_text, re.DOTALL)
                if match:
                    clean_json = match.group(0)
                    try:
                        results = json.loads(clean_json)
                        if isinstance(results, list) and len(results) == len(chunks_batch):
                            return results
                        else:
                            print(f"⚠️ VID Mismatch | ", end='', flush=True)
                    except:
                        print(f"⚠️ VID JSON Error | ", end='', flush=True)
                else:
                    print(f"⚠️ VID No JSON array found | ", end='', flush=True)
            else:
                print("⚠️ VID Empty | ", end='', flush=True)

        except Exception as e:
            print(f"🔥 VID Fail ({type(e).__name__}) | ", end='', flush=True)
            
        time.sleep(3)
            
    print("\n   🚨 Гугл заблокировал запросы. Ставлю базовые видео-промпты.")
    return [f"{video_style_text} subtle cinematic motion"] * len(chunks_batch)


def worker_prompts(q, ctx, all_chunks, sub_keys, sc_keys, video_style_text):
    while True:
        try: task = q.get_nowait()
        except Empty: break
        idx = task
        text = all_chunks[idx]
        prev_text = all_chunks[idx-1] if idx > 0 else "Start"
        
        print(f"[Prompt {idx+1}] 🧠 Анализ сцены и действия...")
        
        # 1. Image Prompt
        p_img = generate_prompt_strict(text, prev_text, ctx, sub_keys, sc_keys)
        
        # 2. Video Prompt
        # Мы не дергаем Gemini, а просто берем стиль. Это ускорит процесс в 10 раз.
        final_vid = f"{video_style_text_for_prompts}, slow cinematic motion"

        with prompts_lock: 
            prompts_storage[idx] = p_img
            video_prompts_storage[idx] = final_video_prompt
            
        q.task_done()

# ─────────────────────────────────────────────────────────────────────────────
#                 БЛОК 3: ГЕНЕРАЦИЯ (WHISK / IMAGEFX)
# ─────────────────────────────────────────────────────────────────────────────
COOKIES = {}
def load_cookies_from_file():
    cookies_dict = {}
    if not os.path.exists(COOKIES_FILE): return cookies_dict
    try:
        with open(COOKIES_FILE, "r", encoding="utf-8") as f: raw_data = f.read().strip()
        raw_data = raw_data.replace('"', '').replace("'", "")
        if raw_data:
            pairs = raw_data.split(';')
            for pair in pairs:
                if '=' in pair:
                    key, value = pair.split('=', 1)
                    cookies_dict[key.strip()] = value.strip()
    except: pass
    return cookies_dict

def get_token_automatically():
    print("⏳ Получение токена ImageFX...")
    url = "https://labs.google/fx/tools/image-fx"
    headers = {"User-Agent": "Mozilla/5.0...","Accept": "text/html..."}
    try:
        response = requests.get(url, headers=headers, cookies=COOKIES, verify=False, timeout=15)
        match = re.search(r'(ya29\.[a-zA-Z0-9_-]+)', response.text)
        return match.group(1) if match else None
    except: return None

class WhiskBot:
    def __init__(self, auth_token):
        self.session_id = f";{int(time.time() * 1000)}"
        self.workflow_id = "4a308a63-405e-454f-a9f0-bc90f9e593e5"
        self.headers = {'authorization': f'Bearer {auth_token}', 'content-type': 'application/json', 'origin': 'https://labs.google'}

    def file_to_b64(self, path):
        with open(path, "rb") as f: return f"data:image/jpeg;base64,{base64.b64encode(f.read()).decode('utf-8')}"

    def upload(self, path, cat):
        if not path or not os.path.exists(path): return None
        url = 'https://labs.google/fx/api/trpc/backbone.uploadImage'
        payload = {"json": {"clientContext": {"workflowId": self.workflow_id, "sessionId": self.session_id}, "uploadMediaInput": {"mediaCategory": cat, "rawBytes": self.file_to_b64(path)}}}
        try:
            r = requests.post(url, headers=self.headers, cookies=COOKIES, json=payload, verify=False, timeout=40)
            if r.status_code == 200: 
                return r.json().get('result', {}).get('data', {}).get('json', {}).get('result', {}).get('uploadMediaGenerationId')
        except: pass
        return None

    def run_recipe(self, text, inputs, ratio, model, seed):
        url = 'https://aisandbox-pa.googleapis.com/v1/whisk:runImageRecipe'
        actual_model = "R2I" if inputs else model
        payload = {"clientContext": {"workflowId": self.workflow_id, "tool": "BACKBONE", "sessionId": self.session_id}, "imageModelSettings": {"imageModel": actual_model, "aspectRatio": ratio}, "seed": seed, "userInstruction": text, "recipeMediaInputs": inputs if inputs else []}
        try:
            resp = requests.post(url, headers=self.headers, cookies=COOKIES, json=payload, verify=False, timeout=60)
            if resp.status_code == 200: return resp.json()
        except: pass
        return None

def get_image_style_text_from_folder():
    if os.path.exists(STYLES_DIRECTORY):
        for f in os.listdir(STYLES_DIRECTORY):
            if f.endswith(".txt"):
                try:
                    with open(os.path.join(STYLES_DIRECTORY, f), "r", encoding="utf-8") as file:
                        return file.read().strip().replace("\n", ", ")
                except: pass
    return ""

def get_video_style_text_from_root():
    if os.path.exists(VIDEO_STYLE_FILE):
        try:
            with open(VIDEO_STYLE_FILE, "r", encoding="utf-8") as f:
                return f.read().strip().replace("\n", ", ")
        except: pass
    return "Cinematic, slow motion"

def process_single_asset(task_data, is_scene=False):
    name, desc, auth_token = task_data
    folder = SCENES_DIRECTORY if is_scene else SUBJECTS_DIRECTORY
    jpg_path = os.path.join(folder, f"{name}.jpg")
    
    if os.path.exists(jpg_path) and os.path.getsize(jpg_path) > 1000: 
        print(f"   👍 Уже есть: {name}")
        return

    bot = WhiskBot(auth_token)
    
    # 📌 ШАГ А: Читаем твой стиль из папки styles
    global_style = get_image_style_text_from_folder()

    media_inputs = []
    style_ref_path = None
    if os.path.exists(STYLES_DIRECTORY):
        for f in os.listdir(STYLES_DIRECTORY):
            if f.lower().endswith(('.jpg', '.jpeg', '.png')):
                style_ref_path = os.path.join(STYLES_DIRECTORY, f)
                break
    
    if not style_ref_path: 
        check_list = [os.path.join(BASE_DIR, REALISM_REFERENCE), os.path.join(BASE_DIR, DEFAULT_STYLE), os.path.join(BASE_DIR, DEFAULT_SUBJECT)]
        for p in check_list:
             if os.path.exists(p): style_ref_path = p; break

    if style_ref_path:
        mid = bot.upload(style_ref_path, "MEDIA_CATEGORY_STYLE")
        if mid: media_inputs = [{"mediaInput": {"mediaCategory": "MEDIA_CATEGORY_STYLE", "mediaGenerationId": mid}}]

    # 📌 ШАГ В: Приклеиваем стиль В НАЧАЛО промпта
    if is_scene:
        prompt = f"{global_style}, Location {name}, {desc}, NO PEOPLE" if global_style else f"Location {name}, {desc}, NO PEOPLE"
        ratio = "IMAGE_ASPECT_RATIO_LANDSCAPE"
    else:
        prompt = f"{global_style}, Character design of {name}, {desc}, neutral background" if global_style else f"Character design of {name}, {desc}, neutral background"
        ratio = "IMAGE_ASPECT_RATIO_PORTRAIT"

    print(f"   🖌️ Generating Asset: {name}...")

    # Отправка в ImageFX
    for i in range(3):
        res = bot.run_recipe(prompt, media_inputs, ratio, MODEL_NAME_IMG, random.randint(1, 1000000))
        if res and "imagePanels" in res:
            try:
                 with open(jpg_path, 'wb') as f: f.write(base64.b64decode(res["imagePanels"][0]["generatedImages"][0]["encodedImage"]))
                 print(f"   ✅ Готово: {name}")
                 return
            except: pass
        time.sleep(2)
    print(f"   ❌ Ошибка генерации ассета: {name}")

def worker_asset_gen_multithreaded(auth_token, is_scene=False):
    folder = SCENES_DIRECTORY if is_scene else SUBJECTS_DIRECTORY
    if not os.path.exists(folder): return
    tasks = []
    for f in os.listdir(folder):
        if f.endswith(".txt"):
            with open(os.path.join(folder, f), "r", encoding="utf-8") as tf:
                tasks.append((os.path.splitext(f)[0], tf.read().strip(), auth_token))
    
    if not tasks: return

    with ThreadPoolExecutor(max_workers=DEFAULT_THREADS) as pool:
        for t in tasks: pool.submit(process_single_asset, t, is_scene)

def preload_all_assets(auth_token):
    print("\n📦 [CACHE] Загрузка ассетов на сервер...")
    cache = {'subjects': {}, 'scenes': {}, 'styles': {}, 'realism': None}
    bot = WhiskBot(auth_token)
    
    # Герои
    if os.path.exists(SUBJECTS_DIRECTORY):
        for f in os.listdir(SUBJECTS_DIRECTORY):
            if f.lower().endswith(('.jpg', '.jpeg')):
                mid = bot.upload(os.path.join(SUBJECTS_DIRECTORY, f), "MEDIA_CATEGORY_SUBJECT")
                if mid: cache['subjects'][f.lower().replace(".jpg","")] = mid
    
    # Сцены
    if os.path.exists(SCENES_DIRECTORY):
        for f in os.listdir(SCENES_DIRECTORY):
            if f.lower().endswith(('.jpg', '.jpeg')):
                mid = bot.upload(os.path.join(SCENES_DIRECTORY, f), "MEDIA_CATEGORY_SUBJECT")
                if mid: cache['scenes'][f.lower().replace(".jpg","")] = mid

    # Стиль
    if os.path.exists(STYLES_DIRECTORY):
        for f in os.listdir(STYLES_DIRECTORY):
             if f.lower().endswith(('.jpg', '.jpeg')):
                mid = bot.upload(os.path.join(STYLES_DIRECTORY, f), "MEDIA_CATEGORY_STYLE")
                if mid: cache['styles']['default'] = mid; break
                
    print(f"✅ Кэш: {len(cache['subjects'])} героев, {len(cache['scenes'])} сцен.")
    return cache

def emergency_rewrite_prompt(bad_prompt):
    """Умный рерайт промпта: сохраняет смысл, но убирает 'жесть' для обхода цензуры."""
    key = get_gemini_key()
    if not key: return bad_prompt
    
    style_text = get_image_style_text_from_folder()
    style_instruction = f"MUST maintain this exact visual style: {style_text}" if style_text else "Keep the visual style neutral."
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={key}"
    sys_prompt = (
        f"Rewrite this image generation prompt to BYPASS strict AI safety filters while KEEPING THE CORE MEANING:\n"
        f"'{bad_prompt}'\n\n"
        f"CRITICAL RULES:\n"
        f"1. REMOVE all explicit mentions of fire, explosions, blood, violence, weapons, or direct harm to humans.\n"
        f"2. REPLACE them with atmospheric tension: use 'bright orange glow' instead of fire, 'heavy fog/haze' instead of smoke, 'shocked expressions' instead of pain/screaming.\n"
        f"3. Keep the characters and the location, but make the scene look like a dramatic movie still without explicit tragedy.\n"
        f"4. Keep it highly visual and under 30 words.\n"
        f"5. {style_instruction}"
    )
    
    try:
        r = requests.post(url, json={"contents": [{"parts": [{"text": sys_prompt}]}]}, proxies=proxies, timeout=10)
        if r.status_code == 200:
            new_text = r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
            return new_text.replace("\n", " ").replace('"', '')
    except: pass
    return bad_prompt

def worker_image_gen(task_queue, session_dir, auth_token, asset_registry):
    local_bot = WhiskBot(auth_token)
    reg_subjects = asset_registry.get('subjects', {})
    reg_scenes = asset_registry.get('scenes', {})
    reg_styles = asset_registry.get('styles', {})
    image_style_text = get_image_style_text_from_folder()

    def get_smart_inputs_lazy(text_prompt):
        inputs = []
        asset_names_debug = []
        used_mid_check = set()
        low_text = text_prompt.lower()
        
        # Хард-лимит ImageFX = 3 файла (чтобы не падал с ошибкой)
        MAX_INPUTS = 3 
        
        # 1. ОБЯЗАТЕЛЬНЫЙ СТИЛЬ (Занимает слот №1)
        if 'default' in reg_styles:
            path = reg_styles['default']
            mid = get_lazy_asset_id(local_bot, path, "MEDIA_CATEGORY_STYLE")
            if mid:
                inputs.append({"mediaInput": {"mediaCategory": "MEDIA_CATEGORY_STYLE", "mediaGenerationId": mid}})
                used_mid_check.add(mid)
                asset_names_debug.append("🎨Style")

        # 2. ГЕРОИ (Занимают оставшиеся слоты, но не превышают лимит)
        for name, path in reg_subjects.items():
            if len(inputs) >= MAX_INPUTS: 
                break # Если 3 файла уже загружено - жестко стопаем
                
            clean_name = name.lower().replace("the", "").strip()
            # Проверяем, упоминается ли герой в промпте
            if clean_name in low_text:
                mid = get_lazy_asset_id(local_bot, path, "MEDIA_CATEGORY_SUBJECT")
                if mid and mid not in used_mid_check:
                    inputs.append({"mediaInput": {"mediaCategory": "MEDIA_CATEGORY_SUBJECT", "mediaGenerationId": mid}})
                    asset_names_debug.append(f"👤{name}")
                    used_mid_check.add(mid)
        
        # 3. ЛОКАЦИИ (Добавляем, ТОЛЬКО если остались свободные слоты после героев)
        for name, path in reg_scenes.items():
            if len(inputs) >= MAX_INPUTS: 
                break
                
            clean_name = name.lower().replace("the", "").strip()
            if clean_name in low_text:
                mid = get_lazy_asset_id(local_bot, path, "MEDIA_CATEGORY_SUBJECT")
                if mid and mid not in used_mid_check:
                    inputs.append({"mediaInput": {"mediaCategory": "MEDIA_CATEGORY_SUBJECT", "mediaGenerationId": mid}})
                    asset_names_debug.append(f"🏠{name}")
                    used_mid_check.add(mid)
        
        # 4. ФОЛЛБЭК: Если героев в тексте не нашли, но слоты есть — берём первого героя из базы
        if len(inputs) < MAX_INPUTS and reg_subjects and not any("👤" in x for x in asset_names_debug):
            first_name = list(reg_subjects.keys())[0]
            first_path = reg_subjects[first_name]
            mid = get_lazy_asset_id(local_bot, first_path, "MEDIA_CATEGORY_SUBJECT")
            if mid and mid not in used_mid_check:
                inputs.append({"mediaInput": {"mediaCategory": "MEDIA_CATEGORY_SUBJECT", "mediaGenerationId": mid}})
                asset_names_debug.append(f"👤{first_name}(fb)")
                used_mid_check.add(mid)
        
        return inputs, asset_names_debug
    while True:
        try: task = task_queue.get_nowait()
        except Empty: break
        idx, original_prompt_text = task
        
        save_path = os.path.join(session_dir, "images", f"{idx+1:04d}.jpg")
        if os.path.exists(save_path) and os.path.getsize(save_path) > 1000: 
            task_queue.task_done(); continue

        current_prompt = original_prompt_text
        
        # ВСЕГДА собираем инпуты по ОРИГИНАЛЬНОМУ тексту, чтобы не потерять референсы
        inputs_list, refs_names = get_smart_inputs_lazy(original_prompt_text)
        refs_str = ", ".join(refs_names) if refs_names else "NO REF"
        
        for attempt in range(1, 7): # Попытки от 1 до 6
            # --- ЛОГИКА 2-2-2 ---
            if attempt == 3:
                print(f"   🔄 [Img {idx+1}] Делаю умный рерайт промпта...")
                current_prompt = emergency_rewrite_prompt(original_prompt_text)
            
            if attempt >= 5:
                print(f"   🚨 [Img {idx+1}] Safe Mode (попытка {attempt}). Отключаю референсы героев.")
                current_prompt = "Simple minimal illustration, cinematic lighting, neutral background"
                # В Safe Mode оставляем только Стиль (если он был), убираем героев, чтобы точно сгенерировалось
                inputs_list = [inp for inp in inputs_list if inp['mediaInput']['mediaCategory'] == "MEDIA_CATEGORY_STYLE"]
                refs_str = "SAFE_MODE_ONLY_STYLE"

            final_text = f"{image_style_text}, {current_prompt}" if image_style_text else current_prompt
            print(f"🚀 [Img {idx+1}] Try {attempt} | Refs: {refs_str}")

            try:
                res = local_bot.run_recipe(final_text, inputs_list, ASPECT_RATIO, MODEL_NAME_IMG, random.randint(1, 9999999))
                if res and "imagePanels" in res:
                    img_data = base64.b64decode(res["imagePanels"][0]["generatedImages"][0]["encodedImage"])
                    with open(save_path, 'wb') as f: f.write(img_data)
                    with prompts_lock: prompts_storage[idx] = final_text 
                    print(f"   ✅ [Img {idx+1}] Saved (Try {attempt})!")
                    break 
                else:
                    print(f"   ❌ [Img {idx+1}] Ошибка ImageFX.")
                    time.sleep(2)
            except Exception as e:
                print(f"   ⚠️ [Img {idx+1}] Сеть: {e}")
                time.sleep(5)
                
        task_queue.task_done()

def run_image_generation_process(session_dir, target_indices=None):
    global COOKIES
    COOKIES = load_cookies_from_file()
    auth_token = get_token_automatically()
    if not auth_token: auth_token = input("⚠️ Введите токен вручную: ").strip()

    # 1. Генерируем ассеты (текст -> картинки героев), если их нет
    if target_indices is None:
        worker_asset_gen_multithreaded(auth_token, False) 
        worker_asset_gen_multithreaded(auth_token, True)
        if REVIEW_ASSETS:
            while True:
                print(f"\n✋ [PAUSE] ПРОВЕРКА АССЕТОВ...")
                asset_list = []
                if os.path.exists(SUBJECTS_DIRECTORY):
                    for f in sorted(os.listdir(SUBJECTS_DIRECTORY)):
                        if f.lower().endswith(('.jpg', '.jpeg', '.png')):
                            asset_list.append(("SUBJECT", os.path.join(SUBJECTS_DIRECTORY, f), f))
                if os.path.exists(SCENES_DIRECTORY):
                    for f in sorted(os.listdir(SCENES_DIRECTORY)):
                        if f.lower().endswith(('.jpg', '.jpeg', '.png')):
                            asset_list.append(("SCENE", os.path.join(SCENES_DIRECTORY, f), f))
                
                if not asset_list: break
                for i, (atype, apath, aname) in enumerate(asset_list):
                    print(f"   {i+1}. [{atype}] {aname}")
                    
                ans = input("\n   Введи номера для перегенерации (или ENTER для продолжения): ").strip()
                if not ans: break
                    
                nums = parse_user_input(ans)
                if nums:
                    print(f"   🗑️ Удаляю ассеты: {nums}")
                    re_subj = False; re_scene = False
                    for n in nums:
                        idx = n - 1
                        if 0 <= idx < len(asset_list):
                            atype, apath, aname = asset_list[idx]
                            if os.path.exists(apath): os.remove(apath)
                            if atype == "SUBJECT": re_subj = True
                            if atype == "SCENE": re_scene = True
                    if re_subj: worker_asset_gen_multithreaded(auth_token, False)
                    if re_scene: worker_asset_gen_multithreaded(auth_token, True)

    # 2. СОБИРАЕМ РЕЕСТР ФАЙЛОВ (БЕЗ ЗАГРУЗКИ НА СЕРВЕР!)
    # Мы просто запоминаем, где лежат файлы, чтобы воркеры их нашли.
    asset_registry = {'subjects': {}, 'scenes': {}, 'styles': {}}
    
    # Собираем Героев
    if os.path.exists(SUBJECTS_DIRECTORY):
        for f in os.listdir(SUBJECTS_DIRECTORY):
            if f.lower().endswith(('.jpg', '.jpeg', '.png')):
                asset_registry['subjects'][f.lower().replace(".jpg","")] = os.path.join(SUBJECTS_DIRECTORY, f)
    
    # Собираем Сцены
    if os.path.exists(SCENES_DIRECTORY):
        for f in os.listdir(SCENES_DIRECTORY):
            if f.lower().endswith(('.jpg', '.jpeg', '.png')):
                asset_registry['scenes'][f.lower().replace(".jpg","")] = os.path.join(SCENES_DIRECTORY, f)

    # Собираем Стиль
    if os.path.exists(STYLES_DIRECTORY):
        for f in os.listdir(STYLES_DIRECTORY):
             if f.lower().endswith(('.jpg', '.jpeg', '.png')):
                asset_registry['styles']['default'] = os.path.join(STYLES_DIRECTORY, f)
                break

    print(f"📂 [Smart Setup] Найдено: {len(asset_registry['subjects'])} героев, {len(asset_registry['scenes'])} сцен.")
    print("🚀 Старт генерации кадров (с ленивой подгрузкой)...")

    # 3. Запуск воркеров (с циклом умной проверки)
    session_prompts = os.path.join(session_dir, "prompts.txt")
    if not os.path.exists(session_prompts): return

    prompts = []
    with open(session_prompts, "r", encoding="utf-8") as f:
        prompts = [line.strip() for line in f if line.strip()]

    while True:
        q = Queue()
        for idx, p in enumerate(prompts):
            if target_indices is not None and idx not in target_indices: continue
            q.put((idx, p))

        with ThreadPoolExecutor(max_workers=DEFAULT_THREADS) as pool:
            for _ in range(DEFAULT_THREADS): 
                pool.submit(worker_image_gen, q, session_dir, auth_token, asset_registry)
        q.join()

    

def main(force_session_id=None):
    print(f"=== VOICEPRO ULTIMATE v30 (SMART RESUME) ===")
    if not os.path.exists(INPUT_TEXT_FILE): print("❌ Нет script.txt"); return
        
    # ИСПОЛЬЗУЕМ НОВУЮ ФУНКЦИЮ
    curr_sess = get_or_create_session(force_session_id)
    session_id = os.path.basename(curr_sess)
    
    with open(INPUT_TEXT_FILE, "r", encoding="utf-8") as f: text = f.read()
    
    # 🌟 ЧИТАЕМ ТУМБЛЕР ИЗ CONFIG.PY
    split_mode = getattr(CFG, 'SCENE_SPLIT_MODE', 'STANDARD')
    
    if split_mode == "DYNAMIC":
        chunks, audio_tasks = prepare_smart_chunks(text)
    else:
        # Стандартный режим (1 к 1)
        chunks = split_text_into_smart_chunks(text, SENTENCES_PER_CHUNK)
        audio_tasks = [(c, True) for c in chunks] # Все аудио реальные, никаких нулей
        print(f"\n--- [СТАНДАРТ] Нарезка по {SENTENCES_PER_CHUNK} предл. ({len(chunks)} кадров) ---")
    
    # 1. АУДИО
    if GENERATE_AUDIO:
        audio_dir = os.path.join(curr_sess, "audio") 
        while True:
            q = Queue()
            for i, task in enumerate(audio_tasks): q.put((i, task[0], task[1], 0))
            with ThreadPoolExecutor(max_workers=DEFAULT_THREADS) as pool:
                for _ in range(DEFAULT_THREADS): pool.submit(worker_audio, q, audio_dir)
            q.join()
            
            if getattr(CFG, 'REVIEW_AUDIO', False):
                print(f"\n✋ [PAUSE] ОЗВУЧКА ГОТОВА.")
                ans = input("   Введи номера для перегенерации (напр. 1 3-5) или ENTER: ").strip()
                if not ans: break
                nums = parse_user_input(ans)
                if nums:
                    print(f"   🗑️ Удаляю аудио: {nums}")
                    for n in nums:
                        p = os.path.join(audio_dir, f"{n:04d}.mp3") # И тут тоже исправил на audio_dir
                        if os.path.exists(p): os.remove(p)
                    continue # Перезапуск генерации удаленных аудио
            break
    
    # 2. АНАЛИЗ ТЕКСТА (ГЕРОИ)
    if get_gemini_key():
        # Сначала читаем твой стиль из папки!
        style_text = get_image_style_text_from_folder()
        
        if GENERATE_HEROES_TEXT: save_subjects(create_subjects(text, style_text))
        if GENERATE_SCENES_TEXT: save_scenes(create_scenes(text, style_text))
    else:
        print("❌ ОШИБКА: api_keys.txt пуст!")
    
# 3. ПРОМПТЫ (СУПЕР-УМНАЯ ПРОВЕРКА)
    print("\n--- 3. ГЕНЕРАЦИЯ ПРОМПТОВ ---")
    
    # ВОТ ЭТИ ПЕРЕМЕННЫЕ МЫ ЗАБЫЛИ ДОБАВИТЬ В ПРОШЛЫЙ РАЗ:
    session_prompts_path = os.path.join(curr_sess, "prompts.txt")
    session_video_prompts_path = os.path.join(curr_sess, "video_prompts.txt")
    ctx = text[:2000] # Контекст истории для Gemini
    subject_keys = list(load_subjects().keys())
    scene_keys = [os.path.splitext(f)[0] for f in os.listdir(SCENES_DIRECTORY) if f.endswith(".txt")] if os.path.exists(SCENES_DIRECTORY) else []

    # 1. УМНАЯ ЗАГРУЗКА (SMART RESUME) - читаем то, что уже сгенерировано
    if os.path.exists(session_prompts_path):
        with open(session_prompts_path, "r", encoding="utf-8") as f:
            for i, line in enumerate(f):
                line = line.strip()
                # Берем промпт, только если это не ошибка и не заглушка
                if line and line != "Error" and "Cinematic highly detailed" not in line:
                    prompts_storage[i] = line

    if os.path.exists(session_video_prompts_path):
        with open(session_video_prompts_path, "r", encoding="utf-8") as f:
            for i, line in enumerate(f):
                line = line.strip()
                if line and line != "Error" and "cinematic motion" not in line:
                    video_prompts_storage[i] = line

    # Определяем стиль видео
    video_style_text_for_prompts = get_video_style_text_from_root()
    print(f"🎥 Video Style: {video_style_text_for_prompts}")
    
    print("🚀 Запуск пакетной генерации (по 10 сцен)...")
    batch_size = 10
    
    for i in range(0, len(chunks), batch_size):
        batch_indices = list(range(i, min(i + batch_size, len(chunks))))
        
        # 2. ПРОВЕРКА: Готова ли уже эта пачка?
        already_done = True
        for idx in batch_indices:
            if idx not in prompts_storage or idx not in video_prompts_storage:
                already_done = False
                break
                
        if already_done:
            print(f"\n📦 Пачка {batch_indices[0]+1}-{batch_indices[-1]+1} УЖЕ ГОТОВА. Пропускаю! ⏭️")
            continue

        print(f"\n📦 Обработка пачки {batch_indices[0]+1}-{batch_indices[-1]+1}...")
        current_batch = [chunks[idx] for idx in batch_indices]
        prev_batch = [chunks[idx-1] if idx > 0 else "Beginning of story." for idx in batch_indices]
        
        # Генерируем промпты картинок (теперь передаем style_text)
        img_prompts = generate_prompts_batch(current_batch, prev_batch, ctx, subject_keys, scene_keys, style_text)
        
        # Генерируем промпты видео
        vid_prompts = generate_video_prompts_batch(
            current_batch, prev_batch, img_prompts, video_style_text_for_prompts
        )
        
        # Сохраняем в память
        for local_idx, (p_img, p_vid) in enumerate(zip(img_prompts, vid_prompts)):
            global_idx = batch_indices[local_idx]
            prompts_storage[global_idx] = p_img
            video_prompts_storage[global_idx] = p_vid
            print(f"   ✅ Сцена {global_idx+1} готова.")
            
        # 3. МГНОВЕННОЕ СОХРАНЕНИЕ В ФАЙЛ ПОСЛЕ КАЖДОЙ ПАЧКИ
        with open(session_prompts_path, "w", encoding="utf-8") as f:
            for j in range(len(chunks)): f.write(f"{prompts_storage.get(j, 'Error')}\n")
        
        with open(session_video_prompts_path, "w", encoding="utf-8") as f:
            for j in range(len(chunks)): f.write(f"{video_prompts_storage.get(j, 'Error')}\n")

    print(f"✅ Промпты сохранены:\n   📄 IMG: {session_prompts_path}\n   🎥 VID: {session_video_prompts_path}")
    
    # 4. ГЕНЕРАЦИЯ КАРТИНОК
    run_image_generation_process(curr_sess)

    # 5. Возврат ID сессии для Main.py
    return session_id

if __name__ == "__main__":
    main()