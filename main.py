#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════════╗
║              🚀 MAIN.PY — ГЛАВНЫЙ ЗАПУСК                     ║
║                                                              ║
║  Этот скрипт запускает ВСЮ ЦЕПОЧКУ от текста до финала:      ║
║                                                              ║
║  ЭТАП 1: Озвучка + Картинки + Промпты  (el11_15)             ║
║  ЭТАП 2: Анимация картинок в видео      (Grok8)              ║
║  ЭТАП 3: Финальный монтаж               (montajj)            ║
║                                                              ║
║  ВСЕ НАСТРОЙКИ — В config.py                                 ║
║  Просто запусти: python main.py                              ║
╚══════════════════════════════════════════════════════════════╝
"""

import os
import sys
import time

try:
    import config as CFG
except ImportError:
    print("❌ Файл config.py не найден!")
    sys.exit(1)

def print_banner():
    print()
    print("╔" + "═"*60 + "╗")
    print("║" + "🚀 АВТОМАТИЧЕСКИЙ ПАЙПЛАЙН — ПОЛНЫЙ ЦИКЛ".center(60) + "║")
    print("╠" + "═"*60 + "╣")
    print(f"║  📝 Режим:            {CFG.RENDER_MODE:<37}║")
    print(f"║  🧵 Потоки (Img/Vid): {CFG.THREADS_IMAGES}/{CFG.THREADS_GROK:<34}║")
    print("╚" + "═"*60 + "╝")

def get_session_id():
    """Спрашивает пользователя: новая сессия или продолжить старую?"""
    if not os.path.exists(CFG.RESULT_BASE):
        return None 
    
    sessions = sorted([int(d) for d in os.listdir(CFG.RESULT_BASE) if d.isdigit()])
    if not sessions:
        return None

    print(f"\n📂 Найдены сессии: {sessions}")
    print("💡 Нажми [ENTER] для создания НОВОЙ сессии.")
    print("💡 Введи номер (например, 12), чтобы ПРОДОЛЖИТЬ работу над ней.")
    
    choice = input("👉 Твой выбор: ").strip()
    
    if choice.isdigit():
        sid = str(choice)
        print(f"\n♻️ ВОЗОБНОВЛЯЕМ РАБОТУ НАД СЕССИЕЙ: {sid}")
        return sid
    else:
        print("\n✨ СОЗДАЕМ НОВУЮ СЕССИЮ...")
        return None # None означает "создай новую"

def run_stage_1(force_session_id=None):
    print("\n" + "🔵"*30)
    print("  ЭТАП 1: ГЕНЕРАЦИЯ (Озвучка + Картинки + Промпты)")
    print("🔵"*30 + "\n")
    
    import el11_15_rotate_video7 as stage1
    # Передаем ID сессии в stage1
    session_id = stage1.main(force_session_id)
    
    if not session_id:
        print("❌ Этап 1 не вернул номер сессии!")
        return None
    
    print(f"\n✅ Этап 1 завершён. Сессия: {session_id}")
    return session_id

def run_stage_2(session_id):
    print("\n" + "🟡"*30)
    print("  ЭТАП 2: АНИМАЦИЯ (Grok)")
    print("🟡"*30 + "\n")
    import Grok8 as stage2
    stage2.run_for_session(session_id)

def run_stage_3(session_id):
    print("\n" + "🟢"*30)
    print("  ЭТАП 3: МОНТАЖ")
    print("🟢"*30 + "\n")
    import montajj as stage3
    stage3.run_for_session(session_id)

def main():
    print_banner()
    
    # СПРАШИВАЕМ ПОЛЬЗОВАТЕЛЯ
    forced_id = get_session_id()
    
    start_time = time.time()
    
    # Запускаем Этап 1 с переданным ID (или None)
    session_id = run_stage_1(forced_id)
    
    if not session_id:
        return
    
    if CFG.RENDER_MODE != "IMAGES":
        run_stage_2(session_id)
    
    run_stage_3(session_id)
    
    elapsed = time.time() - start_time
    print(f"\n🏁 ВРЕМЯ ВЫПОЛНЕНИЯ: {int(elapsed//60)} мин {int(elapsed%60)} сек")

if __name__ == "__main__":
    main()