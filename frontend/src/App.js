import React, { useState } from 'react';
import axios from 'axios';
import './App.css';

// eslint-disable-next-line no-unused-vars
const API_BASE_URL = process.env.REACT_APP_API_BASE_URL || 'http://127.0.0.1:5000';

function App() {
  const [fileA, setFileA] = useState(null);
  const [fileB, setFileB] = useState(null);
  const [filesA, setFilesA] = useState([]);
  const [filesB, setFilesB] = useState([]);
  
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [status, setStatus] = useState('');
  const [pageInfo, setPageInfo] = useState(null);
  const [sessionId, setSessionId] = useState(null);
  const [currentImageIndex, setCurrentImageIndex] = useState({});
  const [isDiffModeEnabled, setIsDiffModeEnabled] = useState(true);

  // ドラッグ＆ドロップ関連のstate
  const [isDraggingA, setIsDraggingA] = useState(false);
  const [isDraggingB, setIsDraggingB] = useState(false);
  const [isDraggingFilesA, setIsDraggingFilesA] = useState(false);
  const [isDraggingFilesB, setIsDraggingFilesB] = useState(false);
  
  const handleFileChange = (e) => {
    if (e.target.name === 'fileA') {
      setFileA(e.target.files[0]);
    } else {
      setFileB(e.target.files[0]);
    }
  };

  const handleFilesChange = (e) => {
    if (e.target.name === 'filesA') {
      setFilesA(e.target.files);
    } else {
      setFilesB(e.target.files);
    }
  };

  const handleNormalDiffCheck = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setResult(null);
    setPageInfo(null);
    setSessionId(null);
    setCurrentImageIndex({});

    if (!fileA || !fileB) {
      setError('両方のファイルをアップロードしてください。');
      setLoading(false);
      return;
    }

    setStatus('差分チェックを開始します...');

    const formData = new FormData();
    formData.append('filesA', fileA);
    formData.append('filesB', fileB);

    try {
      const response = await axios.post(`${API_BASE_URL}/api/check_pages`, formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });
      const currentSessionId = response.data.sessionId;
      setSessionId(currentSessionId);
      
      const diffResponse = await axios.get(`${API_BASE_URL}/api/diff/${currentSessionId}`);
      setResult(diffResponse.data);
      setStatus('差分チェックが完了しました。');
    } catch (err) {
      setError('差分チェック中にエラーが発生しました。');
      console.error(err);
      setStatus('');
    } finally {
      setLoading(false);
    }
  };

  const handleRareCaseCheckPages = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setResult(null);
    setPageInfo(null);
    setSessionId(null);
    setCurrentImageIndex({});

    if (filesA.length === 0 || filesB.length === 0) {
      setError('両方のファイルグループをアップロードしてください。');
      setLoading(false);
      return;
    }

    setStatus('ページリストを取得中...');

    const formData = new FormData();
    for (let i = 0; i < filesA.length; i++) {
      formData.append('filesA', filesA[i]);
    }
    for (let i = 0; i < filesB.length; i++) {
      formData.append('filesB', filesB[i]);
    }

    try {
      const response = await axios.post(`${API_BASE_URL}/api/check_pages`, formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });
      setSessionId(response.data.sessionId);
      setPageInfo(response.data);
      setStatus('ページリストの確認が完了しました。');
    } catch (err) {
      setError('ページチェック中にエラーが発生しました。');
      console.error(err);
      setStatus('');
    } finally {
      setLoading(false);
    }
  };

  const handleRareCaseDiffCheck = async () => {
    setLoading(true);
    setError(null);
    setStatus('差分チェックを開始します...');
    
    try {
      const response = await axios.get(`${API_BASE_URL}/api/diff/${sessionId}`);
      setResult(response.data);
      setStatus('差分チェックが完了しました。');
    } catch (err) {
      setError('差分チェック中にエラーが発生しました。');
      console.error(err);
      setStatus('');
    } finally {
      setLoading(false);
    }
  };

  const handleReset = async () => {
    // 既存のセッションIDがあればバックエンドに削除リクエストを送る
    if (sessionId) {
      try {
        await axios.post(`${API_BASE_URL}/api/clear_session/${sessionId}`);
      } catch (error) {
        console.error('Error clearing session:', error);
      }
    }
    setFileA(null);
    setFileB(null);
    setFilesA([]);
    setFilesB([]);
    setResult(null);
    setLoading(false);
    setError(null);
    setStatus('');
    setPageInfo(null);
    setSessionId(null);
    setCurrentImageIndex({});
    setIsDiffModeEnabled(true);
  };
  
  const handleFileAReset = () => {
    setFileA(null);
  };

  const handleFileBReset = () => {
    setFileB(null);
  };
  
  const handleFilesAReset = () => {
    setFilesA([]);
  };
  
  const handleFilesBReset = () => {
    setFilesB([]);
  };

  const handleImageClick = (filename) => {
    setCurrentImageIndex(prevState => {
      const currentIndex = prevState[filename] || 0;
      let nextIndex;
  
      if (isDiffModeEnabled) {
        // 差分表示モードが有効な場合: 差分画像(0) -> ファイルA(1) -> ファイルB(2) の順
        nextIndex = (currentIndex + 1) % 3;
      } else {
        // 差分表示モードが無効な場合: ファイルA(1) -> ファイルB(2) の順
        // 現在のインデックスが差分画像(0)の場合はファイルA(1)に移動
        if (currentIndex === 0 || currentIndex === 2) {
          nextIndex = 1;
        } else {
          nextIndex = 2;
        }
      }
      return { ...prevState, [filename]: nextIndex };
    });
  };

  const getDisplayImageInfo = (pageResult, index) => {
    const currentIndex = index || 0;

    // 差分がない場合は常に「差分なし」メッセージ
    if (pageResult.diffImage === null && pageResult.status === 'unchanged') {
        return { src: null, name: '差分なし' };
    }

    if (isDiffModeEnabled) {
        // 差分モードON
        switch (currentIndex) {
            case 0:
                return { src: pageResult.diffImage, name: '差分画像' };
            case 1:
                return { src: pageResult.originalA, name: 'ファイルA' };
            case 2:
                return { src: pageResult.originalB, name: 'ファイルB' };
            default:
                return { src: pageResult.diffImage, name: '差分画像' };
        }
    } else {
        // 差分モードOFF
        switch (currentIndex) {
            case 1:
                return { src: pageResult.originalA, name: 'ファイルA' };
            case 2:
                return { src: pageResult.originalB, name: 'ファイルB' };
            default: // Index 0の場合はファイルAを表示
                return { src: pageResult.originalA, name: 'ファイルA' };
        }
    }
  };

  // ドラッグ＆ドロップイベントハンドラ (通常チェック)
  const handleDragOver = (e) => {
    e.preventDefault();
    if (e.currentTarget.dataset.name === 'fileA') {
      setIsDraggingA(true);
    } else {
      setIsDraggingB(true);
    }
  };

  const handleDragLeave = (e) => {
    e.preventDefault();
    if (e.currentTarget.dataset.name === 'fileA') {
      setIsDraggingA(false);
    } else {
      setIsDraggingB(false);
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    if (e.currentTarget.dataset.name === 'fileA') {
      setFileA(e.dataTransfer.files[0]);
      setIsDraggingA(false);
    } else {
      setFileB(e.dataTransfer.files[0]);
      setIsDraggingB(false);
    }
  };
  
  // ドラッグ＆ドロップイベントハンドラ (レアケースチェック)
  const handleFilesDragOver = (e) => {
    e.preventDefault();
    if (e.currentTarget.dataset.name === 'filesA') {
      setIsDraggingFilesA(true);
    } else {
      setIsDraggingFilesB(true);
    }
  };

  const handleFilesDragLeave = (e) => {
    e.preventDefault();
    if (e.currentTarget.dataset.name === 'filesA') {
      setIsDraggingFilesA(false);
    } else {
      setIsDraggingFilesB(false);
    }
  };
  
  const handleFilesDrop = (e) => {
    e.preventDefault();
    if (e.currentTarget.dataset.name === 'filesA') {
      setFilesA(e.dataTransfer.files);
      setIsDraggingFilesA(false);
    } else {
      setFilesB(e.dataTransfer.files);
      setIsDraggingFilesB(false);
    }
  };

  // 数値を考慮した自然順ソート（"p9" < "p10" などを正しく）
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

  return (
    <div className="App">
      <header className="App-header">
        <h1>画像差分チェッカー</h1>
        
        {/* 通常チェック用フォーム */}
        {!pageInfo && filesA.length === 0 && filesB.length === 0 && (
          <form onSubmit={handleNormalDiffCheck}>
            <h3>📄 通常チェック (複数ページPDF)</h3>
            <div className="file-input-container">
              <label htmlFor="fileA">ファイルA:</label>
              <div
                className={`drop-area ${isDraggingA ? 'dragging' : ''}`}
                onDragOver={handleDragOver}
                onDragLeave={handleDragLeave}
                onDrop={handleDrop}
                data-name="fileA"
              >
                <input id="fileA" type="file" name="fileA" onChange={handleFileChange} className="hidden-input" />
                {fileA ? (
                  <p>{fileA.name}</p>
                ) : (
                  <p>ここにファイルをドラッグ＆ドロップ</p>
                )}
              </div>
              <label htmlFor="fileA" className="custom-file-upload">
                ファイルを選択
              </label>
              {fileA && (
                <button type="button" onClick={handleFileAReset} className="cancel-button">
                  キャンセル
                </button>
              )}
            </div>
            <div className="file-input-container">
              <label htmlFor="fileB">ファイルB:</label>
              <div
                className={`drop-area ${isDraggingB ? 'dragging' : ''}`}
                onDragOver={handleDragOver}
                onDragLeave={handleDragLeave}
                onDrop={handleDrop}
                data-name="fileB"
              >
                <input id="fileB" type="file" name="fileB" onChange={handleFileChange} className="hidden-input" />
                {fileB ? (
                  <p>{fileB.name}</p>
                ) : (
                  <p>ここにファイルをドラッグ＆ドロップ</p>
                )}
              </div><label htmlFor="fileB" className="custom-file-upload">
                ファイルを選択
              </label>
              {fileB && (
                <button type="button" onClick={handleFileBReset} className="cancel-button">
                  キャンセル
                </button>
              )}
            </div>
            <button type="submit" disabled={loading || !fileA || !fileB}>
              {loading ? '処理中...' : '差分チェック開始'}
            </button>
          </form>
        )}
        
        {/* レアケースチェック用フォーム */}
        {!pageInfo && !fileA && !fileB && (
          <form onSubmit={handleRareCaseCheckPages}>
            <hr />
            <h3>📁 レアケースチェック (複数ファイル)</h3>
            <div className="file-input-container">
              <label htmlFor="filesA">ファイルAグループ:</label>
              <div
                className={`drop-area ${isDraggingFilesA ? 'dragging' : ''}`}
                onDragOver={handleFilesDragOver}
                onDragLeave={handleFilesDragLeave}
                onDrop={handleFilesDrop}
                data-name="filesA"
              >
                <input id="filesA" type="file" name="filesA" multiple onChange={handleFilesChange} className="hidden-input" />
                {filesA.length > 0 ? (
                  <p>{filesA.length} 個のファイルが選択されました</p>
                ) : (
                  <p>ここにファイルをドラッグ＆ドロップ</p>
                )}
              </div>
              <label htmlFor="filesA" className="custom-file-upload">
                ファイルを選択
              </label>
              {filesA.length > 0 && (
                <button type="button" onClick={handleFilesAReset} className="cancel-button">
                  キャンセル
                </button>
              )}
            </div>
            <div className="file-input-container">
              <label htmlFor="filesB">ファイルBグループ:</label>
              <div
                className={`drop-area ${isDraggingFilesB ? 'dragging' : ''}`}
                onDragOver={handleFilesDragOver}
                onDragLeave={handleFilesDragLeave}
                onDrop={handleFilesDrop}
                data-name="filesB"
              >
                <input id="filesB" type="file" name="filesB" multiple onChange={handleFilesChange} className="hidden-input" />
                {filesB.length > 0 ? (
                  <p>{filesB.length} 個のファイルが選択されました</p>
                ) : (
                  <p>ここにファイルをドラッグ＆ドロップ</p>
                )}
              </div>
              <label htmlFor="filesB" className="custom-file-upload">
                ファイルを選択
              </label>
              {filesB.length > 0 && (
                <button type="button" onClick={handleFilesBReset} className="cancel-button">
                  キャンセル
                </button>
              )}
            </div>
            <button type="submit" disabled={loading || filesA.length === 0 || filesB.length === 0}>
              {loading ? '処理中...' : 'ページチェック'}
            </button>
          </form>
        )}

        {/* レアケース用ページリスト */}
        {pageInfo && !result && (
          <div>
            <h2>アップロード確認</h2>
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
            <button onClick={handleRareCaseDiffCheck} disabled={loading}>
              {loading ? '処理中...' : '差分チェック開始'}
            </button>
            <button type="button" onClick={handleReset} className="cancel-button">
              キャンセル
            </button>
          </div>
        )}
        
        {status && <p className="status-message">{status}</p>}
        {error && <p className="error">{error}</p>}

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
                        <>
                          <img
                            src={displayInfo.src}
                            alt={`Comparison - ${pageResult.filename}`}
                            onClick={() => handleImageClick(pageResult.filename)}
                          />
                          {displayInfo.name === '差分画像' && (
                            <span className="diff-percentage">
                              差異の割合: {pageResult.difference_percentage.toFixed(4)}%
                            </span>
                          )}
                        </>
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
          <button onClick={handleReset}>新しいチェックを開始</button>
        </div>
      )}
      </header>
    </div>
  );
}

export default App;