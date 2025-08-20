import os
import io
import base64
import sys
import uuid
import time
import re
import json

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

def get_images(path):
    if not path:
        return []

    extension = os.path.splitext(path)[1].lower()

    if extension == '.pdf':
        try:
            # popplerのパスを適宜修正
            poppler_path = r'C:\\Program Files\\poppler-24.08.0\\Library\\bin'
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
        return None, False, 0.0

    DIFFERENCE_THRESHOLD_PERCENTAGE = 0.005

    width = min(img_a.width, img_b.width)
    height = min(img_a.height, img_b.height)

    img_a = img_a.resize((width, height)).convert("RGB")
    img_b = img_b.resize((width, height)).convert("RGB")

    np_img_a = np.array(img_a)
    np_img_b = np.array(img_b)

    diff = cv2.absdiff(np_img_a, np_img_b)
    gray_diff = cv2.cvtColor(diff, cv2.COLOR_RGB2GRAY)
    _, diff_mask = cv2.threshold(gray_diff, 30, 255, cv2.THRESH_BINARY)
    
    diff_pixels = np.sum(diff_mask > 0)
    total_pixels = width * height
    
    difference_percentage = (diff_pixels / total_pixels) * 100 if total_pixels > 0 else 0.0

    is_changed = difference_percentage >= DIFFERENCE_THRESHOLD_PERCENTAGE

    if is_changed:
        diff_highlight = np_img_b.copy()
        diff_highlight[np.where(diff_mask == 255)] = [255, 0, 0]
        return Image.fromarray(diff_highlight), True, difference_percentage
    else:
        return None, False, difference_percentage

def image_to_base64(pil_image):
    if pil_image is None:
        return None
    
    buffered = io.BytesIO()
    pil_image.save(buffered, format="JPEG")
    return "data:image/jpeg;base64," + base64.b64encode(buffered.getvalue()).decode()

@app.route('/api/check_pages', methods=['POST'])
def check_pages():
    try:
        session_id = str(uuid.uuid4())
        session_dir = os.path.join(uploads_dir, session_id)
        os.makedirs(session_dir, exist_ok=True)
        
        uploaded_files_a = {}
        uploaded_files_b = {}
        
        file_list_a = []
        if 'filesA' in request.files:
            files_a = request.files.getlist('filesA')
            for file in files_a:
                filename = file.filename
                file_path = os.path.join(session_dir, filename)
                file.save(file_path)
                uploaded_files_a[filename] = file_path
            file_list_a = sorted(uploaded_files_a.keys())

        file_list_b = []
        if 'filesB' in request.files:
            files_b = request.files.getlist('filesB')
            for file in files_b:
                filename = file.filename
                file_path = os.path.join(session_dir, filename)
                file.save(file_path)
                uploaded_files_b[filename] = file_path
            file_list_b = sorted(uploaded_files_b.keys())
        
        print("--- アップロードされたファイルAグループ（ファイル名順）---")
        for filename in file_list_a:
            print(filename)
        print("------------------------------------------")

        print("--- アップロードされたファイルBグループ（ファイル名順）---")
        for filename in file_list_b:
            print(filename)
        print("------------------------------------------")

        # 通常チェック（PDF）
        if len(file_list_a) == 1 and len(file_list_b) == 1 and not request.form.get('fileListA'):
            filename_a = file_list_a[0]
            filename_b = file_list_b[0]
            
            # ページ数を取得して返却
            pages_a = 0
            if filename_a.lower().endswith('.pdf'):
                pages_a = len(convert_from_path(uploaded_files_a[filename_a], poppler_path=r'C:\\Program Files\\poppler-24.08.0\\Library\\bin'))
            
            pages_b = 0
            if filename_b.lower().endswith('.pdf'):
                pages_b = len(convert_from_path(uploaded_files_b[filename_b], poppler_path=r'C:\\Program Files\\poppler-24.08.0\\Library\\bin'))

            # セッション情報を保存
            with open(os.path.join(session_dir, 'session_info.json'), 'w') as f:
                json.dump({
                    "type": "normal",
                    "filesA": uploaded_files_a,
                    "filesB": uploaded_files_b,
                    "sorted_filenames": {"A": file_list_a, "B": file_list_b},
                    "cached_results": {}
                }, f)
            
            return jsonify({
                "sessionId": session_id,
                "filesA": [{"filename": filename_a, "pages": pages_a}],
                "filesB": [{"filename": filename_b, "pages": pages_b}]
            })
            
        # 複数ファイルをアップロードし、手動ペアリングリストがない場合
        elif (len(file_list_a) > 1 or len(file_list_b) > 1) and not request.form.get('fileListA'):
            # 自動的にファイル名順でペアリングリストを作成
            max_len = max(len(file_list_a), len(file_list_b))
            pairing_list = []
            for i in range(max_len):
                pairing_list.append({
                    "filenameA": file_list_a[i] if i < len(file_list_a) else None,
                    "filenameB": file_list_b[i] if i < len(file_list_b) else None
                })
            
            # セッション情報を保存
            with open(os.path.join(session_dir, 'session_info.json'), 'w') as f:
                json.dump({
                    "type": "manual",
                    "filesA": uploaded_files_a,
                    "filesB": uploaded_files_b,
                    "pairing_list": pairing_list,
                    "cached_results": {}
                }, f)

            return jsonify({
                "sessionId": session_id,
                "filesA": [{"filename": f, "pages": 1} for f in file_list_a],
                "filesB": [{"filename": f, "pages": 1} for f in file_list_b]
            })

        # 手動ペアリングチェック（複数ファイル）
        elif 'fileListA' in request.form and 'fileListB' in request.form:
            file_list_a_form = [f.strip() for f in request.form.get('fileListA').split('\n') if f.strip()]
            file_list_b_form = [f.strip() for f in request.form.get('fileListB').split('\n') if f.strip()]
            
            # ペアリングリストを作成
            max_len = max(len(file_list_a_form), len(file_list_b_form))
            pairing_list = []
            for i in range(max_len):
                pairing_list.append({
                    "filenameA": file_list_a_form[i] if i < len(file_list_a_form) else None,
                    "filenameB": file_list_b_form[i] if i < len(file_list_b_form) else None
                })
            
            # セッション情報を保存
            with open(os.path.join(session_dir, 'session_info.json'), 'w') as f:
                json.dump({
                    "type": "manual",
                    "filesA": uploaded_files_a,
                    "filesB": uploaded_files_b,
                    "pairing_list": pairing_list,
                    "cached_results": {}
                }, f)

            return jsonify({
                "sessionId": session_id,
                "filesA": [{"filename": f, "pages": 1} for f in file_list_a],
                "filesB": [{"filename": f, "pages": 1} for f in file_list_b]
            })
            
        else:
            return jsonify({"error": "不適切なファイルグループです。"}), 400

    except Exception as e:
        print(f"エラーが発生しました: {e}", file=sys.stderr)
        return jsonify({"error": "サーバー側でエラーが発生しました。"}), 500

@app.route('/api/diff/<session_id>', methods=['GET'])
def diff_check(session_id):
    start_time = time.time()
    session_dir = os.path.join(uploads_dir, session_id)

    if not os.path.isdir(session_dir):
        return jsonify({"error": "セッションが見つかりません。"}), 404

    try:
        with open(os.path.join(session_dir, 'session_info.json'), 'r') as f:
            session_info = json.load(f)
    except FileNotFoundError:
        return jsonify({"error": "セッション情報ファイルが見つかりません。"}), 404

    results = []

    if session_info["type"] == "normal":
        # ソートされたファイル名リストを使用
        filename_a = session_info["sorted_filenames"]["A"][0]
        filename_b = session_info["sorted_filenames"]["B"][0]
        path_a = session_info["filesA"][filename_a]
        path_b = session_info["filesB"][filename_b]
        
        images_a = get_images(path_a)
        images_b = get_images(path_b)

        if len(images_a) != len(images_b):
            return jsonify({"error": "PDFのページ数が異なります。"}), 400

        for i in range(len(images_a)):
            img_a = images_a[i]
            img_b = images_b[i]
            key = f"normal_p{i+1}"
            
            if key in session_info.get("cached_results", {}):
                cached_data = session_info["cached_results"][key]
                diff_img_base64 = cached_data["diffImage"]
                originalA_base64 = cached_data["originalA"]
                originalB_base64 = cached_data["originalB"]
                status = cached_data["status"]
                diff_percentage = cached_data["difference_percentage"]
            else:
                diff_img, is_changed, diff_percentage = get_diff_image(img_a, img_b)
                status = 'changed' if is_changed else 'unchanged'
                diff_img_base64 = image_to_base64(diff_img)
                originalA_base64 = image_to_base64(img_a)
                originalB_base64 = image_to_base64(img_b)

                # 結果をキャッシュに保存
                session_info.setdefault("cached_results", {})[key] = {
                    "diffImage": diff_img_base64,
                    "originalA": originalA_base64,
                    "originalB": originalB_base64,
                    "status": status,
                    "difference_percentage": diff_percentage
                }
                # ファイルに書き戻す
                with open(os.path.join(session_dir, 'session_info.json'), 'w') as f:
                    json.dump(session_info, f, indent=4)
            
            results.append({
                "filename": f"p{i+1}",
                "pagenum": f"p{i+1}",
                "status": status,
                "originalA": originalA_base64,
                "originalB": originalB_base64,
                "diffImage": diff_img_base64,
                "difference_percentage": diff_percentage
            })
            print(f"ファイル: p{i+1} の比較が完了しました。ステータス: {status}, 差異の割合: {diff_percentage:.4f}%")
            sys.stdout.flush()

    elif session_info["type"] == "manual":
        uploaded_files_a = session_info["filesA"]
        uploaded_files_b = session_info["filesB"]
        
        for pair in session_info["pairing_list"]:
            filename_a = pair.get("filenameA")
            filename_b = pair.get("filenameB")
            key = f"manual_{filename_a or filename_b}"

            if key in session_info.get("cached_results", {}):
                cached_data = session_info["cached_results"][key]
                diff_img_base64 = cached_data["diffImage"]
                originalA_base64 = cached_data["originalA"]
                originalB_base64 = cached_data["originalB"]
                status = cached_data["status"]
                diff_percentage = cached_data["difference_percentage"]
            else:
                path_a = uploaded_files_a.get(filename_a) if filename_a and filename_a != '---' else None
                path_b = uploaded_files_b.get(filename_b) if filename_b and filename_b != '---' else None

                img_a = get_images(path_a)[0] if path_a else None
                img_b = get_images(path_b)[0] if path_b else None

                status = 'changed'
                diff_img_base64 = None
                diff_percentage = 0.0

                if img_a and img_b:
                    diff_img, is_changed, diff_percentage = get_diff_image(img_a, img_b)
                    status = 'changed' if is_changed else 'unchanged'
                    diff_img_base64 = image_to_base64(diff_img)
                elif img_a:
                    status = 'missing_b'
                elif img_b:
                    status = 'missing_a'
                
                originalA_base64 = image_to_base64(img_a)
                originalB_base64 = image_to_base64(img_b)

                # 結果をキャッシュに保存
                session_info.setdefault("cached_results", {})[key] = {
                    "diffImage": diff_img_base64,
                    "originalA": originalA_base64,
                    "originalB": originalB_base64,
                    "status": status,
                    "difference_percentage": diff_percentage
                }
                # ファイルに書き戻す
                with open(os.path.join(session_dir, 'session_info.json'), 'w') as f:
                    json.dump(session_info, f, indent=4)


            results.append({
                "filename": filename_a if filename_a else filename_b,
                "status": status,
                "originalA": originalA_base64,
                "originalB": originalB_base64,
                "diffImage": diff_img_base64,
                "difference_percentage": diff_percentage
            })
            print(f"ファイル: {filename_a if filename_a else filename_b} の比較が完了しました。ステータス: {status}, 差異の割合: {diff_percentage:.4f}%")
            sys.stdout.flush()
    
    end_time = time.time()
    elapsed_time = end_time - start_time
    print(f"すべての差分チェックが完了しました。所要時間: {elapsed_time:.2f}秒")
    sys.stdout.flush()

    return jsonify({"results": results})

@app.route('/api/clear_session/<session_id>', methods=['POST'])
def clear_session(session_id):
    session_dir = os.path.join(uploads_dir, session_id)
    if os.path.isdir(session_dir):
        try:
            for filename in os.listdir(session_dir):
                os.remove(os.path.join(session_dir, filename))
            os.rmdir(session_dir)
            print(f"セッションID: {session_id} の一時ファイルを削除しました。")
            return jsonify({"message": f"Session {session_id} cleared successfully."}), 200
        except Exception as e:
            print(f"Error clearing session {session_id}: {e}", file=sys.stderr)
            return jsonify({"error": "Failed to clear session."}), 500
    else:
        return jsonify({"message": "Session not found."}), 404

if __name__ == '__main__':
    app.run(debug=True)