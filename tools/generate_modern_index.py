#!/usr/bin/env python3
"""고은철 목사 설교 웹북 - 모던 아카이브 index.html 동적 생성 빌더.

manifest.json의 최신 설교 목록과 corpus/lectures_data.json의 강의 목록을 읽어,
사이드바, 탭, 통계 카운트, 검색 데이터 및 카드 그리드가 완벽히 동기화된
모던 반응형 아카이브 랜딩 페이지(site/index.html)를 생성합니다.
"""

import os
import sys
import re
import json
from pathlib import Path

SERIES_MAP = {
    "창세기": ("창세기 (Genesis)", "genesis"),
    "민수기": ("민수기 (Numbers)", "numbers"),
    "레위기": ("레위기 (Leviticus)", "leviticus"),
    "신명기": ("신명기 (Deuteronomy)", "deuteronomy"),
    "여호수아": ("여호수아 (Joshua)", "joshua"),
    "사사기": ("사사기 (Judges)", "judges"),
    "룻기": ("룻기 (Ruth)", "ruth"),
    "사무엘상": ("사무엘상 (1 Samuel)", "samuel1"),
    "사무엘하": ("사무엘하 (2 Samuel)", "samuel2"),
    "열왕기상": ("열왕기상 (1 Kings)", "kings1"),
    "열왕기하": ("열왕기하 (2 Kings)", "kings2"),
    "마태복음": ("마태복음 (Matthew)", "matthew"),
    "산상수훈": ("마태복음 (Matthew)", "matthew"),
    "히브리서": ("히브리서 (Hebrews)", "hebrews"),
    "베드로 전·후서": ("베드로 전·후서 (Peter)", "peter"),
    "베드로전후서": ("베드로 전·후서 (Peter)", "peter"),
    "베드로전서": ("베드로 전·후서 (Peter)", "peter"),
    "베드로후서": ("베드로 전·후서 (Peter)", "peter"),
    "골로새서": ("골로새서 (Colossians)", "colossians"),
    "로마서": ("로마서 (Romans)", "romans"),
    "주제별 신학 강의": ("주제별 신학 및 성경신학", "theology"),
}

LECTURE_TAG_MAP = {
    "c.s 루이스": ("c.s 루이스 신학 강의 교안", "lec-cslewis"),
    "게르할더스 보스": ("게르할더스 보스 성경신학 교안", "lec-vos"),
    "루터": ("마틴 루터 신학 교안", "lec-luther"),
    "바르트, 본회퍼 미래신학": ("바르트 & 본회퍼 미래신학 교안", "lec-barth-bonhoeffer"),
    "발트 아이히로트": ("발트 아이히로트 구약신학 교안", "lec-eichrodt"),
    "본회퍼": ("디트리히 본회퍼 신학 교안", "lec-bonhoeffer"),
    "신(김용규)": ("김용규 '신' 신학 강의 교안", "lec-kim-theology"),
    "에버하르트 융엘": ("에버하르트 융엘 신학 교안", "lec-jungel"),
    "칼 바르트": ("칼 바르트 신학 교안", "lec-barth"),
    "키르케고르": ("쇠렌 키르케고르 신학 교안", "lec-kierkegaard"),
    "토마스 라이트": ("N.T. 라이트 신학 교안", "lec-ntwright"),
    "토마스 아퀴나스": ("토마스 아퀴나스 신학 교안", "lec-aquinas"),
    "판넨베르크": ("볼프하르트 판넨베르크 교안", "lec-pannenberg"),
    "폰 라드": ("게르하르트 폰 라트 구약신학 교안", "lec-vonrad"),
    "인문학·철학 통섭 강의": ("인문학·철학 통섭 강의록 (서양사상사)", "lec-humanities")
}

def slugify(text):
    text = re.sub(r'[^a-zA-Z0-9가-힣]+', '-', text).strip('-')
    return text.lower() or "series"

def build_modern_index_html(proj_root=None):
    if proj_root is None:
        proj_root = Path(__file__).resolve().parent.parent

    manifest_path = proj_root / "corpus" / "manifest.json"
    lectures_path = proj_root / "corpus" / "lectures_data.json"

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    lecture_categories = []
    if lectures_path.exists():
        with open(lectures_path, "r", encoding="utf-8") as f:
            lecture_categories = json.load(f)

    # 1. Group sermon sections from manifest
    sections_raw = manifest.get("sections", [])
    
    ot_series_dict = {}
    nt_series_dict = {}
    theo_series_dict = {}

    for sec in sections_raw:
        t = sec.get("testament", "")
        b_name = sec.get("book_name") or ""
        series = sec.get("series") or b_name or "기타"
        if "베드로" in series:
            series = "베드로 전·후서"
        if "마태" in series or series == "산상수훈" or b_name == "마태복음":
            series = "마태복음"

        out_path_str = sec.get("output", "")
        if out_path_str.startswith("site/"):
            rel_href = out_path_str[5:]
        else:
            rel_href = str(Path(out_path_str).name)

        is_mount = (sec.get("series") == "산상수훈") or (
            sec.get("chapter") in [5, 6, 7]
        ) or (sec.get("id") == "s38-mat6-5-10")

        card_item = {
            "passage": sec.get("passage") or series,
            "title": sec.get("title", ""),
            "href": rel_href,
            "is_mount": is_mount,
            "chapter": sec.get("chapter", 1),
            "id": sec.get("id", "")
        }

        # 히브리서 5부작 연속 강의(s01~s05)는 상단 피처드 배너(히브리서 전권 강해 1~5강)에 독점 배치되므로, 하단 일반 강해 목록 카드에서는 제외
        if sec.get("id") in [
            "s01-heb1-1-4",
            "s02-heb1-5-2-18",
            "s03-heb3-1-7-28",
            "s04-heb8-1-10-18",
            "s05-heb10-19-13-25"
        ]:
            continue

        if t == "OT":
            ot_series_dict.setdefault(series, []).append(card_item)
        elif t == "NT":
            nt_series_dict.setdefault(series, []).append(card_item)
        else:
            theo_series_dict.setdefault(series, []).append(card_item)

    sections_grouped = []

    # 1-1. NT Sections (신약 강해 - 히브리서 최우선 정렬)
    nt_order_pref = ["히브리서", "마태복음", "골로새서", "베드로 전·후서"]
    sorted_nt_keys = sorted(nt_series_dict.keys(), key=lambda k: nt_order_pref.index(k) if k in nt_order_pref else 99)
    for s_name in sorted_nt_keys:
        cards = nt_series_dict[s_name]
        disp_title, tag_key = SERIES_MAP.get(s_name, (f"{s_name} 강해", slugify(s_name)))
        sections_grouped.append({
            "cat_id": "nt",
            "cat_name": "신약 강해",
            "title": disp_title,
            "tag_key": tag_key,
            "cards": cards,
            "series_name": s_name
        })

    # 1-2. OT Sections (구약 강해)
    for s_name, cards in ot_series_dict.items():
        disp_title, tag_key = SERIES_MAP.get(s_name, (f"{s_name} 강해", slugify(s_name)))
        sections_grouped.append({
            "cat_id": "ot",
            "cat_name": "구약 강해",
            "title": disp_title,
            "tag_key": tag_key,
            "cards": cards,
            "series_name": s_name
        })

    # 1-3. Theology Sections
    for s_name, cards in theo_series_dict.items():
        disp_title, tag_key = SERIES_MAP.get(s_name, ("주제별 신학 및 성경신학", "theology"))
        sections_grouped.append({
            "cat_id": "theology",
            "cat_name": "주제별 신학",
            "title": disp_title,
            "tag_key": tag_key,
            "cards": cards,
            "series_name": s_name
        })

    # 1-4. Lecture Sections
    lecture_theology_cnt = 0
    lecture_humanities_cnt = 0
    for litem in lecture_categories:
        ch_list = litem["chapters"] if "chapters" in litem else [litem]
        for ch in ch_list:
            ch_name = ch.get("author") or ch.get("chapter")
            disp_title, tag_key = LECTURE_TAG_MAP.get(ch_name, (f"{ch_name} 강의 교안", f"lec-{slugify(ch_name)}"))
            cards = ch.get("cards", [])
            if tag_key == "lec-humanities":
                lecture_humanities_cnt += len(cards)
            else:
                lecture_theology_cnt += len(cards)

            sections_grouped.append({
                "cat_id": "lectures",
                "cat_name": "강의 자료실",
                "title": disp_title,
                "tag_key": tag_key,
                "cards": cards,
                "series_name": ch_name
            })

    # Count statistics
    ot_count = sum(len(s["cards"]) for s in sections_grouped if s["cat_id"] == "ot")
    nt_count = sum(len(s["cards"]) for s in sections_grouped if s["cat_id"] == "nt")
    theology_count = sum(len(s["cards"]) for s in sections_grouped if s["cat_id"] == "theology")
    sermons_total = ot_count + nt_count + theology_count
    lectures_count = sum(len(s["cards"]) for s in sections_grouped if s["cat_id"] == "lectures")
    total_all = sermons_total + lectures_count

    # Styling Tokens
    badge_styles = {
        "ot": "bg-blue-50 text-blue-700 border-blue-100",
        "nt": "bg-emerald-50 text-emerald-700 border-emerald-100",
        "theology": "bg-purple-50 text-purple-700 border-purple-100",
        "lectures": "bg-amber-50 text-amber-800 border-amber-200"
    }

    cat_tag_names = {
        "ot": "구약",
        "nt": "신약",
        "theology": "신학",
        "lectures": "강의"
    }

    border_hover_styles = {
        "ot": "hover:border-blue-400",
        "nt": "hover:border-emerald-400",
        "theology": "hover:border-purple-400",
        "lectures": "hover:border-amber-400"
    }

    title_hover_styles = {
        "ot": "group-hover:text-blue-600",
        "nt": "group-hover:text-emerald-700",
        "theology": "group-hover:text-purple-700",
        "lectures": "group-hover:text-amber-800"
    }

    read_btn_styles = {
        "ot": "text-blue-600 hover:text-blue-800",
        "nt": "text-emerald-600 hover:text-emerald-800",
        "theology": "text-purple-600 hover:text-purple-800",
        "lectures": "text-amber-700 hover:text-amber-900"
    }

    dot_colors = {
        "ot": "bg-blue-600",
        "nt": "bg-emerald-600",
        "theology": "bg-purple-600",
        "lectures": "bg-amber-600"
    }

    read_btn_labels = {
        "ot": "강해 읽기",
        "nt": "강해 읽기",
        "theology": "강해 읽기",
        "lectures": "강의 읽기"
    }

    # Render Cards HTML
    html_cards = []
    for sec in sections_grouped:
        cat_id = sec["cat_id"]
        badge_cls = badge_styles[cat_id]
        hover_border = border_hover_styles[cat_id]
        hover_title = title_hover_styles[cat_id]
        btn_style = read_btn_styles[cat_id]
        dot_color = dot_colors[cat_id]
        read_label = read_btn_labels[cat_id]
        card_type_label = "개 강의" if cat_id == "lectures" else "개 강해"

        def render_card_item(c):
            passage = c.get("passage") or sec["title"].split()[0]
            title = c["title"]
            href = c["href"]
            search_data = f"{passage} {title} {sec['cat_name']} {sec['title']}".lower()

            return f'''
            <article class="sermon-card bg-white rounded-xl border border-slate-200 p-4 {hover_border} hover:shadow-md transition-all flex flex-col justify-between group" data-category="{cat_id}" data-chapter="{sec["tag_key"]}" data-search="{search_data}">
              <div>
                <div class="flex items-center justify-between mb-2">
                  <span class="text-xs font-bold px-2 py-0.5 rounded border {badge_cls} line-clamp-1 max-w-[200px]" title="{passage}">{passage}</span>
                  <span class="text-[11px] text-slate-400 font-medium">{cat_tag_names[cat_id]}</span>
                </div>
                <h3 class="font-serif font-bold text-slate-900 text-base {hover_title} transition-colors line-clamp-2 mb-2">
                  <a href="{href}">{title}</a>
                </h3>
              </div>
              <div class="pt-3 border-t border-slate-100 flex items-center justify-between mt-2">
                <a href="{href}" class="inline-flex items-center gap-1 text-xs font-bold {btn_style} transition-colors">
                  <span>{read_label}</span>
                  <svg class="w-3.5 h-3.5 transition-transform group-hover:translate-x-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M9 5l7 7-7 7"></path></svg>
                </a>
                <a href="graph.html" title="신학 지식 그래프에서 확인" class="text-slate-400 hover:text-blue-600 p-1 transition-colors">
                  <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><circle cx="18" cy="5" r="3" stroke-width="2"></circle><circle cx="6" cy="12" r="3"></circle><circle cx="18" cy="19" r="3"></circle><line x1="8.59" y1="13.51" x2="15.42" y2="17.49" stroke-width="2"></line><line x1="15.41" y1="6.51" x2="8.59" y2="10.49" stroke-width="2"></line></svg>
                </a>
              </div>
            </article>
            '''

        if sec["tag_key"] == "matthew":
            mount_cards = [c for c in sec["cards"] if c.get("is_mount")]
            other_cards = [c for c in sec["cards"] if not c.get("is_mount")]
            mount_cards_html = "\n".join(render_card_item(c) for c in mount_cards)
            other_cards_html = "\n".join(render_card_item(c) for c in other_cards)

            sec_html = f'''
        <div class="chapter-section chapter-heading mb-8" data-category="{cat_id}" data-chapter="{sec["tag_key"]}" id="sec-{sec["tag_key"]}">
          <div class="chapter-header flex items-center justify-between pb-3 mb-4 border-b border-slate-200 cursor-pointer select-none group/hdr hover:border-slate-300 transition-all rounded-lg px-2 -mx-2 hover:bg-slate-50/80" onclick="toggleSection(\'{sec["tag_key"]}\')" title="클릭하여 접기/펼치기">
            <div class="flex items-center gap-2.5">
              <span class="w-2.5 h-5 rounded-full {dot_color}"></span>
              <h2 class="text-lg md:text-xl font-bold font-serif text-slate-800 group-hover/hdr:text-emerald-700 transition-colors">{sec["title"]}</h2>
              <span class="text-xs font-semibold px-2.5 py-0.5 rounded-full bg-slate-100 text-slate-600">{len(sec["cards"])}{card_type_label}</span>
            </div>
            <button type="button" class="toggle-btn inline-flex items-center gap-1.5 px-3 py-1 rounded-md text-xs font-semibold text-slate-600 bg-white border border-slate-200 shadow-2xs group-hover/hdr:bg-white group-hover/hdr:text-emerald-700 group-hover/hdr:border-emerald-300 transition-all pointer-events-none" id="btn-{sec["tag_key"]}" aria-expanded="true">
              <span class="toggle-text">접기</span>
              <svg class="toggle-icon w-3.5 h-3.5 transform transition-transform duration-200 text-slate-400 group-hover/hdr:text-emerald-700" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M19 9l-7 7-7-7"></path></svg>
            </button>
          </div>
          <div id="grid-{sec["tag_key"]}" class="chapter-card-grid space-y-6 transition-all duration-200">
            <!-- 1. 산상수훈 서브 그룹 -->
            <div class="sub-chapter-group p-4 sm:p-5 rounded-2xl bg-emerald-50/40 border border-emerald-100/90 shadow-2xs">
              <div class="flex items-center justify-between pb-3 mb-4 border-b border-emerald-100">
                <div class="flex items-center gap-2">
                  <span class="inline-flex items-center justify-center w-7 h-7 rounded-lg bg-emerald-100 text-emerald-700 font-bold text-xs">
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253"></path></svg>
                  </span>
                  <h3 class="text-base sm:text-lg font-bold font-serif text-emerald-950">산상수훈 (마태복음 5-7장)</h3>
                  <span class="text-xs font-semibold px-2.5 py-0.5 rounded-full bg-emerald-100 text-emerald-800 border border-emerald-200">{len(mount_cards)}개 강해</span>
                </div>
                <span class="hidden sm:inline text-xs text-emerald-700/80 font-medium">산상대훈 8복과 하나님 나라의 윤리</span>
              </div>
              <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {mount_cards_html}
              </div>
            </div>

            <!-- 2. 마태복음 강해 서브 그룹 -->
            <div class="sub-chapter-group p-4 sm:p-5 rounded-2xl bg-slate-50/70 border border-slate-200/90 shadow-2xs">
              <div class="flex items-center justify-between pb-3 mb-4 border-b border-slate-200">
                <div class="flex items-center gap-2">
                  <span class="inline-flex items-center justify-center w-7 h-7 rounded-lg bg-slate-200 text-slate-700 font-bold text-xs">
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path></svg>
                  </span>
                  <h3 class="text-base sm:text-lg font-bold font-serif text-slate-900">마태복음 강해 (장별 설교)</h3>
                  <span class="text-xs font-semibold px-2.5 py-0.5 rounded-full bg-slate-200 text-slate-700 border border-slate-300">{len(other_cards)}개 강해</span>
                </div>
                <span class="hidden sm:inline text-xs text-slate-500 font-medium">마태복음 장별 연속 강해 및 신규 강해 설교</span>
              </div>
              <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {other_cards_html}
              </div>
            </div>
          </div>
        </div>
            '''
        else:
            cards_html = "\n".join(render_card_item(c) for c in sec["cards"])
            sec_html = f'''
        <div class="chapter-section chapter-heading mb-8" data-category="{cat_id}" data-chapter="{sec["tag_key"]}" id="sec-{sec["tag_key"]}">
          <div class="chapter-header flex items-center justify-between pb-3 mb-4 border-b border-slate-200 cursor-pointer select-none group/hdr hover:border-slate-300 transition-all rounded-lg px-2 -mx-2 hover:bg-slate-50/80" onclick="toggleSection(\'{sec["tag_key"]}\')" title="클릭하여 접기/펼치기">
            <div class="flex items-center gap-2.5">
              <span class="w-2.5 h-5 rounded-full {dot_color}"></span>
              <h2 class="text-lg md:text-xl font-bold font-serif text-slate-800 group-hover/hdr:text-blue-600 transition-colors">{sec["title"]}</h2>
              <span class="text-xs font-semibold px-2.5 py-0.5 rounded-full bg-slate-100 text-slate-600">{len(sec["cards"])}{card_type_label}</span>
            </div>
            <button type="button" class="toggle-btn inline-flex items-center gap-1.5 px-3 py-1 rounded-md text-xs font-semibold text-slate-600 bg-white border border-slate-200 shadow-2xs group-hover/hdr:bg-white group-hover/hdr:text-blue-600 group-hover/hdr:border-blue-300 transition-all pointer-events-none" id="btn-{sec["tag_key"]}" aria-expanded="true">
              <span class="toggle-text">접기</span>
              <svg class="toggle-icon w-3.5 h-3.5 transform transition-transform duration-200 text-slate-400 group-hover/hdr:text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M19 9l-7 7-7-7"></path></svg>
            </button>
          </div>
          <div id="grid-{sec["tag_key"]}" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 chapter-card-grid transition-all duration-200">
            {cards_html}
          </div>
        </div>
        '''
        html_cards.append(sec_html)

    full_cards_html = "\n".join(html_cards)

    # Render Sidebar Book Quick Links
    ot_buttons_html = []
    for s_name, cards in ot_series_dict.items():
        _, tag_key = SERIES_MAP.get(s_name, (s_name, slugify(s_name)))
        ot_buttons_html.append(f'<button type="button" onclick="filterByChapter(\'{tag_key}\')" class="ch-filter-btn px-2 py-1.5 rounded bg-slate-50 text-slate-700 hover:bg-blue-50 hover:text-blue-700 text-left font-medium transition-colors">{s_name} ({len(cards)})</button>')

    nt_buttons_html = []
    for s_name in sorted_nt_keys:
        cards = nt_series_dict[s_name]
        _, tag_key = SERIES_MAP.get(s_name, (s_name, slugify(s_name)))
        nt_buttons_html.append(f'<button type="button" onclick="filterByChapter(\'{tag_key}\')" class="ch-filter-btn px-2 py-1.5 rounded bg-slate-50 text-slate-700 hover:bg-emerald-50 hover:text-emerald-700 text-left font-medium transition-colors">{s_name} ({len(cards)})</button>')

    ot_buttons_str = "\n".join(ot_buttons_html)
    nt_buttons_str = "\n".join(nt_buttons_html)

    page_html = f'''<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>꼬목 강해 설교 · 고은철 목사 아카이브</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Noto+Serif+KR:wght@500;600;700&display=swap" rel="stylesheet">
  <script src="https://cdn.tailwindcss.com"></script>
  <script>
    tailwind.config = {{
      theme: {{
        extend: {{
          fontFamily: {{
            serif: ['"Noto Serif KR"', 'serif'],
            sans: ['Inter', 'sans-serif'],
          }},
          colors: {{
            brand: {{
              navy: '#0F172A',
              blue: '#2563EB',
              canvas: '#F8FAFC'
            }}
          }}
        }}
      }}
    }}
  </script>
  <style>
    body {{ font-family: 'Inter', sans-serif; background-color: #F8FAFC; }}
    .font-serif {{ font-family: 'Noto Serif KR', serif; }}
    /* Custom scrollbar */
    ::-webkit-scrollbar {{ width: 6px; height: 6px; }}
    ::-webkit-scrollbar-thumb {{ background: #CBD5E1; border-radius: 3px; }}
    .no-scrollbar::-webkit-scrollbar {{ display: none; }}
    .no-scrollbar {{ -ms-overflow-style: none; scrollbar-width: none; }}
    /* Google Translate hidden banner and clean integration */
    .goog-te-banner-frame.skiptranslate, .goog-te-banner-frame {{ display: none !important; }}
    body {{ top: 0px !important; }}
    #goog-gt-tt, .goog-te-balloon-frame {{ display: none !important; }}
    .goog-text-highlight {{ background: transparent !important; box-shadow: none !important; }}
    .skiptranslate iframe {{ display: none !important; }}
  </style>
</head>
<body class="text-slate-800 antialiased min-h-screen flex flex-col">

  <!-- 1. 상단 글로벌 헤더 -->
  <header class="top-header sticky top-0 z-50 bg-white/95 backdrop-blur-md border-b border-slate-200">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 h-16 flex items-center justify-between">
      <!-- 브랜드 로고 -->
      <a href="index.html" class="flex items-center gap-3">
        <div class="w-9 h-9 rounded-lg bg-slate-900 text-white flex items-center justify-center shadow-sm">
          <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253"></path></svg>
        </div>
        <div>
          <span class="font-serif font-bold text-base sm:text-lg text-slate-900 leading-none">꼬목 강해 설교</span>
          <span class="block text-[11px] text-slate-500 mt-0.5">그말씀하나교회 · 고은철 목사</span>
        </div>
      </a>

      <!-- 상단 네비게이션 -->
      <nav class="top-nav hidden lg:flex items-center gap-1">
        <button type="button" onclick="setCategory('all')" data-nav-cat="all" class="nav-btn px-3 py-1.5 rounded-lg text-sm font-semibold transition-all bg-slate-900 text-white">전체 강해 ({sermons_total})</button>
        <button type="button" onclick="setCategory('ot')" data-nav-cat="ot" class="nav-btn px-3 py-1.5 rounded-lg text-sm font-medium text-slate-600 hover:text-slate-900 hover:bg-slate-100 transition-all">구약 강해 ({ot_count})</button>
        <button type="button" onclick="setCategory('nt')" data-nav-cat="nt" class="nav-btn px-3 py-1.5 rounded-lg text-sm font-medium text-slate-600 hover:text-slate-900 hover:bg-slate-100 transition-all">신약 강해 ({nt_count})</button>
        <button type="button" onclick="setCategory('theology')" data-nav-cat="theology" class="nav-btn px-3 py-1.5 rounded-lg text-sm font-medium text-slate-600 hover:text-slate-900 hover:bg-slate-100 transition-all">주제별 신학 ({theology_count})</button>
        <button type="button" onclick="setCategory('lectures')" data-nav-cat="lectures" class="nav-btn px-3 py-1.5 rounded-lg text-sm font-medium text-slate-600 hover:text-slate-900 hover:bg-slate-100 transition-all">강의 자료실 ({lectures_count})</button>
        <a href="graph.html" class="px-3 py-1.5 rounded-lg text-sm font-medium text-blue-600 hover:bg-blue-50 flex items-center gap-1.5 transition-all">
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><circle cx="18" cy="5" r="3" stroke-width="2"></circle><circle cx="6" cy="12" r="3" stroke-width="2"></circle><circle cx="18" cy="19" r="3" stroke-width="2"></circle><line x1="8.59" y1="13.51" x2="15.42" y2="17.49" stroke-width="2"></line><line x1="15.41" y1="6.51" x2="8.59" y2="10.49" stroke-width="2"></line></svg>
          <span>실시간 지식맵</span>
        </a>
      </nav>

      <!-- 우측 언어 토글 (KR, EN, CN) 및 모바일 메뉴 버튼 -->
      <div class="flex items-center gap-2">
        <div class="lang-toggle flex items-center bg-slate-100 p-0.5 rounded-lg text-xs font-semibold">
          <button type="button" id="langKrBtn" onclick="switchToKorean()" class="px-2 py-1 rounded-md bg-white text-slate-900 shadow-xs transition-all">KR</button>
          <a href="en/index.html" id="langEnBtn" class="px-2 py-1 text-slate-500 hover:text-slate-900 rounded-md transition-all">EN</a>
          <button type="button" id="cnTranslateBtn" title="中文翻译" class="px-2 py-1 text-slate-500 hover:text-slate-900 rounded-md transition-all">CN</button>
        </div>
        <button type="button" id="mobileMenuBtn" class="lg:hidden p-2 rounded-lg text-slate-600 hover:bg-slate-100" aria-label="메뉴 열기">
          <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16"></path></svg>
        </button>
      </div>
    </div>
  </header>

  <!-- 메인 레이아웃: 사이드바 + 본문 컨테이너 -->
  <div class="max-w-7xl mx-auto px-4 sm:px-6 py-6 w-full flex-1 flex gap-8">

    <!-- 2. 좌측 사이드바 -->
    <aside id="sidebar" class="sidebar hidden lg:block w-64 shrink-0">
      <div class="sticky top-24 space-y-6">

        <!-- 카테고리 선택 -->
        <div class="bg-white rounded-xl border border-slate-200 p-3.5 shadow-xs">
          <div class="text-[11px] font-bold text-slate-400 uppercase tracking-wider px-2 mb-2">카테고리</div>
          <div class="space-y-1">
            <button type="button" onclick="setCategory('all')" data-side-cat="all" class="side-cat-btn w-full flex items-center justify-between px-3 py-2 rounded-lg text-sm font-semibold transition-all bg-slate-900 text-white shadow-xs">
              <span class="flex items-center gap-2">
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 10h16M4 14h16M4 18h16"></path></svg>
                <span>전체 강해</span>
              </span>
              <span class="text-xs opacity-75">{sermons_total}</span>
            </button>
            <button type="button" onclick="setCategory('ot')" data-side-cat="ot" class="side-cat-btn w-full flex items-center justify-between px-3 py-2 rounded-lg text-sm font-medium text-slate-600 hover:bg-slate-100 hover:text-slate-900 transition-all">
              <span class="flex items-center gap-2">
                <svg class="w-4 h-4 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253"></path></svg>
                <span>구약 강해</span>
              </span>
              <span class="text-xs text-slate-400">{ot_count}</span>
            </button>
            <button type="button" onclick="setCategory('nt')" data-side-cat="nt" class="side-cat-btn w-full flex items-center justify-between px-3 py-2 rounded-lg text-sm font-medium text-slate-600 hover:bg-slate-100 hover:text-slate-900 transition-all">
              <span class="flex items-center gap-2">
                <svg class="w-4 h-4 text-emerald-600" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path></svg>
                <span>신약 강해</span>
              </span>
              <span class="text-xs text-slate-400">{nt_count}</span>
            </button>
            <button type="button" onclick="setCategory('theology')" data-side-cat="theology" class="side-cat-btn w-full flex items-center justify-between px-3 py-2 rounded-lg text-sm font-medium text-slate-600 hover:bg-slate-100 hover:text-slate-900 transition-all">
              <span class="flex items-center gap-2">
                <svg class="w-4 h-4 text-purple-600" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19.428 15.428a2 2 0 00-1.022-.547l-2.387-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z"></path></svg>
                <span>주제별 신학</span>
              </span>
              <span class="text-xs text-slate-400">{theology_count}</span>
            </button>
            <button type="button" onclick="setCategory('lectures')" data-side-cat="lectures" class="side-cat-btn w-full flex items-center justify-between px-3 py-2 rounded-lg text-sm font-medium text-slate-600 hover:bg-slate-100 hover:text-slate-900 transition-all">
              <span class="flex items-center gap-2">
                <svg class="w-4 h-4 text-amber-600" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 14v3m4-3v3m4-3v3M3 21h18M3 10h18M3 7l9-4 9 4M4 10h16v11H4V10z"></path></svg>
                <span>강의 자료실</span>
              </span>
              <span class="text-xs text-slate-400">{lectures_count}</span>
            </button>
          </div>
        </div>

        <!-- 성경 권별 & 강의실 퀵 바로가기 -->
        <div class="bg-white rounded-xl border border-slate-200 p-3.5 shadow-xs">
          <div class="text-[11px] font-bold text-slate-400 uppercase tracking-wider px-2 mb-2">성경 권별 &amp; 강의 바로가기</div>
          <div class="space-y-3 text-xs">
            <div>
              <div class="text-[11px] font-semibold text-blue-600 px-2 mb-1">구약 강해 ({ot_count})</div>
              <div class="grid grid-cols-2 gap-1 px-1">
                {ot_buttons_str}
              </div>
            </div>
            <div>
              <div class="text-[11px] font-semibold text-emerald-600 px-2 mb-1">신약 강해 ({nt_count})</div>
              <div class="grid grid-cols-2 gap-1 px-1">
                {nt_buttons_str}
              </div>
            </div>
            <div class="pt-2 border-t border-slate-100">
              <div class="text-[11px] font-semibold text-amber-700 px-2 mb-1">강의 자료실 ({lectures_count})</div>
              <div class="grid grid-cols-1 gap-1 px-1">
                <button type="button" onclick="filterByChapter('theology-lectures')" class="ch-filter-btn px-2 py-1.5 rounded bg-slate-50 text-slate-700 hover:bg-amber-50 hover:text-amber-800 text-left font-medium transition-colors flex items-center justify-between">
                  <span>인물별 신학 강의 교안</span>
                  <span class="text-[11px] text-slate-400">{lecture_theology_cnt}</span>
                </button>
                <button type="button" onclick="filterByChapter('lec-humanities')" class="ch-filter-btn px-2 py-1.5 rounded bg-slate-50 text-slate-700 hover:bg-amber-50 hover:text-amber-800 text-left font-medium transition-colors flex items-center justify-between">
                  <span>인문학·철학 강의록</span>
                  <span class="text-[11px] text-slate-400">{lecture_humanities_cnt}</span>
                </button>
              </div>
            </div>
          </div>
        </div>

        <!-- 실시간 신학 지식 그래프 배너 -->
        <a href="graph.html" class="landing-graph-container block p-3.5 rounded-xl bg-gradient-to-br from-slate-900 to-slate-800 text-white shadow-xs hover:shadow-md transition-all group">
          <div class="flex items-center gap-2 mb-1.5">
            <svg class="w-4 h-4 text-amber-400 group-hover:rotate-45 transition-transform" fill="none" stroke="currentColor" viewBox="0 0 24 24"><circle cx="18" cy="5" r="3" stroke-width="2"></circle><circle cx="6" cy="12" r="3" stroke-width="2"></circle><circle cx="18" cy="19" r="3" stroke-width="2"></circle><line x1="8.59" y1="13.51" x2="15.42" y2="17.49" stroke-width="2"></line><line x1="15.41" y1="6.51" x2="8.59" y2="10.49" stroke-width="2"></line></svg>
            <span class="text-xs font-bold text-amber-300 uppercase tracking-wider">실시간 지식맵</span>
          </div>
          <p class="text-xs text-slate-300 leading-snug">성경 본문과 구속사 신학 개념을 연결한 지식 그래프 열기 &rarr;</p>
        </a>

      </div>
    </aside>

    <!-- 3. 메인 컨텐츠 영역 -->
    <main class="flex-1 min-w-0">

      <!-- 상단 히어로 & 검색창 -->
      <div class="mb-8">
        <div class="mb-4">
          <h1 class="font-serif text-2xl sm:text-3xl font-bold text-slate-900 tracking-tight mb-2">
            성경 본문의 구속사적 해명과 신학 아카이브
          </h1>
          <p class="text-sm text-slate-600">
            그말씀하나교회 고은철 목사의 성경강해 설교와 신학 강의 교안 및 인문학 통섭 연구자료입니다.
          </p>
        </div>

        <!-- 단 하나의 세련된 통합 검색창 -->
        <div class="relative">
          <div class="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none">
            <svg class="w-5 h-5 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"></path></svg>
          </div>
          <input type="text" id="mainSearchInput" placeholder="설교·강의 제목, 성경 구절(창 6, 마 5), 신학자(루이스, 보스, 루터) 검색..." class="w-full pl-11 pr-10 py-3 bg-white border border-slate-200 rounded-xl text-sm text-slate-800 placeholder:text-slate-400 focus:outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100 shadow-xs transition-all">
          <button type="button" id="clearSearchBtn" class="hidden absolute inset-y-0 right-0 pr-3.5 flex items-center text-slate-400 hover:text-slate-600">
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path></svg>
          </button>
        </div>

        <!-- 중앙 카테고리 탭 버튼들 -->
        <div class="mt-4 flex items-center gap-1.5 sm:gap-2 overflow-x-auto pb-1 no-scrollbar">
          <button type="button" onclick="setCategory('all')" data-main-cat="all" class="main-cat-btn px-4 py-2 rounded-lg text-sm font-semibold transition-all whitespace-nowrap bg-slate-900 text-white shadow-xs">
            전체 강해 <span class="ml-1 text-xs opacity-80">({sermons_total})</span>
          </button>
          <button type="button" onclick="setCategory('ot')" data-main-cat="ot" class="main-cat-btn px-4 py-2 rounded-lg text-sm font-medium transition-all whitespace-nowrap bg-white border border-slate-200 text-slate-600 hover:bg-slate-50 hover:text-slate-900 shadow-xs">
            구약 강해 <span class="ml-1 text-xs text-slate-400">({ot_count})</span>
          </button>
          <button type="button" onclick="setCategory('nt')" data-main-cat="nt" class="main-cat-btn px-4 py-2 rounded-lg text-sm font-medium transition-all whitespace-nowrap bg-white border border-slate-200 text-slate-600 hover:bg-slate-50 hover:text-slate-900 shadow-xs">
            신약 강해 <span class="ml-1 text-xs text-slate-400">({nt_count})</span>
          </button>
          <button type="button" onclick="setCategory('theology')" data-main-cat="theology" class="main-cat-btn px-4 py-2 rounded-lg text-sm font-medium transition-all whitespace-nowrap bg-white border border-slate-200 text-slate-600 hover:bg-slate-50 hover:text-slate-900 shadow-xs">
            주제별 신학 <span class="ml-1 text-xs text-slate-400">({theology_count})</span>
          </button>
          <button type="button" onclick="setCategory('lectures')" data-main-cat="lectures" class="main-cat-btn px-4 py-2 rounded-lg text-sm font-medium transition-all whitespace-nowrap bg-white border border-slate-200 text-slate-600 hover:bg-amber-50 hover:text-amber-800 shadow-xs">
            강의 자료실 <span class="ml-1 text-xs text-amber-600 font-semibold">({lectures_count})</span>
          </button>
        </div>

        <!-- 현재 필터 상태 및 검색 결과 카운트 + 일괄 접기/펼치기 -->
        <div id="filterStatus" class="mt-3 flex flex-wrap items-center justify-between gap-2 text-xs text-slate-500">
          <div>총 <span id="visibleCount" class="font-bold text-slate-800">{sermons_total}</span>개의 강해·강의 목록이 표시되고 있습니다.</div>
          <div class="flex items-center gap-2">
            <button type="button" id="resetFilterBtn" onclick="resetAllFilters()" class="hidden text-blue-600 hover:underline font-semibold">필터 초기화</button>
            <div class="flex items-center gap-1.5 pl-2 border-l border-slate-200">
              <button type="button" onclick="collapseAllSections()" class="px-2.5 py-1 text-xs font-medium rounded-lg border border-slate-200 bg-white text-slate-700 hover:bg-slate-50 hover:text-slate-900 transition-all flex items-center gap-1 shadow-2xs" title="모든 성경 권별 및 강의 섹션 접기">
                <svg class="w-3.5 h-3.5 text-slate-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 15l7-7 7 7"></path></svg>
                <span>모두 접기</span>
              </button>
              <button type="button" onclick="expandAllSections()" class="px-2.5 py-1 text-xs font-medium rounded-lg border border-slate-200 bg-white text-slate-700 hover:bg-slate-50 hover:text-slate-900 transition-all flex items-center gap-1 shadow-2xs" title="모든 성경 권별 및 강의 섹션 펼치기">
                <svg class="w-3.5 h-3.5 text-slate-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"></path></svg>
                <span>모두 펼치기</span>
              </button>
            </div>
          </div>
        </div>
      </div>

      <!-- ✨ 최신 성경신학 집중 연속 강해: 히브리서 5부작 피처드 배너 덱 -->
      <div id="featuredHebrewsBanner" class="mb-8 p-5 sm:p-6 rounded-2xl bg-gradient-to-br from-slate-900 via-indigo-950 to-slate-900 text-white shadow-xl border border-indigo-500/20 relative overflow-hidden transition-all duration-300">
        <div class="absolute -right-12 -top-12 w-48 h-48 bg-indigo-500/10 rounded-full blur-3xl pointer-events-none"></div>
        <div class="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 mb-5 border-b border-indigo-800/60">
          <div>
            <div class="flex items-center gap-2 mb-1.5">
              <span class="px-2.5 py-0.5 rounded-full text-[11px] font-bold tracking-wide uppercase bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">New Release</span>
              <span class="text-xs font-semibold text-indigo-300">성경신학 집중 연속 강해 시리즈</span>
            </div>
            <h2 class="font-serif text-xl sm:text-2xl font-bold text-white tracking-tight flex items-center gap-2">
              <span>히브리서 전권 강해 (1~5강 완결)</span>
              <span class="text-xs font-sans font-normal px-2 py-0.5 rounded bg-indigo-500/30 text-indigo-200">히 1~13장</span>
            </h2>
            <p class="text-xs sm:text-sm text-slate-300 mt-1 max-w-2xl leading-relaxed">
              모형론적 성취와 대제사장 그리스도의 완전한 대속, 흔들리지 않는 하나님 나라를 밝히는 5편의 집중 연속 강해입니다.
            </p>
          </div>
          <div class="flex items-center gap-2 shrink-0">
            <a href="hebrews/s01-heb1-1-4.html" class="inline-flex items-center justify-center gap-1.5 px-4 py-2.5 rounded-xl bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-bold text-xs sm:text-sm transition-all shadow-md hover:shadow-emerald-500/20">
              <span>제1강부터 읽기</span>
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 7l5 5m0 0l-5 5m5-5H6"></path></svg>
            </a>
            <button type="button" onclick="filterByChapter('hebrews')" class="inline-flex items-center justify-center gap-1.5 px-3 py-2.5 rounded-xl bg-white/10 hover:bg-white/20 text-slate-200 font-semibold text-xs transition-all border border-white/10">
              <span>목록 바로가기</span>
            </button>
          </div>
        </div>

        <!-- 5개 집중 강의 카드 그리드 -->
        <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3">
          <a href="hebrews/s01-heb1-1-4.html" class="block p-3 rounded-xl bg-white/5 hover:bg-white/10 border border-white/10 hover:border-emerald-400/50 transition-all group">
            <div class="text-[10px] font-bold text-emerald-400 mb-1 flex items-center justify-between">
              <span>제1강</span>
              <span class="text-slate-400 font-mono">히 1:1-4</span>
            </div>
            <h4 class="text-xs font-bold text-white group-hover:text-emerald-300 transition-colors line-clamp-2 leading-snug">
              하나님의 최종 계시이신 아들
            </h4>
            <p class="text-[11px] text-slate-400 mt-1 line-clamp-1">창조의 상속자와 영광의 광채</p>
          </a>
          <a href="hebrews/s02-heb1-5-2-18.html" class="block p-3 rounded-xl bg-white/5 hover:bg-white/10 border border-white/10 hover:border-emerald-400/50 transition-all group">
            <div class="text-[10px] font-bold text-emerald-400 mb-1 flex items-center justify-between">
              <span>제2강</span>
              <span class="text-slate-400 font-mono">히 1:5-2:18</span>
            </div>
            <h4 class="text-xs font-bold text-white group-hover:text-emerald-300 transition-colors line-clamp-2 leading-snug">
              천사보다 높으신 아들과 고난받으신 대제사장
            </h4>
            <p class="text-[11px] text-slate-400 mt-1 line-clamp-1">죽음의 고난을 통한 구원의 창시자</p>
          </a>
          <a href="hebrews/s03-heb3-1-7-28.html" class="block p-3 rounded-xl bg-white/5 hover:bg-white/10 border border-white/10 hover:border-emerald-400/50 transition-all group">
            <div class="text-[10px] font-bold text-emerald-400 mb-1 flex items-center justify-between">
              <span>제3강</span>
              <span class="text-slate-400 font-mono">히 3:1-7:28</span>
            </div>
            <h4 class="text-xs font-bold text-white group-hover:text-emerald-300 transition-colors line-clamp-2 leading-snug">
              모세·안식의 성취와 멜기세덱적 대제사장
            </h4>
            <p class="text-[11px] text-slate-400 mt-1 line-clamp-1">레위 제사를 초월하는 영원한 반차</p>
          </a>
          <a href="hebrews/s04-heb8-1-10-18.html" class="block p-3 rounded-xl bg-white/5 hover:bg-white/10 border border-white/10 hover:border-emerald-400/50 transition-all group">
            <div class="text-[10px] font-bold text-emerald-400 mb-1 flex items-center justify-between">
              <span>제4강</span>
              <span class="text-slate-400 font-mono">히 8:1-10:18</span>
            </div>
            <h4 class="text-xs font-bold text-white group-hover:text-emerald-300 transition-colors line-clamp-2 leading-snug">
              새 언약과 대속죄일 제의의 완전성
            </h4>
            <p class="text-[11px] text-slate-400 mt-1 line-clamp-1">참 장막에서 단번에 드려진 보혈</p>
          </a>
          <a href="hebrews/s05-heb10-19-13-25.html" class="block p-3 rounded-xl bg-white/5 hover:bg-white/10 border border-white/10 hover:border-emerald-400/50 transition-all group">
            <div class="text-[10px] font-bold text-emerald-400 mb-1 flex items-center justify-between">
              <span>제5강</span>
              <span class="text-slate-400 font-mono">히 10:19-13:25</span>
            </div>
            <h4 class="text-xs font-bold text-white group-hover:text-emerald-300 transition-colors line-clamp-2 leading-snug">
              신앙의 경주와 흔들리지 않는 나라
            </h4>
            <p class="text-[11px] text-slate-400 mt-1 line-clamp-1">믿음의 구름 증인들과 영문 밖의 삶</p>
          </a>
        </div>
      </div>

      <!-- 4. 강해 및 강의 카드 섹션 목록 -->
      <div id="sermonContainer">
        {full_cards_html}
      </div>

      <!-- 검색 결과 없음 상태 -->
      <div id="noResults" class="hidden text-center py-16 bg-white rounded-2xl border border-slate-200">
        <div class="w-12 h-12 rounded-full bg-slate-100 text-slate-400 mx-auto flex items-center justify-center mb-3">
          <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"></path></svg>
        </div>
        <h3 class="text-base font-bold text-slate-800 mb-1">검색 결과가 없습니다</h3>
        <p class="text-xs text-slate-500 mb-4">검색어 철자를 확인하시거나, 다른 키워드나 성경 장절(창 6, 마 5), 신학자 이름을 입력해 보세요.</p>
        <button type="button" onclick="resetAllFilters()" class="px-4 py-2 rounded-lg bg-slate-900 text-white text-xs font-semibold hover:bg-slate-800 transition-colors">
          전체 목록으로 돌아가기
        </button>
      </div>

    </main>
  </div>

  <!-- 푸터 -->
  <footer class="bg-white border-t border-slate-200 py-8 mt-12 text-xs text-slate-500">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 flex flex-col md:flex-row justify-between items-center gap-4">
      <div>
        <span class="font-bold text-slate-700">꼬목 강해 설교 · 그말씀하나교회</span> | 담임목회: 고은철 목사
        <p class="text-slate-400 mt-1">성경의 본문적 의미와 구속사적 맥락을 성실하게 해명하는 신학·강해 저장소</p>
      </div>
      <div class="flex items-center gap-4">
        <button type="button" onclick="setCategory('all')" class="hover:text-slate-900">전체 강해</button>
        <button type="button" onclick="setCategory('lectures')" class="hover:text-slate-900">강의 자료실</button>
        <a href="graph.html" class="text-blue-600 hover:underline">실시간 지식맵</a>
      </div>
    </div>
  </footer>

  <!-- 자바스크립트: 동기화된 탭 & 실시간 검색 제어 -->
  <script>
    let currentCategory = 'all';
    let currentChapter = 'all';
    let currentSearch = '';

    const searchInput = document.getElementById('mainSearchInput');
    const clearBtn = document.getElementById('clearSearchBtn');
    const noResults = document.getElementById('noResults');
    const visibleCountEl = document.getElementById('visibleCount');
    const resetBtn = document.getElementById('resetFilterBtn');

    // 카테고리 전환 (상단 네비, 사이드바, 본문 탭 동시 동기화 및 해시 연동)
    function setCategory(cat) {{
      currentCategory = cat;
      currentChapter = 'all';
      if (cat === 'all') {{
        history.replaceState(null, '', window.location.pathname);
      }} else {{
        history.replaceState(null, '', '#' + cat);
      }}
      updateUI();
      applyFilters();
      window.scrollTo({{ top: 0, behavior: 'smooth' }});
    }}

    // -------------------------------------------------------------
    // 섹션별 접기 / 펼치기 (Accordion Toggle) 로직
    // -------------------------------------------------------------
    function toggleSection(tagKey) {{
      const grid = document.getElementById(`grid-${{tagKey}}`);
      const btn = document.getElementById(`btn-${{tagKey}}`);
      if (!grid || !btn) return;

      const isHidden = grid.classList.contains('hidden');
      if (isHidden) {{
        grid.classList.remove('hidden');
        const textSpan = btn.querySelector('.toggle-text');
        const iconSvg = btn.querySelector('.toggle-icon');
        if (textSpan) textSpan.textContent = '접기';
        if (iconSvg) iconSvg.classList.remove('rotate-180');
        btn.setAttribute('aria-expanded', 'true');
      }} else {{
        grid.classList.add('hidden');
        const textSpan = btn.querySelector('.toggle-text');
        const iconSvg = btn.querySelector('.toggle-icon');
        if (textSpan) textSpan.textContent = '펼치기';
        if (iconSvg) iconSvg.classList.add('rotate-180');
        btn.setAttribute('aria-expanded', 'false');
      }}
    }}

    function expandSection(tagKey) {{
      const grid = document.getElementById(`grid-${{tagKey}}`);
      const btn = document.getElementById(`btn-${{tagKey}}`);
      if (!grid || !btn) return;
      grid.classList.remove('hidden');
      const textSpan = btn.querySelector('.toggle-text');
      const iconSvg = btn.querySelector('.toggle-icon');
      if (textSpan) textSpan.textContent = '접기';
      if (iconSvg) iconSvg.classList.remove('rotate-180');
      btn.setAttribute('aria-expanded', 'true');
    }}

    function collapseAllSections() {{
      document.querySelectorAll('.chapter-section').forEach(sec => {{
        const tagKey = sec.getAttribute('data-chapter');
        const grid = document.getElementById(`grid-${{tagKey}}`);
        const btn = document.getElementById(`btn-${{tagKey}}`);
        if (grid && btn) {{
          grid.classList.add('hidden');
          const textSpan = btn.querySelector('.toggle-text');
          const iconSvg = btn.querySelector('.toggle-icon');
          if (textSpan) textSpan.textContent = '펼치기';
          if (iconSvg) iconSvg.classList.add('rotate-180');
          btn.setAttribute('aria-expanded', 'false');
        }}
      }});
    }}

    function expandAllSections() {{
      document.querySelectorAll('.chapter-section').forEach(sec => {{
        const tagKey = sec.getAttribute('data-chapter');
        const grid = document.getElementById(`grid-${{tagKey}}`);
        const btn = document.getElementById(`btn-${{tagKey}}`);
        if (grid && btn) {{
          grid.classList.remove('hidden');
          const textSpan = btn.querySelector('.toggle-text');
          const iconSvg = btn.querySelector('.toggle-icon');
          if (textSpan) textSpan.textContent = '접기';
          if (iconSvg) iconSvg.classList.remove('rotate-180');
          btn.setAttribute('aria-expanded', 'true');
        }}
      }});
    }}

    // 특정 챕터/서브 필터
    function filterByChapter(ch) {{
      currentChapter = ch;
      if (['genesis', 'numbers', 'leviticus', 'deuteronomy'].includes(ch)) {{
        currentCategory = 'ot';
      }} else if (['matthew', 'sermon-mount', 'hebrews', 'peter', 'matthew10', 'colossians', 'romans'].includes(ch)) {{
        currentCategory = 'nt';
      }} else if (ch === 'theology') {{
        currentCategory = 'theology';
      }} else if (ch.startsWith('lec-') || ch === 'theology-lectures') {{
        currentCategory = 'lectures';
      }}
      updateUI();
      applyFilters();

      setTimeout(() => {{
        let targetSec = null;
        if (ch === 'theology-lectures') {{
          targetSec = document.querySelector('.chapter-section[data-category="lectures"]');
        }} else if (ch === 'sermon-mount' || ch === 'matthew10' || ch === 'matthew') {{
          targetSec = document.querySelector('.chapter-section[data-chapter="matthew"]');
        }} else {{
          targetSec = document.querySelector(`.chapter-section[data-chapter="${{ch}}"]`);
        }}
        if (targetSec) {{
          const secTag = targetSec.getAttribute('data-chapter');
          expandSection(secTag);
          targetSec.scrollIntoView({{ behavior: 'smooth', block: 'start' }});
        }}
      }}, 50);
    }}

    function resetAllFilters() {{
      currentCategory = 'all';
      currentChapter = 'all';
      currentSearch = '';
      if (searchInput) searchInput.value = '';
      updateUI();
      applyFilters();
    }}

    function updateUI() {{
      // 1. 상단 네비 버튼 스타일 업데이트
      document.querySelectorAll('.nav-btn').forEach(btn => {{
        if (btn.getAttribute('data-nav-cat') === currentCategory) {{
          btn.className = 'nav-btn px-3 py-1.5 rounded-lg text-sm font-semibold transition-all bg-slate-900 text-white';
        }} else {{
          btn.className = 'nav-btn px-3 py-1.5 rounded-lg text-sm font-medium text-slate-600 hover:text-slate-900 hover:bg-slate-100 transition-all';
        }}
      }});

      // 2. 사이드바 카테고리 버튼 스타일 업데이트
      document.querySelectorAll('.side-cat-btn').forEach(btn => {{
        if (btn.getAttribute('data-side-cat') === currentCategory) {{
          btn.className = 'side-cat-btn w-full flex items-center justify-between px-3 py-2 rounded-lg text-sm font-semibold transition-all bg-slate-900 text-white shadow-xs';
        }} else {{
          btn.className = 'side-cat-btn w-full flex items-center justify-between px-3 py-2 rounded-lg text-sm font-medium text-slate-600 hover:bg-slate-100 hover:text-slate-900 transition-all';
        }}
      }});

      // 3. 본문 중앙 메인 카테고리 탭 스타일 업데이트
      document.querySelectorAll('.main-cat-btn').forEach(btn => {{
        if (btn.getAttribute('data-main-cat') === currentCategory) {{
          btn.className = 'main-cat-btn px-4 py-2 rounded-lg text-sm font-semibold transition-all whitespace-nowrap bg-slate-900 text-white shadow-xs';
        }} else {{
          const isLec = btn.getAttribute('data-main-cat') === 'lectures';
          const hoverCls = isLec ? 'hover:bg-amber-50 hover:text-amber-800' : 'hover:bg-slate-50 hover:text-slate-900';
          btn.className = `main-cat-btn px-4 py-2 rounded-lg text-sm font-medium transition-all whitespace-nowrap bg-white border border-slate-200 text-slate-600 ${{hoverCls}} shadow-xs`;
        }}
      }});

      // 리셋 버튼 표시 여부
      if (currentCategory !== 'all' || currentChapter !== 'all' || currentSearch !== '') {{
        resetBtn.classList.remove('hidden');
      }} else {{
        resetBtn.classList.add('hidden');
      }}
    }}

    function applyFilters() {{
      // 최신 히브리서 피처드 배너 가시성 동적 제어
      const featuredBanner = document.getElementById('featuredHebrewsBanner');
      if (featuredBanner) {{
        if (currentSearch.length > 0 || (currentCategory !== 'all' && currentCategory !== 'nt')) {{
          featuredBanner.classList.add('hidden');
        }} else {{
          featuredBanner.classList.remove('hidden');
        }}
      }}

      let visibleCards = 0;
      const sections = document.querySelectorAll('.chapter-section');

      sections.forEach(sec => {{
        const secCat = sec.getAttribute('data-category');
        const secChapter = sec.getAttribute('data-chapter');

        let matchCategory = false;
        if (currentCategory === 'all') {{
          if (currentSearch.length > 0) {{
            matchCategory = true;
          }} else {{
            matchCategory = (secCat === 'ot' || secCat === 'nt' || secCat === 'theology');
          }}
        }} else {{
          matchCategory = (secCat === currentCategory);
        }}

        let matchChapter = false;
        if (currentChapter === 'all') {{
          matchChapter = true;
        }} else if (currentChapter === 'theology-lectures') {{
          matchChapter = (secCat === 'lectures' && secChapter !== 'lec-humanities');
        }} else if (currentChapter === 'sermon-mount' || currentChapter === 'matthew10' || currentChapter === 'matthew') {{
          matchChapter = (secChapter === 'matthew');
        }} else {{
          matchChapter = (secChapter === currentChapter);
        }}

        let visibleCardsInSection = 0;
        const cards = sec.querySelectorAll('.sermon-card');

        cards.forEach(card => {{
          const searchData = (card.getAttribute('data-search') || '').toLowerCase();
          const matchSearch = (!currentSearch) || searchData.includes(currentSearch);

          if (matchCategory && matchChapter && matchSearch) {{
            card.classList.remove('hidden');
            visibleCards++;
            visibleCardsInSection++;
          }} else {{
            card.classList.add('hidden');
          }}
        }});

        sec.querySelectorAll('.sub-chapter-group').forEach(subGrp => {{
          const visibleInSub = subGrp.querySelectorAll('.sermon-card:not(.hidden)').length;
          if (visibleInSub === 0) {{
            subGrp.classList.add('hidden');
          }} else {{
            subGrp.classList.remove('hidden');
          }}
        }});

        if (visibleCardsInSection > 0) {{
          sec.classList.remove('hidden');
          if (currentSearch.length > 0) {{
            expandSection(secChapter);
          }}
        }} else {{
          sec.classList.add('hidden');
        }}
      }});

      visibleCountEl.textContent = visibleCards;

      if (visibleCards === 0) {{
        noResults.classList.remove('hidden');
      }} else {{
        noResults.classList.add('hidden');
      }}
    }}

    // 검색창 이벤트
    searchInput.addEventListener('input', (e) => {{
      currentSearch = e.target.value.trim().toLowerCase();
      if (currentSearch.length > 0) {{
        clearBtn.classList.remove('hidden');
      }} else {{
        clearBtn.classList.add('hidden');
      }}
      applyFilters();
    }});

    clearBtn.addEventListener('click', () => {{
      searchInput.value = '';
      currentSearch = '';
      clearBtn.classList.add('hidden');
      applyFilters();
    }});

    // 모바일 사이드바 토글
    const mobileBtn = document.getElementById('mobileMenuBtn');
    const sidebar = document.getElementById('sidebar');
    if (mobileBtn && sidebar) {{
      mobileBtn.addEventListener('click', () => {{
        sidebar.classList.toggle('hidden');
      }});
    }}

    // 해시 라우팅 지원
    window.addEventListener('DOMContentLoaded', () => {{
      const hash = window.location.hash.replace('#', '').toLowerCase();
      if (['lectures', 'lecture-archive'].includes(hash)) {{
        setCategory('lectures');
      }} else if (['ot', 'old-testament'].includes(hash)) {{
        setCategory('ot');
      }} else if (['nt', 'new-testament'].includes(hash)) {{
        setCategory('nt');
      }} else if (['theology', 'systematic-theology'].includes(hash)) {{
        setCategory('theology');
      }}
    }});

    // 다국어 번역 로직
    const krBtn = document.getElementById('langKrBtn');
    const enBtn = document.getElementById('langEnBtn');
    const cnBtn = document.getElementById('cnTranslateBtn');

    function isCnActive() {{
      return document.cookie.split(';').some(item => item.trim().startsWith('googtrans=') && item.includes('zh-CN'));
    }}

    function updateLangUI() {{
      if (!krBtn || !cnBtn) return;
      if (isCnActive()) {{
        cnBtn.className = 'px-2 py-1 rounded-md bg-white text-slate-900 shadow-xs font-bold transition-all';
        krBtn.className = 'px-2 py-1 text-slate-500 hover:text-slate-900 rounded-md transition-all';
      }} else {{
        krBtn.className = 'px-2 py-1 rounded-md bg-white text-slate-900 shadow-xs font-bold transition-all';
        cnBtn.className = 'px-2 py-1 text-slate-500 hover:text-slate-900 rounded-md transition-all';
      }}
    }}

    function setTranslateCookie(val) {{
      const domain = window.location.hostname;
      document.cookie = `googtrans=${{val}}; path=/;`;
      if (domain !== 'localhost' && !domain.includes('127.0.0.1')) {{
        document.cookie = `googtrans=${{val}}; path=/; domain=.${{domain}};`;
      }}
    }}

    function loadGoogleTranslateScript(callback) {{
      if (window.google && window.google.translate) {{
        if (callback) callback();
        return;
      }}
      if (!document.getElementById('google_translate_element')) {{
        const div = document.createElement('div');
        div.id = 'google_translate_element';
        div.style.display = 'none';
        document.body.appendChild(div);
      }}
      window.googleTranslateElementInit = function() {{
        new window.google.translate.TranslateElement({{
          pageLanguage: 'auto',
          includedLanguages: 'zh-CN,ko,en',
          autoDisplay: false
        }}, 'google_translate_element');
        if (callback) callback();
      }};
      const script = document.createElement('script');
      script.src = '//translate.google.com/translate_a/element.js?cb=googleTranslateElementInit';
      script.async = true;
      document.head.appendChild(script);
    }}

    function switchToKorean() {{
      if (isCnActive()) {{
        setTranslateCookie('');
        const domain = window.location.hostname;
        document.cookie = `googtrans=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;`;
        if (domain !== 'localhost') {{
          document.cookie = `googtrans=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/; domain=.${{domain}};`;
        }}
        window.location.reload();
      }}
    }}

    if (cnBtn) {{
      cnBtn.addEventListener('click', (e) => {{
        e.preventDefault();
        if (isCnActive()) {{
          switchToKorean();
        }} else {{
          setTranslateCookie('/auto/zh-CN');
          updateLangUI();
          loadGoogleTranslateScript(() => {{
            setTimeout(() => {{
              const select = document.querySelector('.goog-te-combo');
              if (select) {{
                select.value = 'zh-CN';
                select.dispatchEvent(new Event('change'));
              }} else {{
                window.location.reload();
              }}
            }}, 300);
          }});
        }}
      }});
    }}

    updateLangUI();
  </script>
</body>
</html>
'''

    out_site = proj_root / "site" / "index.html"
    out_tpl = proj_root / "templates" / "modern_index.html"

    out_site.parent.mkdir(parents=True, exist_ok=True)
    out_tpl.parent.mkdir(parents=True, exist_ok=True)

    with open(out_site, "w", encoding="utf-8") as f:
        f.write(page_html)

    with open(out_tpl, "w", encoding="utf-8") as f:
        f.write(page_html)

    print(f"[OK] 모던 아카이브 index.html 동적 빌드 완료: 총 {sermons_total}편 설교 + {lectures_count}편 강의 (총 {total_all}편)")
    return out_site

if __name__ == "__main__":
    build_modern_index_html()
