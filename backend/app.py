import os
import io
import base64
import sys
import time
import uuid

from flask import Flask, request, jsonify
from flask_cors import CORS
from PIL import Image
from pdf2image import convert_from_path
import numpy as np
import cv2

# Pillowの画像サイズ制限を解除
Image.MAX_IMAGE_PIXELS = None

# 一時ファイルを保存するフォルダ
uploads_dir = 'uploads'
os.makedirs(uploads_dir, exist_ok=True)

app = Flask(__name__)
CORS(app)  # Reactからのリクエストを許可

# -----------------
# 既存の画像処理関数
# -----------------

def get_images(path):
    """ファイルパスから画像リストを取得する（PDF対応）"""
    if not path:
        return []

    extension = os.path.splitext(path)[1].lower()

    if extension == '.pdf':
        try:
            # Windows環境では、popplerのパスを指定する必要があります
            poppler_path = r'C:\Program Files\poppler-24.08.0\Library\bin'
            return convert_from_path(path, dpi=200, poppler_path=poppler_path)
        except Exception as e:
            print(f"PDFファイルの読み込みに失敗しました: {e}")
            return []
    else:
        try:
            return [Image.open(path)]
        except Exception as e:
            print(f"画像ファイルの読み込みに失敗しました: {e}")
            return []

def get_diff_image(img_a, img_b):
    """2つの画像の差分を検出し、強調して表示する"""
    if not img_a or not img_b:
        return None

    # サイズを統一
    width = max(img_a.width, img_b.width)
    height = max(img_a.height, img_b.height)

    img_a = img_a.resize((width, height)).convert("RGB")
    img_b = img_b.resize((width, height)).convert("RGB")

    # 画像をnumpy配列に変換
    np_img_a = np.array(img_a)
    np_img_b = np.array(img_b)

    # 差分を計算 (CV2を使用)
    diff = cv2.absdiff(np_img_a, np_img_b)

    # 差分を強調するために、グレースケールに変換して閾値処理
    gray_diff = cv2.cvtColor(diff, cv2.COLOR_RGB2GRAY)
    _, diff_mask = cv2.threshold(gray_diff, 30, 255, cv2.THRESH_BINARY)

    # マスクを適用し、差分箇所を赤色などでハイライト
    diff_highlight = np_img_b.copy()
    diff_highlight[np.where(diff_mask == 255)] = [255, 0, 0] # 赤色でハイライト

    return Image.fromarray(diff_highlight)

def image_to_base64(image):
    """画像をBase64文字列に変換する"""
    if image:
        buffered = io.BytesIO()
        image.save(buffered, format="PNG")
        img_str = base64.b64encode(buffered.getvalue()).decode('utf-8')
        return f"data:image/png;base64,{img_str}"
    return ""

# -----------------
# Flask APIエンドポイント
# -----------------

@app.route('/api/check_pages', methods=['POST'])
def check_pages():
    if 'fileA' not in request.files or 'fileB' not in request.files:
        return jsonify({"error": "両方のファイルをアップロードしてください。"}), 400

    file_a = request.files['fileA']
    file_b = request.files['fileB']

    # 一時ファイル名を作成して保存
    session_id = str(uuid.uuid4())
    session_dir = os.path.join(uploads_dir, session_id)
    os.makedirs(session_dir, exist_ok=True)
    
    path_a = os.path.join(session_dir, file_a.filename)
    path_b = os.path.join(session_dir, file_b.filename)
    file_a.save(path_a)
    file_b.save(path_b)
    
    # ページ数とファイル名をクライアントに返す
    try:
        images_a = get_images(path_a)
        images_b = get_images(path_b)
        
        len_a = len(images_a)
        len_b = len(images_b)

        return jsonify({
            "sessionId": session_id,
            "lenA": len_a,
            "lenB": len_b,
            "filenameA": file_a.filename,
            "filenameB": file_b.filename
        })

    except Exception as e:
        print(f"ページチェック中にエラーが発生しました: {e}")
        return jsonify({"error": "ファイルのページチェックに失敗しました。"}), 500

@app.route('/api/diff/<session_id>', methods=['GET'])
def diff_files(session_id):
    session_dir = os.path.join(uploads_dir, session_id)
    if not os.path.isdir(session_dir):
        return jsonify({"error": "セッションIDが見つかりません。"}), 404
        
    files = os.listdir(session_dir)
    if len(files) < 2:
        return jsonify({"error": "差分チェック用のファイルが見つかりません。"}), 404

    # ファイルパスを取得
    path_a = os.path.join(session_dir, files[0])
    path_b = os.path.join(session_dir, files[1])

    print("差分チェックの準備を開始します...")
    sys.stdout.flush()

    start_time = time.time()

    images_a = get_images(path_a)
    images_b = get_images(path_b)
    len_a = len(images_a)
    len_b = len(images_b)

    if not images_a and not images_b:
        return jsonify({"error": "画像ファイルの読み込みに問題が発生しました。"}), 500

    results = []
    num_pages = max(len_a, len_b)

    for i in range(num_pages):
        page_number = i + 1
        print(f"ページ {page_number} の処理を開始します...")
        sys.stdout.flush()

        img_a_exists = i < len_a
        img_b_exists = i < len_b
        
        # ページが存在しない場合（追加または削除）
        if not img_a_exists:
            status = "added"
            img_b = images_b[i]
            diff_img = None
            img_a = None
        elif not img_b_exists:
            status = "removed"
            img_a = images_a[i]
            diff_img = None
            img_b = None
        # 両方存在する場合（変更または変更なし）
        else:
            img_a = images_a[i]
            img_b = images_b[i]
            diff_img = get_diff_image(img_a, img_b)
            
            # 差分がない場合は"unchanged"、ある場合は"changed"
            diff_array = np.array(diff_img)
            status = "changed" if np.sum(diff_array) > 0 else "unchanged"

        originalA_base64 = image_to_base64(img_a)
        originalB_base64 = image_to_base64(img_b)
        diffImage_base64 = image_to_base64(diff_img)
        
        results.append({
            "page": page_number,
            "status": status,
            "originalA": originalA_base64,
            "originalB": originalB_base64,
            "diffImage": diffImage_base64
        })

        print(f"ページ {page_number} の処理が完了しました。")
        sys.stdout.flush()
    
    end_time = time.time()
    elapsed_time = end_time - start_time

    print(f"すべてのページの処理が完了しました。所要時間: {elapsed_time:.2f}秒")
    sys.stdout.flush()
    
    return jsonify({"results": results})


if __name__ == '__main__':
    app.run(debug=True)