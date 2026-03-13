import json
import os

# パス設定
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ACADEMIC_FILE = os.path.join(SCRIPT_DIR, "academic_info.json") # 分割済みの既存ファイル
COURSES_FILE = os.path.join(SCRIPT_DIR, "courses_clean.json")  # 新しいコースファイル
OUTPUT_FILE = os.path.join(SCRIPT_DIR, "unified_ur_data.json")

def process_courses(course_data):
    unified_courses = []
    base_url = "https://cdcs.ur.rochester.edu/" # ロチェスター大学のコースカタログURL

    for course in course_data:
        # 1. テキストの統合 (松田さんのアイデア)
        # ラベルを付けることでAIが構造を理解しやすくなります
        combined_text = (
            f"Course Code: {course['code']}\n"
            f"Title: {course['title']}\n"
            f"Credits: {course['credits']} | Offered: {course['offered']}\n"
            f"Description: {course['description']}\n"
        )
        
        if course.get('notes'):
            combined_text += f"Important Notes: {course['notes']}\n"
        if course.get('restrictions'):
            combined_text += f"Restrictions: {course['restrictions']}\n"

        # 2. メタデータの整理
        # 既存データと共通のキーを維持しつつ、コース特有のキーも保持
        entry = {
            "url": base_url,
            "department": "",
            "school": "",
            "depth": 2,
            "content_type": "course_description",
            "text": combined_text.strip(),
            "chunk_index": 0, # コース情報は短いので1チャンク扱い
            "chunk_total": 1,
        }
        unified_courses.append(entry)
    
    return unified_courses

def main():
    # 既存の学術情報を読み込む
    with open(ACADEMIC_FILE, "r", encoding="utf-8") as f:
        academic_data = json.load(f)

    # 新しいコース情報を読み込んで処理
    with open(COURSES_FILE, "r", encoding="utf-8") as f:
        raw_courses = json.load(f)
    processed_courses = process_courses(raw_courses)

    # 統合
    unified_data = academic_data + processed_courses

    # 保存
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(unified_data, f, indent=2, ensure_ascii=False)

    print(f"統合完了！")
    print(f"学術データ: {len(academic_data)}件")
    print(f"コースデータ: {len(processed_courses)}件")
    print(f"合計: {len(unified_data)}件が {OUTPUT_FILE} に保存されました。")

if __name__ == "__main__":
    main()