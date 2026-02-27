"""
╔══════════════════════════════════════════════════════════╗
║          ⚙️ ГЛАВНЫЙ ПУЛЬТ НАСТРОЕК (config.py)          ║
║     Все три скрипта читают настройки ОТСЮДА.             ║
║     Меняй тумблеры тут — и всё подхватится.              ║
╚══════════════════════════════════════════════════════════╝
"""

# ─────────────────────────────────────────────────────────
#  📂 ОБЩИЕ ПУТИ
# ─────────────────────────────────────────────────────────
RESULT_BASE = "Result_Final"   # Базовая папка для всех сессий

# ─────────────────────────────────────────────────────────
#  🎬 РЕЖИМ ФИНАЛЬНОЙ СКЛЕЙКИ (ТУМБЛЕР)
# ─────────────────────────────────────────────────────────
# "IMAGES" — итоговое видео только из картинок (картинка + аудио)
# "VIDEOS" — итоговое видео только из видео Grok (видео + аудио)
# "RANDOM" — для каждого кадра рандомно: картинка или видео
RENDER_MODE = "IMAGES"

# Шанс (в процентах) выбрать ВИДЕО в режиме RANDOM. 
# Например, 70 означает 70% видео и 30% картинок.
RANDOM_VIDEO_PERCENT = 70

# ─────────────────────────────────────────────────────────
#  ✂️ НАРЕЗКА ТЕКСТА
# ─────────────────────────────────────────────────────────
# "STANDARD" — 1 картинка на 1 кусок текста (строго по SENTENCES_PER_CHUNK)
# "DYNAMIC"  — 1 озвучка на предложение, но внутри него МНОГО меняющихся картинок
SCENE_SPLIT_MODE = "DYNAMIC"

SENTENCES_PER_CHUNK = 1    # Работает только если SCENE_SPLIT_MODE = "STANDARD"
# ─────────────────────────────────────────────────────────
#  🎭 ГЕНЕРАЦИЯ — ЧТО ВКЛЮЧИТЬ
# ─────────────────────────────────────────────────────────
GENERATE_AUDIO         = True   # Озвучка через ElevenLabs
GENERATE_HEROES_TEXT   = True   # Описание героев через Gemini
GENERATE_HEROES_IMAGES = True   # Портреты героев через ImageFX
GENERATE_SCENES_TEXT   = True   # Описание локаций через Gemini
GENERATE_SCENES_IMAGES = True   # Фоны локаций через ImageFX

# ─────────────────────────────────────────────────────────
#  🚀 ПОТОКИ (ПАРАЛЛЕЛЬНОСТЬ)
# ─────────────────────────────────────────────────────────
THREADS_IMAGES = 5     # Потоки для генерации картинок (el11_15)
THREADS_GROK   = 10     # Потоки для генерации видео (Grok8)

# ─────────────────────────────────────────────────────────
#  📐 ФОРМАТ ВИДЕО
# ─────────────────────────────────────────────────────────
USER_RATIO = "16:9"        # "16:9" или "9:16"
FPS = 30                   # Кадров в секунду
VIDEO_WIDTH = 1920         # Ширина итогового видео
VIDEO_HEIGHT = 1080        # Высота итогового видео

# ─────────────────────────────────────────────────────────
#  🖼️ НЕЙРОСЕТЬ ДЛЯ КАРТИНОК
# ─────────────────────────────────────────────────────────
MODEL_NAME_IMG = "IMAGEN_4"
USER_SEED = None           # None = случайный

# ─────────────────────────────────────────────────────────
#  🎬 ПЕРЕХОДЫ И ЭФФЕКТЫ (МОНТАЖ)
# ─────────────────────────────────────────────────────────
TRANSITION_MODE = "NONE"       # "NONE", "FADE_BLACK", "CROSSFADE"
TRANSITION_DURATION = 0.0      # Длительность перехода (сек)
TRIM_START = 0.5               # Обрезка начала видео Grok (мусор)

# ─────────────────────────────────────────────────────────
#  🛡️ РУЧНАЯ ПРОВЕРКА (УМНЫЕ СТОПЫ)
# ─────────────────────────────────────────────────────────
# Введи нужные номера через пробел (например: 1 3 5-7), чтобы переделать кадры.
# Оставь пустым и нажми ENTER, чтобы пойти дальше.
REVIEW_AUDIO   = True   # Пауза после генерации озвучки
REVIEW_ASSETS  = True   # Пауза после генерации героев/сцен
REVIEW_IMAGES  = True   # Пауза после генерации картинок (кадров)
REVIEW_VIDEOS  = True   # Пауза после генерации видео в Grok (перед склейкой)

# ─────────────────────────────────────────────────────────
#  📂 ФАЙЛЫ ПО УМОЛЧАНИЮ (заглушки)
# ─────────────────────────────────────────────────────────
DEFAULT_SUBJECT    = "face.jpg"
DEFAULT_STYLE      = "style.jpeg"
DEFAULT_SCENE      = "snene.jpg"
REALISM_REFERENCE  = "realism.jpg"

# ─────────────────────────────────────────────────────────
#  📂 ПАПКИ АССЕТОВ (Whisk / ImageFX)
# ─────────────────────────────────────────────────────────
# Эти папки создаются автоматически.
# subjects/ — описания и портреты героев
# scenes/   — описания и фоны локаций
# styles/   — стиль картинок (.txt + .jpg)
# Внутри каждой создаётся подпапка с номером сессии (subjects/1, subjects/2...)
SUBJECTS_DIR_NAME  = "subjects"
SCENES_DIR_NAME    = "scenes"
STYLES_DIR_NAME    = "styles"

# ─────────────────────────────────────────────────────────
#  🎤 ОЗВУЧКА (ElevenLabs)
# ─────────────────────────────────────────────────────────
VOICE_ID           = "gJEfHTTiifXEDmO687lC"
VOICE_SIMILARITY   = 0.75
VOICE_STABILITY    = 0.50
VOICE_SPEED        = 1.0
SILENCE_SEC        = 0.5       # Тишина в конце каждого аудио

# ─────────────────────────────────────────────────────────
#  🖼️ GEMINI
# ─────────────────────────────────────────────────────────
GEMINI_MODEL       = "gemini-2.5-flash"

# ─────────────────────────────────────────────────────────
#  🌍 PROXY
# ─────────────────────────────────────────────────────────
USE_PROXY              = True
PROXY_ROTATION_MODE    = "PORT"    # "PORT" или "API"
PROXY_LOGIN            = "YOUR_PROXY_PASSWORD_HERE"
PROXY_PASSWORD         = "YOUR_PROXY_PASSWORD_HERE"
PROXY_HOST             = "YOUR_PROXY_PASSWORD_HERE"

# ─────────────────────────────────────────────────────────
#  🧠 НАСТРОЙКИ ГЕНЕРАЦИИ ПРОМПТОВ (GEMINI SYSTEM PROMPTS)
# ─────────────────────────────────────────────────────────
# Здесь ты управляешь тем, КАК Gemini описывает картинки и видео.
# {subj} = список героев, {scene} = список локаций.

# ИНСТРУКЦИЯ ДЛЯ КАРТИНОК (Детальность, стиль, непрерывность + УМНАЯ ЦЕНЗУРА)
GEMINI_SYS_PROMPT_IMG = """
You are an expert storyboard artist and continuity director. 
TASK: Convert the text chunk into a RICH visual description (3-4 sentences) tailored for an image generation prompt.

CRITICAL RULES:
1. NO ABSTRACT CONCEPTS: If text says "he felt lonely", write: "A figure sitting alone in a vast empty dark room".
2. TRANSLATE METAPHORS: Turn words into visual storytelling elements.
3. STRICT CONTINUITY: These scenes are strictly sequential! Maintain the presence of characters from the previous scene unless the text explicitly says they left.
4. ASSETS: If characters {subj} or scenes {scene} are relevant, weave them naturally into the description.
5. STYLE INTEGRATION: Seamlessly blend the provided Visual Style into the description.
6. PG-13 SAFETY (CRITICAL): AI image generators block violence, fire, explosions, and tragedy. You MUST censor the visual description! Replace "fire/explosions" with "intense bright orange dramatic lighting". Replace "smoke" with "thick cinematic fog". Replace "pain/screaming" with "shocked, intense expressions". NEVER put people directly in fire or danger. Create atmospheric tension without explicit violence.
7. FORMAT: Output ONLY the description text. No "Here is the prompt".
"""

# ИНСТРУКЦИЯ ДЛЯ ВИДЕО (Движение, динамика, глаголы)
GEMINI_SYS_PROMPT_VID = """
You are a Cinematographer designing a shot for an AI Video Generator (like Grok Imagine).
TASK: Write a DETAILED video animation prompt based on the script text and the image description.

CRITICAL RULES:
1. FOCUS ON ACTION AND MOTION: The video must have visible movement. Never describe a static image.
2. TRANSLATE AUDIO TO MOTION: If script implies running, describe "fast camera tracking shot, wind blowing through hair, dust kicking up from feet".
3. CONNECTION TO AUDIO: The video will be synced to voiceover narration. The action you describe MUST match what the narrator is saying at this moment.
4. DESCRIBE THE FULL SCENE: Write 3-4 sentences covering: what the character does, how the camera moves, what happens in the background, and the mood/atmosphere.
5. USE CHARACTER NAMES: Always refer to characters by their exact names from the story.
6. CAMERA WORK: Include specific camera directions (slow zoom in, tracking shot, pan left, static wide shot, close-up, aerial view, etc.)
7. FORMAT: Output ONLY the video description. No labels, no "Video prompt:", just the description text.

EXAMPLE OUTPUT:
"Stick walks slowly down the empty neon-lit street, his shadow stretching long behind him. The camera tracks him from a low angle, revealing the towering buildings of the City of Lines above. Rain begins to fall as he stops and looks up, the camera slowly tilting upward to reveal the dark sky."
"""

# ─────────────────────────────────────────────────────────
#  🧠 ГЕНЕРАЦИЯ ГЕРОЕВ И СЦЕН (ОБНОВЛЕНО ДЛЯ ПАЙПЛАЙНА)
# ─────────────────────────────────────────────────────────

# Инструкция для ГЕРОЕВ (subjects).
GEMINI_SYS_PROMPT_SUBJECTS = """
Analyze this text:
{text}

TASK: List Main Characters.
CRITICAL RULES:
1. KEY REQUIREMENT: Output the Character Name in ENGLISH ONLY (e.g., use 'Stick' instead of 'Стик').
2. VISUALS: Provide a detailed physical description (face, clothes, accessories, body type, age).
3. ISOLATION: Describe the character on a neutral or white background. Focus on the person, not the surroundings.
4. If no names exist, invent one (e.g., 'Protagonist', 'Narrator').

FORMAT: 'EnglishName: Detailed visual description of the character...'
"""

# Инструкция для СЦЕН (scenes).
GEMINI_SYS_PROMPT_SCENES = """
Analyze text:
{text}

TASK: List Locations/Environments.
CRITICAL RULES:
1. KEY REQUIREMENT: Output the Location Name in ENGLISH ONLY (e.g., 'Bedroom', 'Office').
2. CONTENT: Describe the ENVIRONMENT ONLY. DO NOT include people or characters.
3. TYPE: Specify if it is INDOOR (walls, floor, furniture, windows) or OUTDOOR (sky, ground, buildings, weather).
4. DETAILS: Focus on lighting, textures (wood, concrete, metal), atmosphere, and geometry.
5. LENGTH: 2-3 sentences per location.

FORMAT: 'EnglishLocationName: Empty environment description, indoor/outdoor details, lighting, texture...'
"""