import os
import io
import base64
import sys
import uuid
import time
import shutil
import threading

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
CORS(app)

# セッション管理のためのグローバル変数
SESSIONS = {}

# セッションを自動削除する関数
def clear_session_after_delay(session_id, delay):
    def delete_session():
        print(f"セッション {session_id} が期限切れになりました。ファイルを削除します。")
        try:
            session_dir = os.path.join(uploads_dir, session_id)
            if os.path.exists(session_dir):
                shutil.rmtree(session_dir)
            if session_id in SESSIONS:
                del SESSIONS[session_id]
        except Exception as e:
            print(f"セッションディレクトリ {session_id} の削除中にエラーが発生しました: {e}", file=sys.stderr)
    
    timer = threading.Timer(delay, delete_session)
    timer.start()

def get_images(path):
    if not path:
        return []

    extension = os.path.splitext(path)[1].lower()

    if extension == '.pdf':
        try:
            poppler_path = r'C:\Program Files\poppler-24.08.0\Library\bin'
            return convert_from_path(path, dpi=200, poppler_path=poppler_path)
        except Exception as e:
            print(f"PDFファイルの読み込みに失敗しました: {e}", file=sys.stderr)
            return []
    else:
        try:
            return [Image.open(path)]
        except Exception as e:
            print(f"画像ファイルの読み込みに失敗しました: {e}", file=sys.stderr)
            return []

def get_diff_image(img_a, img_b):
    if not img_a or not img_b:
        return None

    width = max(img_a.width, img_b.width)
    height = max(img_a.height, img_b.height)

    img_a = img_a.resize((width, height)).convert("RGB")
    img_b = img_b.resize((width, height)).convert("RGB")

    np_img_a = np.array(img_a)
    np_img_b = np.array(img_b)

    diff = cv2.absdiff(np_img_a, np_img_b)

    gray_diff = cv2.cvtColor(diff, cv2.COLOR_RGB2GRAY)
    _, diff_mask = cv2.threshold(gray_diff, 30, 255, cv2.THRESH_BINARY)

    diff_highlight = np_img_b.copy()
    diff_highlight[np.where(diff_mask == 255)] = [255, 0, 0]

    return Image.fromarray(diff_highlight)

def image_to_base64(image):
    if image:
        buffered = io.BytesIO()
        image.save(buffered, format="PNG")
        img_str = base64.b64encode(buffered.getvalue()).decode('utf-8')
        return f"data:image/png;base64,{img_str}"
    return ""

@app.route('/api/check_pages', methods=['POST'])
def check_pages():
    print("ページチェックを開始します...")
    sys.stdout.flush()

    if 'filesA' not in request.files and 'filesB' not in request.files:
        print("エラー: ファイルがアップロードされていません。", file=sys.stderr)
        sys.stdout.flush()
        return jsonify({"error": "ファイルがアップロードされていません。"}), 400

    files_a = request.files.getlist('filesA') if 'filesA' in request.files else []
    files_b = request.files.getlist('filesB') if 'filesB' in request.files else []
    
    session_id = str(uuid.uuid4())
    session_dir = os.path.join(uploads_dir, session_id)
    os.makedirs(session_dir, exist_ok=True)
    
    SESSIONS[session_id] = {'dir': session_dir}
    
    file_info_a = []
    file_info_b = []
    
    for file in files_a:
        path = os.path.join(session_dir, 'A_' + file.filename)
        file.save(path)
        images = get_images(path)
        filename_without_prefix = os.path.splitext(file.filename)[0].replace('A_', '', 1)
        file_info_a.append({"filename": filename_without_prefix, "pages": len(images)})
        
    for file in files_b:
        path = os.path.join(session_dir, 'B_' + file.filename)
        file.save(path)
        images = get_images(path)
        filename_without_prefix = os.path.splitext(file.filename)[0].replace('B_', '', 1)
        file_info_b.append({"filename": filename_without_prefix, "pages": len(images)})

    print("ページチェックが完了しました。セッションID:", session_id)
    sys.stdout.flush()

    return jsonify({
        "sessionId": session_id,
        "filesA": file_info_a,
        "filesB": file_info_b
    })

@app.route('/api/diff/<session_id>', methods=['GET'])
def diff_files(session_id):
    print(f"セッションID: {session_id} の差分チェックを開始します...")
    sys.stdout.flush()
    start_time = time.time()

    session_dir = os.path.join(uploads_dir, session_id)
    if not os.path.isdir(session_dir):
        print("エラー: セッションIDが見つかりません。", file=sys.stderr)
        sys.stdout.flush()
        return jsonify({"error": "セッションIDが見つかりません。"}), 404
    
    files = os.listdir(session_dir)
    if not files:
        print("エラー: 差分チェック用のファイルが見つかりません。", file=sys.stderr)
        sys.stdout.flush()
        return jsonify({"error": "差分チェック用のファイルが見つかりません。"}), 404

    files_a_paths = sorted([os.path.join(session_dir, f) for f in files if f.startswith('A_')])
    files_b_paths = sorted([os.path.join(session_dir, f) for f in files if f.startswith('B_')])
    
    results = []
    
    if len(files_a_paths) == 1 and len(files_b_paths) == 1:
        print("複数ページPDFの通常チェックモードで実行します。")
        sys.stdout.flush()

        images_a = get_images(files_a_paths[0])
        images_b = get_images(files_b_paths[0])
        len_a = len(images_a)
        len_b = len(images_b)

        if not images_a and not images_b:
            print("エラー: 画像ファイルの読み込みに問題が発生しました。", file=sys.stderr)
            sys.stdout.flush()
            return jsonify({"error": "画像ファイルの読み込みに問題が発生しました。"}), 500

        num_pages = max(len_a, len_b)
        
        for i in range(num_pages):
            page_number = i + 1
            print(f"ページ {page_number} の処理を開始します...")
            sys.stdout.flush()

            img_a_exists = i < len_a
            img_b_exists = i < len_b
            
            status = "unchanged"
            diff_img = None
            img_a = None
            img_b = None

            if not img_a_exists:
                status = "added"
                img_b = images_b[i]
            elif not img_b_exists:
                status = "removed"
                img_a = images_a[i]
            else:
                img_a = images_a[i]
                img_b = images_b[i]
                diff_img = get_diff_image(img_a, img_b)
                diff_array = np.array(diff_img)
                if np.sum(diff_array) > 0:
                    status = "changed"
            
            originalA_base64 = image_to_base64(img_a)
            originalB_base64 = image_to_base64(img_b)
            diffImage_base64 = image_to_base64(diff_img)
            
            results.append({
                "filename": f"ページ {page_number}",
                "status": status,
                "originalA": originalA_base64,
                "originalB": originalB_base64,
                "diffImage": diffImage_base64
            })
            print(f"ページ {page_number} の比較が完了しました。ステータス: {status}")
            sys.stdout.flush()
    
    else:
        print("複数ファイルのレアケースチェックモードで実行します。")
        sys.stdout.flush()

        dict_a = {os.path.splitext(os.path.basename(f))[0].replace('A_', '', 1): f for f in files_a_paths}
        dict_b = {os.path.splitext(os.path.basename(f))[0].replace('B_', '', 1): f for f in files_b_paths}

        all_filenames = sorted(list(set(dict_a.keys()) | set(dict_b.keys())))
        
        for filename in all_filenames:
            print(f"ファイル: {filename} の比較を開始します...")
            sys.stdout.flush()

            path_a = dict_a.get(filename)
            path_b = dict_b.get(filename)

            img_a = get_images(path_a)[0] if path_a and get_images(path_a) else None
            img_b = get_images(path_b)[0] if path_b and get_images(path_b) else None
            
            status = "unchanged"
            diff_img = None

            if not img_a:
                status = "added"
            elif not img_b:
                status = "removed"
            else:
                diff_img = get_diff_image(img_a, img_b)
                diff_array = np.array(diff_img)
                status = "changed" if np.sum(diff_array) > 0 else "unchanged"

            originalA_base64 = image_to_base64(img_a)
            originalB_base64 = image_to_base64(img_b)
            diffImage_base64 = image_to_base64(diff_img)
            
            results.append({
                "filename": filename,
                "status": status,
                "originalA": originalA_base64,
                "originalB": originalB_base64,
                "diffImage": diffImage_base64
            })
            print(f"ファイル: {filename} の比較が完了しました。ステータス: {status}")
            sys.stdout.flush()

    end_time = time.time()
    elapsed_time = end_time - start_time
    print(f"すべての差分チェックが完了しました。所要時間: {elapsed_time:.2f}秒")
    sys.stdout.flush()

    return jsonify({"results": results})

@app.route('/api/clear_session/<session_id>', methods=['POST'])
def clear_session(session_id):
    if session_id in SESSIONS:
        try:
            session_dir = os.path.join(uploads_dir, session_id)
            if os.path.exists(session_dir):
                shutil.rmtree(session_dir)
            del SESSIONS[session_id]
            print(f"Session {session_id} successfully cleared.")
        except Exception as e:
            print(f"Error clearing session {session_id}: {e}", file=sys.stderr)
            return jsonify({'message': 'Error clearing session'}), 500
    return jsonify({'message': 'Session cleared'})


if __name__ == '__main__':
    app.run(debug=True)