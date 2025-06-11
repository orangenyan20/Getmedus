import streamlit as st
import requests
from bs4 import BeautifulSoup
import re
import time
from io import BytesIO
from docx import Document
from docx.shared import Inches

# --- 問題番号からURLを生成 ---
def generate_urls_from_ids(question_ids):
    base_url = "https://medu4.com/"
    return [f"{base_url}{qid.strip()}" for qid in question_ids if qid.strip()]

# --- ページ情報取得（問題文・選択肢・解説など） ---
def get_page_text(url, get_images=True):
    try:
        response = requests.get(url)
        if response.status_code != 200:
            st.warning(f"❌ URL取得失敗: {url}")
            return {
                "category": "取得失敗",
                "problem": "問題文なし",
                "choices": [],
                "answer": "解答なし",
                "question_id": "問題番号なし",
                "explanation": "解説なし",
                "images": []
            }

        soup = BeautifulSoup(response.text, 'html.parser')

        category = soup.find('span', class_='button-small-line')
        category_name = category.text.strip() if category else '分野名なし'

        problem = soup.find('div', class_='quiz-body mb-64')
        problem_text = problem.text.strip() if problem else '問題文なし'

        choices = []
        for choice in soup.find_all('div', class_='box-select'):
            try:
                choice_header = choice.find('span', {'class': 'choice-header'}).text.strip()
                choice_text = choice.find_all('span')[1].text.strip()
                choices.append(f"{choice_header} {choice_text}")
            except:
                continue

        h4_tags = soup.find_all('h4')
        answer_text = '解答なし'
        question_id = '問題番号なし'
        if len(h4_tags) >= 2:
            answer_text = h4_tags[0].text.strip()
            question_id_match = re.search(r'([0-9]{3}[A-Za-z][0-9]+)', h4_tags[1].text)
            if question_id_match:
                question_id = question_id_match.group(1)

        explanation = soup.find('div', class_='explanation')
        explanation_text = explanation.text.strip() if explanation else '解説なし'

        image_urls = []
        if get_images:
            image_divs = soup.find_all('div', class_='box-quiz-image mb-32')
            for div in image_divs:
                img_tag = div.find('img')
                if img_tag and img_tag.get('src'):
                    img_url = img_tag['src'].replace('thumb_', '')
                    image_urls.append(img_url)

        return {
            "category": category_name,
            "problem": problem_text,
            "choices": choices,
            "answer": answer_text,
            "question_id": question_id,
            "explanation": explanation_text,
            "images": image_urls
        }

    except Exception as e:
        st.error(f"⚠️ エラー: {url} - {e}")
        return {
            "category": "エラー",
            "problem": "問題文なし",
            "choices": [],
            "answer": "解答なし",
            "question_id": "問題番号なし",
            "explanation": "解説なし",
            "images": []
        }

# --- Wordファイル生成 ---
def create_word_doc(pages_data, search_query, include_images=True):
    doc = Document()
    doc.add_heading('検索結果', 0)
    doc.add_paragraph(f"取得問題数: {len(pages_data)}問")

    for idx, page_data in enumerate(pages_data, start=1):
        title = f"問題{idx} {page_data['question_id']}"
        doc.add_paragraph(title, style='Heading2')
        doc.add_paragraph(f"問題文: {page_data['problem']}")

        if include_images and page_data['images']:
            for img_url in page_data['images']:
                try:
                    response = requests.get(img_url)
                    if response.status_code == 200:
                        image_stream = BytesIO(response.content)
                        doc.add_paragraph()
                        doc.add_picture(image_stream, width=Inches(2.5))
                    else:
                        doc.add_paragraph(f"画像取得失敗: {img_url}")
                except Exception as e:
                    doc.add_paragraph(f"画像取得中エラー: {e}")

        doc.add_paragraph("選択肢:")
        for choice in page_data['choices']:
            doc.add_paragraph(choice)
        doc.add_paragraph(f"{page_data['answer']}")
        doc.add_paragraph(f"解説: {page_data['explanation']}")
        doc.add_paragraph("-" * 50)

    filename = f"{search_query}_search_results.docx"
    doc.save(filename)
    return filename

# --- Streamlit UI ---
st.title("🩺 Medu4 問題番号 一括収集ツール")

uploaded_file = st.file_uploader("問題番号のファイルをアップロード（.txt or .csv）", type=["txt", "csv"])
include_images = st.checkbox("画像も含める", value=True)

# ファイル読み込み（複数エンコーディング対応）
def try_read_file(file):
     encodings = [
        'utf-8',
        'shift_jis',
        'cp932',
        'iso-2022-jp',
        'utf-16',
        'utf-16-le',
        'utf-16-be'
    ]
    raw = file.read()
    for enc in encodings:
        try:
            return raw.decode(enc).splitlines()
        except:
            continue
    st.error("❌ ファイルの読み込みに失敗しました。文字コードを確認してください。")
    return []

if uploaded_file:
    question_ids = try_read_file(uploaded_file)
    st.write(f"読み込んだ問題ID数: {len(question_ids)}")
    urls = generate_urls_from_ids(question_ids)

    st.write(f"{len(urls)}件の問題を取得します")
    progress_bar = st.progress(0)
    pages_data = []

    for i, url in enumerate(urls):
        page_data = get_page_text(url, get_images=include_images)
        pages_data.append(page_data)
        progress_bar.progress((i + 1) / len(urls))
        time.sleep(0.2)  # サーバー負荷軽減のため遅延

    with st.spinner("📄 Wordファイルを作成中..."):
        filename = create_word_doc(pages_data, "問題番号リスト", include_images=include_images)

    st.success("✅ Wordファイルの生成が完了しました！")
    with open(filename, "rb") as file:
        st.download_button("📥 Wordファイルをダウンロード", file, file_name=filename)
