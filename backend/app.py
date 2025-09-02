import os
import io
import base64
import sys
import uuid
import time
import re  # === [FIX] Natural sort (numeric-aware) ===

from flask import Flask, request, jsonify
from flask_cors import CORS
from PIL import Image
from pdf2image import convert_from_path, pdfinfo_from_path  # pdfinfo_from_path を追加
import numpy as np
import cv2

# Pillowの画像サイズ制限を解除
Image.MAX_IMAGE_PIXELS = None

# 一時ファイルを保存するフォルダ
uploads_dir = 'uploads'
os.makedirs(uploads_dir, exist_ok=True)

app = Flask(__name__)
CORS(app)

# === [FIX] Natural sort (numeric-aware) ===
def natural_key(path_or_name: str):
    """人間の自然な並び順でソートするためのキー（数値は数値として比較）"""
    s = os.path.basename(path_or_name)
    return [int(tok) if tok.isdigit() else tok.lower() for tok in re.split(r'(\d+)', s)]

# ===========================
# 画像読み込みユーティリティ
# ===========================
def get_images(path):
    """path から画像の配列(PIL.Image)を返す。PDFは全ページ展開、画像は1枚配列で返す。"""
    if not path:
        return []

    extension = os.path.splitext(path)[1].lower()

    if extension == '.pdf':
        try:
            poppler_path = os.environ.get("POPPLER_PATH", None)
            if poppler_path and os.path.isdir(poppler_path):
                return convert_from_path(path, dpi=200, poppler_path=poppler_path)
            else:
                return convert_from_path(path, dpi=200)
        except Exception as e:
            print(f"PDFファイルの読み込みに失敗しました: {e}", file=sys.stderr)
            return []
    else:
        try:
            return [Image.open(path)]
        except Exception as e:
            print(f"画像ファイルの読み込みに失敗しました: {e}", file=sys.stderr)
            return []

def count_pages_fast(path):
    """PDFはページ展開せずに枚数だけ取得。画像は1ページ扱い。"""
    ext = os.path.splitext(path)[1].lower()
    if ext == ".pdf":
        try:
            poppler_path = os.environ.get("POPPLER_PATH", None)
            info = pdfinfo_from_path(path, poppler_path=poppler_path) if poppler_path else pdfinfo_from_path(path)
            return int(info.get("Pages", 0))
        except Exception as e:
            print(f"PDFページ数の取得に失敗: {e}", file=sys.stderr)
            return 0
    else:
        return 1

def image_to_base64(image):
    if image:
        buffered = io.BytesIO()
        image.save(buffered, format="PNG")
        img_str = base64.b64encode(buffered.getvalue()).decode('utf-8')
        return f"data:image/png;base64,{img_str}"
    return ""

# ===================================
# ページ間の差分（ハイライト）ユーティリティ
# ===================================
def get_diff_image(img_a, img_b):
    """
    2枚のPIL Imageを比較して、差分ハイライト画像(PIL)・変更有無・差分率(%)を返す。
    サイズ調整は「2枚のうち面積（幅×高さ）が小さい方の元サイズ」に揃える。
    しきい値は百分率(%)で 0.001 を採用。
    """
    if not img_a or not img_b:
        return None, False, 0.0

    # しきい値は "百分率"（%）で扱う（0.001%）
    DIFFERENCE_THRESHOLD_PERCENTAGE = 0.001

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
        diff_highlight[np.where(diff_mask == 255)] = [255, 0, 0]  # 赤塗り
        return Image.fromarray(diff_highlight), True, difference_percentage
    else:
        return None, False, difference_percentage

# ===================================
# レアケース用：ページ配列のアライメント
# ===================================
def _to_gray_resized_rgb(np_rgb, size=256):
    """RGB ndarray -> gray resized ndarray"""
    g = cv2.cvtColor(cv2.resize(np_rgb, (size, size), interpolation=cv2.INTER_AREA),
                     cv2.COLOR_RGB2GRAY)
    return g

def _ahash(gray, size=32):
    small = cv2.resize(gray, (size, size), interpolation=cv2.INTER_AREA)
    avg = small.mean()
    return (small > avg).astype(np.uint8)

def _hamming(h1, h2):
    return int(np.sum(h1 != h2))

def _ssim_like(g1, g2):
    x = cv2.GaussianBlur(g1.astype(np.float32), (5, 5), 0)
    y = cv2.GaussianBlur(g2.astype(np.float32), (5, 5), 0)
    C1, C2 = (6.5025, 58.5225)
    mu_x = cv2.GaussianBlur(x, (11, 11), 1.5)
    mu_y = cv2.GaussianBlur(y, (11, 11), 1.5)
    sigma_x = cv2.GaussianBlur(x * x, (11, 11), 1.5) - mu_x * mu_x
    sigma_y = cv2.GaussianBlur(y * y, (11, 11), 1.5) - mu_y * mu_y
    sigma_xy = cv2.GaussianBlur(x * y, (11, 11), 1.5) - mu_x * mu_y
    ssim_map = ((2 * mu_x * mu_y + C1) * (2 * sigma_xy + C2)) / (
        (mu_x * mu_x + mu_y * mu_y + C1) * (sigma_x + sigma_y + C2) + 1e-8
    )
    return float(np.clip(ssim_map.mean(), 0.0, 1.0))

def _build_cost_matrix(pil_list_A, pil_list_B, hash_size=32, down=256, w_hash=0.5, w_ssim=0.5, diag_bias=0.01):
    """
    A, B: list of PIL.Image (RGB)
    戻り値: コスト行列 (n x m) 小さいほど似ている
    diag_bias: 近傍対応をわずかに優先する対角バイアス（0〜）。0.01前後が無難。
    """
    A_rgb = [np.array(img.convert("RGB").resize((down, down))) for img in pil_list_A]
    B_rgb = [np.array(img.convert("RGB").resize((down, down))) for img in pil_list_B]
    A_g = [_to_gray_resized_rgb(a, size=down) for a in A_rgb]
    B_g = [_to_gray_resized_rgb(b, size=down) for b in B_rgb]
    A_h = [_ahash(g, size=hash_size) for g in A_g]
    B_h = [_ahash(g, size=hash_size) for g in B_g]

    n, m = len(A_g), len(B_g)
    C = np.zeros((n, m), dtype=np.float32)
    denom = float(max(n, m)) if max(n, m) > 0 else 1.0

    for i in range(n):
        for j in range(m):
            dh = _hamming(A_h[i], B_h[j]) / float(hash_size * hash_size)  # 0..1
            s = _ssim_like(A_g[i], B_g[j])                                 # 0..1
            cost = w_hash * dh + w_ssim * (1.0 - s)
            # 対角バイアス
            if diag_bias > 0:
                cost += diag_bias * (abs(i - j) / denom)
            C[i, j] = cost
    return C

def _align_affine(C, gap_open=0.15, gap_extend=0.02, band=None):
    """
    アフィンギャップのグローバルアライメント。Cはコスト行列（小さいほど良い）。
    戻り値: [(i or None, j or None), ...]
    """
    n, m = C.shape
    INF = 1e9
    M = np.full((n + 1, m + 1), INF, dtype=np.float32)
    X = np.full((n + 1, m + 1), INF, dtype=np.float32)
    Y = np.full((n + 1, m + 1), INF, dtype=np.float32)
    TBM = np.zeros((n + 1, m + 1), dtype=np.uint8)
    TBX = np.zeros((n + 1, m + 1), dtype=np.uint8)
    TBY = np.zeros((n + 1, m + 1), dtype=np.uint8)

    M[0, 0] = 0.0

    for i in range(1, n + 1):
        X[i, 0] = gap_open + (i - 1) * gap_extend
    for j in range(1, m + 1):
        Y[0, j] = gap_open + (j - 1) * gap_extend

    for i in range(1, n + 1):
        j_min, j_max = 1, m
        if band is not None:
            j_min = max(1, i - band)
            j_max = min(m, i + band)
        for j in range(j_min, j_max + 1):
            c = C[i - 1, j - 1]
            # 対角（マッチ）
            candM = [(M[i - 1, j - 1] + c, 1), (X[i - 1, j - 1] + c, 2), (Y[i - 1, j - 1] + c, 3)]
            M[i, j], TBM[i, j] = min(candM, key=lambda x: x[0])
            # 縦ギャップ（Aにギャップ= Aの削除）
            candX = [(M[i - 1, j] + gap_open, 1), (X[i - 1, j] + gap_extend, 2)]
            X[i, j], TBX[i, j] = min(candX, key=lambda x: x[0])
            # 横ギャップ（Bにギャップ= Bの追加）
            candY = [(M[i, j - 1] + gap_open, 1), (Y[i, j - 1] + gap_extend, 2)]
            Y[i, j], TBY[i, j] = min(candY, key=lambda x: x[0])

    # 終端から追跡
    end_costs = [(M[n, m], 'M'), (X[n, m], 'X'), (Y[n, m], 'Y')]
    _, state = min(end_costs, key=lambda x: x[0])

    align = []
    i, j = n, m
    while i > 0 or j > 0:
        if state == 'M':
            prev = TBM[i, j]
            align.append((i - 1, j - 1))
            i, j = i - 1, j - 1
            state = 'M' if prev == 1 else ('X' if prev == 2 else 'Y')
        elif state == 'X':
            prev = TBX(i, j) if callable(TBX) else TBX[i, j]  # 防御
            align.append((i - 1, None))
            i -= 1
            state = 'M' if prev == 1 else 'X'
        else:  # 'Y'
            prev = TBY(i, j) if callable(TBY) else TBY[i, j]  # 防御
            align.append((None, j - 1))
            j -= 1
            state = 'M' if prev == 1 else 'Y'

    align.reverse()
    return align

# ===========================
# ルーティング
# ===========================
@app.route('/api/check_pages', methods=['POST'])
def check_pages():
    print("ページチェックを開始します...")
    sys.stdout.flush()

    # === [UPLOAD UNIFIED] 入口統一：filesA/filesB に加えて files でも受付 ===
    has_any = ('filesA' in request.files) or ('filesB' in request.files) or ('files' in request.files)
    if not has_any:
        print("エラー: ファイルがアップロードされていません。", file=sys.stderr)
        sys.stdout.flush()
        return jsonify({"error": "ファイルがアップロードされていません。"}), 400

    files_a = request.files.getlist('filesA') if 'filesA' in request.files else []
    files_b = request.files.getlist('filesB') if 'filesB' in request.files else []

    # 単一フィールド 'files' で来た場合は A_/B_ 接頭辞で振り分け
    unknown_group = []
    if 'files' in request.files:
        mixed = request.files.getlist('files')
        for f in mixed:
            fname = f.filename or ""
            if fname.startswith('A_'):
                files_a.append(f)
            elif fname.startswith('B_'):
                files_b.append(f)
            else:
                unknown_group.append(fname)  # 判別不可→警告リストへ

    session_id = str(uuid.uuid4())
    session_dir = os.path.join(uploads_dir, session_id)
    os.makedirs(session_dir, exist_ok=True)

    # 一旦保存
    for file in files_a:
        path = os.path.join(session_dir, 'A_' + file.filename)
        file.save(path)
    for file in files_b:
        path = os.path.join(session_dir, 'B_' + file.filename)
        file.save(path)

    # === [CONFIRM VIEW] 確認表示用の情報（自然順＆ファイル数）
    all_files = os.listdir(session_dir)
    files_a_paths = sorted([os.path.join(session_dir, f) for f in all_files if f.startswith('A_')], key=natural_key)
    files_b_paths = sorted([os.path.join(session_dir, f) for f in all_files if f.startswith('B_')], key=natural_key)

    file_info_a = []
    file_names_a = []
    for p in files_a_paths:
        show = os.path.basename(p).replace('A_', '', 1)
        pages = count_pages_fast(p)
        file_info_a.append({"filename": show, "pages": pages})
        file_names_a.append(show)

    file_info_b = []
    file_names_b = []
    for p in files_b_paths:
        show = os.path.basename(p).replace('B_', '', 1)
        pages = count_pages_fast(p)
        file_info_b.append({"filename": show, "pages": pages})
        file_names_b.append(show)

    # === [VALIDATION] 軽い運用チェック（任意）
    issues = []
    if unknown_group:
        issues.append("A_/B_ の接頭辞で判別できないファイルがあります: " + ", ".join(unknown_group))

    print("ページチェックが完了しました。セッションID:", session_id)
    sys.stdout.flush()

    return jsonify({
        "sessionId": session_id,
        "filesA": file_info_a,
        "filesB": file_info_b,
        "groupFileCountA": len(file_info_a),
        "groupFileCountB": len(file_info_b),
        "fileNamesA": file_names_a,
        "fileNamesB": file_names_b,
        "uploadIssues": issues,            # 追加：警告の配列
        "isValidPattern": len(issues) == 0 # 追加：推奨パターンかどうか
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

    # 自然順
    files_a_paths = sorted([os.path.join(session_dir, f) for f in files if f.startswith('A_')], key=natural_key)
    files_b_paths = sorted([os.path.join(session_dir, f) for f in files if f.startswith('B_')], key=natural_key)

    results = []

    # =============================
    # === [UNIFIED ALIGN] 常にレアケース・フローで処理 =============================
    # =============================
    print("レアケース（アライメント）方式で実行します。")
    sys.stdout.flush()

    def load_group(paths, prefix):
        """
        各ファイルの全ページを展開し、[(label, PIL)] を返す。
        label は '元ファイル名'（ページサフィックスは付けない）。
        """
        items = []
        for p in paths:
            base = os.path.basename(p)
            orig = base.replace(f"{prefix}_", "", 1)
            imgs = get_images(p)  # 一度だけ読む
            for _idx, im in enumerate(imgs, start=1):
                label = f"{orig}"  # ファイル名のみ
                items.append((label, im))
        return items

    groupA = load_group(files_a_paths, "A")
    groupB = load_group(files_b_paths, "B")

    pagesA = [im for (_, im) in groupA]
    pagesB = [im for (_, im) in groupB]

    if len(pagesA) == 0 and len(pagesB) == 0:
        print("エラー: 画像ファイルの読み込みに問題が発生しました。", file=sys.stderr)
        sys.stdout.flush()
        return jsonify({"error": "画像ファイルの読み込みに問題が発生しました。"}), 500

    if len(pagesA) == 0:
        for j, (labelB, imB) in enumerate(groupB):
            results.append({
                "filename": labelB,
                "status": "added",
                "originalA": "",
                "originalB": image_to_base64(imB),
                "diffImage": None,
                "difference_percentage": 0.0
            })
        end_time = time.time()
        elapsed_time = end_time - start_time
        print(f"すべての差分チェックが完了しました。所要時間: {elapsed_time:.2f}秒")
        sys.stdout.flush()
        return jsonify({"results": results})

    if len(pagesB) == 0:
        for i, (labelA, imA) in enumerate(groupA):
            results.append({
                "filename": labelA,
                "status": "removed",
                "originalA": image_to_base64(imA),
                "originalB": "",
                "diffImage": None,
                "difference_percentage": 0.0
            })
        end_time = time.time()
        elapsed_time = end_time - start_time
        print(f"すべての差分チェックが完了しました。所要時間: {elapsed_time:.2f}秒")
        sys.stdout.flush()
        return jsonify({"results": results})

    # 進捗ログ：コスト行列
    print(f"[Rare] Building cost matrix... A:{len(pagesA)} pages, B:{len(pagesB)} pages")
    sys.stdout.flush()
    C = _build_cost_matrix(pagesA, pagesB, hash_size=32, down=256, w_hash=0.5, w_ssim=0.5, diag_bias=0.01)
    print(f"[Rare] Cost matrix built: shape={C.shape}")
    sys.stdout.flush()

    # アライメント
    print("[Rare] Aligning (affine-gap DP)...")
    sys.stdout.flush()
    # ページ数が極端に多い場合は band を適宜広げる/狭めるとパフォーマンス調整可能
    pairs = _align_affine(C, gap_open=0.15, gap_extend=0.02, band=10)
    print(f"[Rare] Alignment done. pairs={len(pairs)}")
    sys.stdout.flush()

    # ペアごとの進捗
    total_pairs = len(pairs)
    for idx, pair in enumerate(pairs, start=1):
        ai, bj = pair
        if ai is None and bj is not None:
            labelB, imB = groupB[bj]
            status = "added"
            diff_percentage = 0.0
            results.append({
                "filename": labelB,
                "status": status,
                "originalA": "",
                "originalB": image_to_base64(imB),
                "diffImage": None,
                "difference_percentage": 0.0
            })
        elif bj is None and ai is not None:
            labelA, imA = groupA[ai]
            status = "removed"
            diff_percentage = 0.0
            results.append({
                "filename": labelA,
                "status": status,
                "originalA": image_to_base64(imA),
                "originalB": "",
                "diffImage": None,
                "difference_percentage": 0.0
            })
        else:
            labelA, imA = groupA[ai]
            labelB, imB = groupB[bj]
            diff_img, is_changed, diff_percentage = get_diff_image(imA, imB)
            status = "changed" if is_changed else "unchanged"
            results.append({
                "filename": f"{labelA} ↔ {labelB}",
                "status": status,
                "originalA": image_to_base64(imA),
                "originalB": image_to_base64(imB),
                "diffImage": image_to_base64(diff_img) if is_changed else None,
                "difference_percentage": diff_percentage
            })

        left = ("" if ai is None else groupA[ai][0])
        right = ("" if bj is None else groupB[bj][0])
        print(f"[Rare] Progress {idx}/{total_pairs} : {status}  {left}  ↔  {right} | diff={diff_percentage:.6f}%")
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
            return jsonify({"message": f"Session {session_id} cleared."}), 200
        except OSError as e:
            print(f"Error clearing session {session_id}: {e}", file=sys.stderr)
            return jsonify({"error": "Failed to clear session"}), 500
    return jsonify({"message": "Session not found."}), 404

if __name__ == '__main__':
    # 本番では debug=False 推奨
    app.run(debug=True)
