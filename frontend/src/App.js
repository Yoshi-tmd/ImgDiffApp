import React, { useState } from 'react';
import axios from 'axios';
import './App.css';

function App() {
  const [fileA, setFileA] = useState(null);
  const [fileB, setFileB] = useState(null);
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [status, setStatus] = useState('');
  const [pageInfo, setPageInfo] = useState(null);
  const [sessionId, setSessionId] = useState(null);
  const [currentImageIndex, setCurrentImageIndex] = useState({});

  const handleFileChange = (e) => {
    if (e.target.name === 'fileA') {
      setFileA(e.target.files[0]);
    } else {
      setFileB(e.target.files[0]);
    }
  };
  
const handlePageCheck = async (e) => {
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
    
    setStatus('ページリストを取得中...');

    const formData = new FormData();
    formData.append('fileA', fileA);
    formData.append('fileB', fileB);

    try {
        const response = await axios.post('http://127.0.0.1:5000/api/check_pages', formData, {
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

  const handleDiffCheck = async () => {
    setLoading(true);
    setError(null);
    setStatus('差分チェックを開始します...');
    
    try {
        const response = await axios.get(`http://127.0.0.1:5000/api/diff/${sessionId}`);
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

  const handleReset = () => {
    setFileA(null);
    setFileB(null);
    setResult(null);
    setLoading(false);
    setError(null);
    setStatus('');
    setPageInfo(null);
    setSessionId(null);
    setCurrentImageIndex({});
  };

  const handleImageClick = (pageNumber) => {
    setCurrentImageIndex(prevState => {
      const currentIndex = prevState[pageNumber] || 0;
      const nextIndex = (currentIndex + 1) % 3; // 0, 1, 2を循環
      return { ...prevState, [pageNumber]: nextIndex };
    });
  };

  const getImageSrc = (pageResult, index) => {
    switch (index) {
      case 0:
        return pageResult.diffImage || '';
      case 1:
        return pageResult.originalA || '';
      case 2:
        return pageResult.originalB || '';
      default:
        return pageResult.diffImage || '';
    }
  };

  const getImageName = (index) => {
    switch (index) {
      case 0:
        return '差分画像';
      case 1:
        return 'ファイルA';
      case 2:
        return 'ファイルB';
      default:
        return '差分画像';
    }
  };

  return (
    <div className="App">
      <header className="App-header">
        <h1>画像差分チェッカー</h1>
        {/* <--- ページリストを取得するためのフォーム --- > */}
        {!pageInfo && (
            <form onSubmit={handlePageCheck}>
                <div className="file-input-container">
                    <label htmlFor="fileA">ファイルA:</label>
                    <input type="file" name="fileA" onChange={handleFileChange} />
                </div>
                <div className="file-input-container">
                    <label htmlFor="fileB">ファイルB:</label>
                    <input type="file" name="fileB" onChange={handleFileChange} />
                </div>
                <button type="submit" disabled={loading}>
                    {loading ? '処理中...' : 'ページチェック'}
                </button>
            </form>
        )}
        
        {/* <--- ページリストと差分チェックボタン --- > */}
        {pageInfo && !result && (
            <div>
                <h2>ページリスト</h2>
                <div className="page-check-container">
                    <p>ファイルA: {pageInfo.lenA}ページ</p>
                    <p>ファイルB: {pageInfo.lenB}ページ</p>
                    {pageInfo.lenA !== pageInfo.lenB && (
                        <p className="warning">⚠️ ページ数が異なります！</p>
                    )}
                </div>
                <button onClick={handleDiffCheck} disabled={loading}>
                    {loading ? '処理中...' : '差分チェック開始'}
                </button>
            </div>
        )}
        
        {/* <--- ステータスとエラーの表示 --- > */}
        {status && <p className="status-message">{status}</p>}
        {error && <p className="error">{error}</p>}

        {result && result.results && (
          <div>
            <div className="results-container">
              {result.results.map((pageResult) => (
                <div key={pageResult.page} className="page-container">
                  <h2>ページ {pageResult.page}</h2>
                  <div className="image-set-container">
                    <div className="image-comparison-container">
                      <div className="image-pair">
                        <h3>ファイルA</h3>
                        <img src={pageResult.originalA || ''} alt={`Original A - Page ${pageResult.page}`} />
                      </div>
                      <div className="image-pair">
                        <h3>ファイルB</h3>
                        <img src={pageResult.originalB || ''} alt={`Original B - Page ${pageResult.page}`} />
                      </div>
                    </div>
                    <div className="image-pair">
                      <h3>{getImageName(currentImageIndex[pageResult.page] || 0)}</h3>
                      <img
                        src={getImageSrc(pageResult, currentImageIndex[pageResult.page] || 0)}
                        alt={`Difference - Page ${pageResult.page}`}
                        onClick={() => handleImageClick(pageResult.page)}
                      />
                    </div>
                  </div>
                </div>
              ))}
            </div>
            <button onClick={handleReset}>新しいチェックを開始</button>
          </div>
        )}
      </header>
    </div>
  );
}

export default App;