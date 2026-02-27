import subprocess
import os
import re
import glob
import random
import shutil

# ╔══════════════════════════════════════════════╗
# ║           ⚙️ НАСТРОЙКИ (ТУМБЛЕРЫ)           ║
# ╚══════════════════════════════════════════════╝

try:
    import config as CFG
    RESULT_BASE         = CFG.RESULT_BASE
    RENDER_MODE         = CFG.RENDER_MODE
    FPS                 = CFG.FPS
    TRIM_START          = CFG.TRIM_START
    VIDEO_WIDTH         = CFG.VIDEO_WIDTH
    VIDEO_HEIGHT        = CFG.VIDEO_HEIGHT
    TRANSITION_MODE     = CFG.TRANSITION_MODE
    TRANSITION_DURATION = CFG.TRANSITION_DURATION
    print("✅ [Монтаж] Настройки загружены из config.py")
except ImportError:
    print("⚠️ config.py не найден, используем встроенные настройки")
    RESULT_BASE = "Result_Final"
    RENDER_MODE = "RANDOM"
    FPS = 30
    TRIM_START = 0.5
    VIDEO_WIDTH = 1920
    VIDEO_HEIGHT = 1080
    TRANSITION_MODE = "NONE"
    TRANSITION_DURATION = 0.0
    RANDOM_VIDEO_PERCENT = 50

# -----------------

def get_duration(filename):
    """Получаем длительность файла в секундах"""
    try:
        cmd = [
            'ffprobe', '-v', 'error', '-show_entries', 'format=duration', 
            '-of', 'default=noprint_wrappers=1:nokey=1', filename
        ]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        return float(result.stdout.strip())
    except (ValueError, AttributeError, Exception):
        return None

def natural_sort_key(s):
    return [int(text) if text.isdigit() else text.lower() for text in re.split('([0-9]+)', s)]

def join_audios(audio_paths, output_path):
    """Склеивает несколько аудиофайлов в один"""
    if not audio_paths: return False
    if len(audio_paths) == 1:
        shutil.copy2(audio_paths[0], output_path)
        return True

    # Создаем список для ffmpeg
    list_path = output_path + ".txt"
    with open(list_path, "w", encoding="utf-8") as f:
        for ap in audio_paths:
            f.write(f"file '{os.path.abspath(ap)}'\n")
    
    # Склеиваем
    cmd = [
        'ffmpeg', '-y', '-f', 'concat', '-safe', '0', 
        '-i', list_path, '-c', 'copy', output_path
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
    
    try: os.remove(list_path)
    except: pass
    
    return os.path.exists(output_path)

def process_image_chunk(img_path, aud_path, output_path, aud_dur):
    """Создает видео из КАРТИНКИ + аудио."""
    scale = f"scale={VIDEO_WIDTH}:{VIDEO_HEIGHT}:force_original_aspect_ratio=decrease,pad={VIDEO_WIDTH}:{VIDEO_HEIGHT}:(ow-iw)/2:(oh-ih)/2,format=yuv420p"
    
    filters = scale
    if TRANSITION_MODE == "FADE_BLACK" and TRANSITION_DURATION > 0:
        filters += f",fade=t=in:st=0:d={TRANSITION_DURATION},fade=t=out:st={aud_dur-TRANSITION_DURATION}:d={TRANSITION_DURATION}"
    
    cmd = [
        'ffmpeg', '-y', '-v', 'error',
        '-loop', '1', '-i', img_path,
        '-i', aud_path,
        '-vf', filters,
        '-c:v', 'libx264', '-preset', 'medium', '-crf', '23', '-pix_fmt', 'yuv420p',
        '-c:a', 'aac', '-b:a', '192k', '-ac', '2', '-ar', '44100',
        '-t', str(aud_dur),
        '-r', str(FPS),
        output_path
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
    return os.path.exists(output_path)

def process_video_chunk(vid_path, aud_path, output_path, aud_dur):
    """Создает видео из ВИДЕО GROK + аудио (растягивает/обрезает)."""
    vid_dur = get_duration(vid_path)
    if not vid_dur: return False

    clean_vid_dur = vid_dur - TRIM_START
    if clean_vid_dur <= 0.1: clean_vid_dur = 0.1 # Защита от деления на ноль

    # Если аудио длиннее (или мы склеили несколько аудио) -> ЗАМЕДЛЯЕМ видео
    if aud_dur > clean_vid_dur:
        pts_factor = aud_dur / clean_vid_dur
        # Ограничим замедление, чтобы не зависало (макс x4)
        if pts_factor > 10.0: pts_factor = 10.0 
        
        filter_complex = f"[0:v]trim=start={TRIM_START},setpts=PTS-STARTPTS,setpts={pts_factor}*PTS,scale={VIDEO_WIDTH}:{VIDEO_HEIGHT}:force_original_aspect_ratio=decrease,pad={VIDEO_WIDTH}:{VIDEO_HEIGHT}:(ow-iw)/2:(oh-ih)/2,format=yuv420p[v]"

    # Если аудио короче -> ОБРЕЗАЕМ конец видео
    else:
        filter_complex = f"[0:v]trim=start={TRIM_START}:duration={aud_dur},setpts=PTS-STARTPTS,scale={VIDEO_WIDTH}:{VIDEO_HEIGHT}:force_original_aspect_ratio=decrease,pad={VIDEO_WIDTH}:{VIDEO_HEIGHT}:(ow-iw)/2:(oh-ih)/2,format=yuv420p[v]"

    cmd = [
        'ffmpeg', '-y',
        '-i', vid_path,
        '-i', aud_path,
        '-filter_complex', filter_complex,
        '-map', '[v]',
        '-map', '1:a',
        '-r', str(FPS),
        '-c:v', 'libx264', '-preset', 'medium', '-crf', '23', '-pix_fmt', 'yuv420p',
        '-c:a', 'aac', '-b:a', '192k', '-ac', '2', '-ar', '44100',
        output_path
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
    return os.path.exists(output_path)

def check_media_exists(base_name, images_dir, videos_dir, mode):
    """Проверяет, есть ли медиафайл для данного имени в заданном режиме"""
    img_path = os.path.join(images_dir, f"{base_name}.jpg")
    vid_path = os.path.join(videos_dir, f"{base_name}.mp4")
    
    # Альтернативные расширения картинок
    if not os.path.exists(img_path):
        for ext in ['.jpeg', '.png']:
            alt = os.path.join(images_dir, f"{base_name}{ext}")
            if os.path.exists(alt): img_path = alt; break

    has_img = os.path.exists(img_path) and os.path.getsize(img_path) > 1000
    has_vid = os.path.exists(vid_path) and os.path.getsize(vid_path) > 1000

    if mode == "IMAGES": return has_img
    if mode == "VIDEOS": return has_vid
    if mode == "RANDOM": return has_img or has_vid
    return False

def run_for_session(session_id):
    session_path = os.path.join(RESULT_BASE, str(session_id))
    if not os.path.exists(session_path):
        print(f"❌ Сессия {session_id} не найдена!"); return False
    
    audio_dir = os.path.join(session_path, "audio")
    images_dir = os.path.join(session_path, "images")
    videos_dir = os.path.join(session_path, "videos")
    temp_dir = os.path.join(session_path, "temp_parts")
    output_file = os.path.join(session_path, "final_render.mp4")
    
    if not os.path.exists(audio_dir):
        print(f"❌ Нет папки аудио: {audio_dir}"); return False
    
    os.makedirs(temp_dir, exist_ok=True)
    # Очистка
    for f in glob.glob(os.path.join(temp_dir, "*")):
        try: os.remove(f)
        except: pass
    
    audio_files = sorted([f for f in os.listdir(audio_dir) if f.endswith('.mp3')], key=natural_sort_key)
    if not audio_files: print("❌ Нет аудио файлов!"); return False
    
    print(f"\n📊 Сессия {session_id} | Режим: {RENDER_MODE}")
    print(f"   🎵 Аудио треков: {len(audio_files)}")
    
    processed_files = []
    stats = {"images": 0, "videos": 0, "stretched": 0}

    i = 0
    while i < len(audio_files):
        # 1. Берем текущий файл
        curr_audio_file = audio_files[i]
        base_name = os.path.splitext(curr_audio_file)[0]
        
        # 2. Ищем "сирот" впереди (файлы без медиа)
        orphans_audio = []
        j = i + 1
        while j < len(audio_files):
            next_audio = audio_files[j]
            next_base = os.path.splitext(next_audio)[0]
            
            # Если у следующего файла НЕТ медиа — забираем его себе
            if not check_media_exists(next_base, images_dir, videos_dir, RENDER_MODE):
                orphans_audio.append(os.path.join(audio_dir, next_audio))
                j += 1
            else:
                # Как только нашли файл с медиа — останавливаемся
                break
        
        # Список аудио для текущего кадра (текущий + все сироты)
        current_batch_audio = [os.path.join(audio_dir, curr_audio_file)] + orphans_audio
        
        # Если нашли сирот — склеиваем аудио
        final_audio_path = os.path.join(temp_dir, f"audio_merged_{base_name}.mp3")
        if len(current_batch_audio) > 1:
            print(f"🔗 {base_name}: Склеиваем аудио {base_name} + {len(orphans_audio)} след. (без медиа)")
            if not join_audios(current_batch_audio, final_audio_path):
                print(f"❌ Ошибка склейки аудио для {base_name}")
                i += 1; continue
        else:
            shutil.copy2(current_batch_audio[0], final_audio_path)

        aud_dur = get_duration(final_audio_path)
        if not aud_dur: i += 1; continue

        # Подготовка путей медиа
        img_path = os.path.join(images_dir, f"{base_name}.jpg")
        vid_path = os.path.join(videos_dir, f"{base_name}.mp4")
        if not os.path.exists(img_path):
             for ext in ['.jpeg', '.png']:
                alt = os.path.join(images_dir, f"{base_name}{ext}")
                if os.path.exists(alt): img_path = alt; break

        has_image = os.path.exists(img_path)
        has_video = os.path.exists(vid_path)
        output_temp_path = os.path.join(temp_dir, f"part_{base_name}.mp4")

        # Выбор режима
        use_mode = RENDER_MODE
        if use_mode == "RANDOM":
            if has_image and has_video: 
                # Умный рандом с учетом процентов из config.py
                chance = random.randint(1, 100)
                if chance <= RANDOM_VIDEO_PERCENT:
                    use_mode = "VIDEOS"
                else:
                    use_mode = "IMAGES"
            elif has_video: use_mode = "VIDEOS"
            elif has_image: use_mode = "IMAGES"
        
        # Фоллбэки
        if use_mode == "VIDEOS" and not has_video: use_mode = "IMAGES" if has_image else None
        if use_mode == "IMAGES" and not has_image: use_mode = "VIDEOS" if has_video else None

        # --- ЗАЩИТА ОТ СЛАЙД-ШОУ ПРИ ДЛИННЫХ АУДИО (>15 СЕК) ---
        if use_mode == "VIDEOS" and has_image and aud_dur > 15.0:
            print(f"⚠️ {base_name}: Аудио очень длинное ({aud_dur:.1f}с > 12с). Принудительно ставим КАРТИНКУ вместо растягивания видео.")
            use_mode = "IMAGES"
        # --------------------------------------------------------

        # РЕНДЕР
        success = False

        # РЕНДЕР
        success = False
        info_extra = f" (x{len(orphans_audio)+1} аудио)" if len(orphans_audio) > 0 else ""
        
        if use_mode == "IMAGES":
            print(f"🖼️ {base_name}: Картинка ({aud_dur:.1f}с){info_extra}")
            success = process_image_chunk(img_path, final_audio_path, output_temp_path, aud_dur)
            if success: stats["images"] += 1
            
        elif use_mode == "VIDEOS":
            print(f"🎥 {base_name}: Видео ({aud_dur:.1f}с){info_extra}")
            success = process_video_chunk(vid_path, final_audio_path, output_temp_path, aud_dur)
            if success: stats["videos"] += 1

        if success:
            processed_files.append(output_temp_path)
            if len(orphans_audio) > 0: stats["stretched"] += len(orphans_audio)
        else:
            print(f"❌ Ошибка рендера {base_name}")

        # ПЕРЕХОДИМ К СЛЕДУЮЩЕМУ (пропуская поглощенных сирот)
        i = j 

    # ФИНАЛЬНАЯ СКЛЕЙКА ВСЕГО ВИДЕО
    if not processed_files:
        print("\n❌ Нет фрагментов!"); return False
    
    print(f"\n🔗 Склеиваем {len(processed_files)} частей...")
    concat_list_path = os.path.join(temp_dir, "mylist.txt")
    with open(concat_list_path, 'w', encoding='utf-8') as f:
        for pf in processed_files: f.write(f"file '{os.path.basename(pf)}'\n")
    
    subprocess.run(['ffmpeg', '-y', '-f', 'concat', '-safe', '0', '-i', 'mylist.txt',
                     '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k', 'output_temp.mp4'],
                    cwd=temp_dir, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
    
    final_temp_path = os.path.join(temp_dir, "output_temp.mp4")
    if os.path.exists(final_temp_path):
        if os.path.exists(output_file): os.remove(output_file)
        os.rename(final_temp_path, output_file)
        
        # Чистка
        try: shutil.rmtree(temp_dir)
        except: pass
        
        sz = os.path.getsize(output_file) / (1024 * 1024)
        print(f"\n✅ ГОТОВО! {output_file} ({sz:.1f} MB)")
        print(f"📊 Итог: Картинки: {stats['images']} | Видео: {stats['videos']} | 🩹 Растянуто на пустоты: {stats['stretched']}")
        return True
    else:
        print("\n❌ Ошибка финальной сборки."); return False

def main():
    print("="*60)
    print("🎬 МОНТАЖЁР — SMART STITCH")
    print("="*60)
    if not os.path.exists(RESULT_BASE): print(f"❌ Папка {RESULT_BASE} не найдена!"); return
    
    sessions = sorted([d for d in os.listdir(RESULT_BASE) if os.path.isdir(os.path.join(RESULT_BASE, d)) and d.isdigit()], key=int)
    if not sessions: print("❌ Нет сессий!"); return

    print(f"📁 Сессии: {', '.join(sessions)}")
    sid = input("Введи номер (ENTER = последняя): ").strip() or sessions[-1]
    
    run_for_session(sid)

if __name__ == "__main__":
    main()