import React, { useState } from 'react';
import axios from 'axios';
import './App.css';

// API ベースURL（環境変数が無ければローカル）
const API_BASE_URL = process.env.REACT_APP_API_BASE_URL || 'http://127.0.0.1:5000';

function App() {
  // A/B それぞれのアップロード（多ページ1本でも、単ページ複数でもOK）
  const [filesA, setFilesA] = useState([]);
  const [filesB, setFilesB] = useState([]);

  // バックエンド応答
  const [sessionId, setSessionId] = useState(null);
  const [pageInfo, setPageInfo] = useState(null);   // 確認ビュー用（件数・ファイル名リストなど）
  const [result, setResult] = useState(null);       // 差分結果

  // UI 状態
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState('');
  const [error, setError] = useState(null);
  const [isDraggingA, setIsDraggingA] = useState(false);
  const [isDraggingB, setIsDraggingB] = useState(false);

  // 画像切替（差分→A→B）
  const [currentImageIndex, setCurrentImageIndex] = useState({});
  const [isDiffModeEnabled, setIsDiffModeEnabled] = useState(true);

  // 数値を考慮した自然順ソート（"p9" < "p10"）
  const naturalCompare = (a, b) => {
    const ax = a.toLowerCase().split(/(\d+)/).map(s => (/\d+/.test(s) ? Number(s) : s));
    const bx = b.toLowerCase().split(/(\d+)/).map(s => (/\d+/.test(s) ? Number(s) : s));
    for (let i = 0; i < Math.max(ax.length, bx.length); i++) {
      if (ax[i] === undefined) return -1;
      if (bx[i] === undefined) return 1;
      if (ax[i] === bx[i]) continue;
      return ax[i] < bx[i] ? -1 : 1;
    }
    return 0;
  };

  /* ===== ドロップ/選択（A） ===== */
  const handleFilesAChange = (e) => setFilesA(Array.from(e.target.files || []));
  const handleDragOverA = (e) => { e.preventDefault(); setIsDraggingA(true); };
  const handleDragLeaveA = (e) => { e.preventDefault(); setIsDraggingA(false); };
  const handleDropA = (e) => {
    e.preventDefault();
    const dropped = Array.from(e.dataTransfer.files || []);
    setFilesA(dropped);
    setIsDraggingA(false);
  };

  /* ===== ドロップ/選択（B） ===== */
  const handleFilesBChange = (e) => setFilesB(Array.from(e.target.files || []));
  const handleDragOverB = (e) => { e.preventDefault(); setIsDraggingB(true); };
  const handleDragLeaveB = (e) => { e.preventDefault(); setIsDraggingB(false); };
  const handleDropB = (e) => {
    e.preventDefault();
    const dropped = Array.from(e.dataTransfer.files || []);
    setFilesB(dropped);
    setIsDraggingB(false);
  };

  // アップロード確認（ページ情報取得）— レアケース統一
  const handleCheckPages = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setStatus('ページリストを取得中...');
    setPageInfo(null);
    setResult(null);
    setSessionId(null);
    setCurrentImageIndex({});

    if ((!filesA || filesA.length === 0) && (!filesB || filesB.length === 0)) {
      setError('AかBのどちらかにファイルをアップロードしてください。');
      setStatus('');
      setLoading(false);
      return;
    }

    try {
      const formData = new FormData();
      filesA.forEach((f) => formData.append('filesA', f));
      filesB.forEach((f) => formData.append('filesB', f));

      const response = await axios.post(`${API_BASE_URL}/api/check_pages`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });

      setSessionId(response.data.sessionId);
      setPageInfo(response.data);
      setStatus('アップロード確認が完了しました。');
    } catch (err) {
      console.error(err);
      setError('ページチェック中にエラーが発生しました。');
      setStatus('');
    } finally {
      setLoading(false);
    }
  };

  // 差分チェック開始（常に Rare / アライメント方式）
  const handleRunDiff = async () => {
    if (!sessionId) return;
    setLoading(true);
    setError(null);
    setStatus('差分チェックを開始します...');
    try {
      const diffResponse = await axios.get(`${API_BASE_URL}/api/diff/${sessionId}`);
      setResult(diffResponse.data);
      setStatus('差分チェックが完了しました。');
      window.scrollTo({ top: 0, behavior: 'smooth' });
    } catch (err) {
      console.error(err);
      setError('差分チェック中にエラーが発生しました。');
      setStatus('');
    } finally {
      setLoading(false);
    }
  };

  // リセット（サーバの一時ファイルも削除）
  const handleReset = async () => {
    if (sessionId) {
      try {
        await axios.post(`${API_BASE_URL}/api/clear_session/${sessionId}`);
      } catch (error) {
        console.error('Error clearing session:', error);
      }
    }
    setFilesA([]);
    setFilesB([]);
    setSessionId(null);
    setPageInfo(null);
    setResult(null);
    setLoading(false);
    setError(null);
    setStatus('');
    setCurrentImageIndex({});
    setIsDiffModeEnabled(true);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  // 画像クリックで表示切替
  const handleImageClick = (filename) => {
    setCurrentImageIndex(prev => {
      const currentIndex = prev[filename] || 0;
      let nextIndex;
      if (isDiffModeEnabled) {
        // 差分画像(0) -> A(1) -> B(2)
        nextIndex = (currentIndex + 1) % 3;
      } else {
        // 差分非表示: A(1) <-> B(2)
        if (currentIndex === 0 || currentIndex === 2) nextIndex = 1;
        else nextIndex = 2;
      }
      return { ...prev, [filename]: nextIndex };
    });
  };

  // 表示する画像の選択
  const getDisplayImageInfo = (pageResult, index) => {
    const currentIndex = index || 0;
    if (pageResult.diffImage === null && pageResult.status === 'unchanged') {
      return { src: null, name: '差分なし' };
    }
    if (isDiffModeEnabled) {
      switch (currentIndex) {
        case 0: return { src: pageResult.diffImage, name: '差分画像' };
        case 1: return { src: pageResult.originalA, name: 'ファイルA' };
        case 2: return { src: pageResult.originalB, name: 'ファイルB' };
        default: return { src: pageResult.diffImage, name: '差分画像' };
      }
    } else {
      switch (currentIndex) {
        case 1: return { src: pageResult.originalA, name: 'ファイルA' };
        case 2: return { src: pageResult.originalB, name: 'ファイルB' };
        default: return { src: pageResult.originalA, name: 'ファイルA' };
      }
    }
  };

  return (
    <div className="App">
      <header className="App-header">
        <h1>画像差分チェッカー</h1>

        {/* A/B 2ドロップゾーン（多ページPDF/単ページ複数の両対応） */}
        {!pageInfo && !result && (
          <form onSubmit={handleCheckPages}>
            <h3>📂 ファイルをアップロードしてください</h3>

            <div className="file-input-container">
              <div
                className={`drop-area ${isDraggingA ? 'dragging' : ''}`}
                onDragOver={handleDragOverA}
                onDragLeave={handleDragLeaveA}
                onDrop={handleDropA}
              >
                <input
                  id="filesA"
                  type="file"
                  name="filesA"
                  multiple
                  onChange={handleFilesAChange}
                  className="hidden-input"
                />
                {filesA.length > 0 ? (
                  <p>Aグループ：{filesA.length} 個のファイルが選択されました</p>
                ) : (
                  <p>ここにファイルをドラッグ（A：多ページPDF1本 もしくは 単ページ複数）</p>
                )}
              </div>
              <label htmlFor="filesA" className="custom-file-upload">Aグループを選択</label>
            </div>

            <div className="file-input-container" style={{ marginTop: 12 }}>
              <div
                className={`drop-area ${isDraggingB ? 'dragging' : ''}`}
                onDragOver={handleDragOverB}
                onDragLeave={handleDragLeaveB}
                onDrop={handleDropB}
              >
                <input
                  id="filesB"
                  type="file"
                  name="filesB"
                  multiple
                  onChange={handleFilesBChange}
                  className="hidden-input"
                />
                {filesB.length > 0 ? (
                  <p>Bグループ：{filesB.length} 個のファイルが選択されました</p>
                ) : (
                  <p>ここにファイルをドラッグ（B：多ページPDF1本 もしくは 単ページ複数）</p>
                )}
              </div>
              <label htmlFor="filesB" className="custom-file-upload">Bグループを選択</label>
            </div>

            <button type="submit" disabled={loading || (filesA.length === 0 && filesB.length === 0)} style={{ marginTop: 14 }}>
              {loading ? '処理中...' : 'ページチェック'}
            </button>
          </form>
        )}

        {/* 確認ビュー（A/B 2列 + 件数 + 警告表示） */}
        {pageInfo && !result && (
          <div>
            <h2>アップロード確認</h2>

            {/* バリデーション警告（任意表示） */}
            {Array.isArray(pageInfo.uploadIssues) && pageInfo.uploadIssues.length > 0 && (
              <div className="error" style={{ textAlign: 'left' }}>
                <strong>⚠️ 注意:</strong>
                <ul style={{ marginTop: 8 }}>
                  {pageInfo.uploadIssues.map((msg, i) => <li key={`issue-${i}`}>{msg}</li>)}
                </ul>
              </div>
            )}

            <div className="page-check-container">
              <div className="page-check-group list-group-a">
                {(() => {
                  const namesA = (pageInfo.fileNamesA && pageInfo.fileNamesA.length
                    ? [...pageInfo.fileNamesA]
                    : (pageInfo.filesA || []).map(f => f.filename)
                  ).sort(naturalCompare);
                  const countA = typeof pageInfo.groupFileCountA === 'number' ? pageInfo.groupFileCountA : namesA.length;
                  return (
                    <>
                      <h3>ファイルAグループ（{countA}件）</h3>
                      <ul>
                        {namesA.length === 0 ? <li>---</li> : namesA.map((name, i) => <li key={`A-${i}`}>{name}</li>)}
                      </ul>
                    </>
                  );
                })()}
              </div>

              <div className="page-check-group list-group-b">
                {(() => {
                  const namesB = (pageInfo.fileNamesB && pageInfo.fileNamesB.length
                    ? [...pageInfo.fileNamesB]
                    : (pageInfo.filesB || []).map(f => f.filename)
                  ).sort(naturalCompare);
                  const countB = typeof pageInfo.groupFileCountB === 'number' ? pageInfo.groupFileCountB : namesB.length;
                  return (
                    <>
                      <h3>ファイルBグループ（{countB}件）</h3>
                      <ul>
                        {namesB.length === 0 ? <li>---</li> : namesB.map((name, i) => <li key={`B-${i}`}>{name}</li>)}
                      </ul>
                    </>
                  );
                })()}
              </div>
            </div>

            <button onClick={handleRunDiff} disabled={loading} style={{ marginTop: 8 }}>
              {loading ? '処理中...' : '差分チェック開始'}
            </button>
            <button type="button" onClick={handleReset} className="cancel-button" style={{ marginLeft: 8 }}>
              キャンセル
            </button>
          </div>
        )}

        {status && <p className="status-message">{status}</p>}
        {error && <p className="error">{error}</p>}

        {/* 差分結果 */}
        {result && result.results && (
          <div>
            <div className="results-container">
              {result.results.map((pageResult) => {
                const displayInfo = getDisplayImageInfo(pageResult, currentImageIndex[pageResult.filename]);
                return (
                  <div key={pageResult.filename} className="page-container">
                    <h2>{pageResult.filename}</h2>

                    <div className="image-set-container">
                      <div className="image-comparison-container">
                        <div className="image-pair">
                          <h3>ファイルA</h3>
                          {pageResult.originalA ? (
                            <img src={pageResult.originalA} alt={`Original A - ${pageResult.filename}`} />
                          ) : (
                            <span>---</span>
                          )}
                        </div>
                        <div className="image-pair">
                          <h3>ファイルB</h3>
                          {pageResult.originalB ? (
                            <img src={pageResult.originalB} alt={`Original B - ${pageResult.filename}`} />
                          ) : (
                            <span>---</span>
                          )}
                        </div>
                      </div>

                      <div className="image-pair diff-image-pair">
                        <div className="diff-header">
                          <h3 className={displayInfo.name === '差分画像' ? "diff-image-title" : ""}>
                            {displayInfo.name}
                            {displayInfo.name === '差分画像' && (
                              <span className="diff-percentage">
                                diff : {pageResult.difference_percentage.toFixed(4)}%
                              </span>
                            )}
                          </h3>
                          <label className="diff-mode-checkbox">
                            <input
                              type="checkbox"
                              checked={isDiffModeEnabled}
                              onChange={() => setIsDiffModeEnabled(!isDiffModeEnabled)}
                            />
                            差分画像を表示
                          </label>
                        </div>

                        {displayInfo.src ? (
                          <img
                            src={displayInfo.src}
                            alt={`Comparison - ${pageResult.filename}`}
                            onClick={() => handleImageClick(pageResult.filename)}
                          />
                        ) : (
                          <div className="no-diff-message">
                            <span>{displayInfo.name}</span>
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>

            <button onClick={handleReset} className="button-initialize">新しいチェックを開始</button>

            {/* === スクロールナビゲーションボタン === */}
            <div className="scroll-buttons">
              <button onClick={() => window.scrollTo({ top: 0, behavior: 'smooth' })}>
                ⬆ 先頭へ
              </button>
              <button onClick={() => window.scrollTo({ top: document.body.scrollHeight, behavior: 'smooth' })}>
                ⬇ 最下部へ
              </button>
            </div>
          </div>
        )}
      </header>
    </div>
  );
}

export default App;
