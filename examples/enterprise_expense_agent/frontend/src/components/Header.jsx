import React, { useState } from 'react';
import { useExpenseStore } from '../store/useExpenseStore';

export function Header() {
  const backendUrl = useExpenseStore((state) => state.backendUrl);
  const setBackendUrl = useExpenseStore((state) => state.setBackendUrl);
  const isConnected = useExpenseStore((state) => state.isConnected);
  const engineInfo = useExpenseStore((state) => state.engineInfo);

  const [inputUrl, setInputUrl] = useState(backendUrl);

  const handleUrlBlur = () => {
    if (inputUrl !== backendUrl) {
      setBackendUrl(inputUrl);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter') {
      handleUrlBlur();
    }
  };

  return (
    <header className="app-header">
      <div className="brand-section">
        <div className="logo-icon">E</div>
        <div>
          <div className="app-title">Enterprise Expense Agent</div>
          <div className="app-subtitle">LangGraph 生产级状态机 · React 状态脚手架控制台</div>
        </div>
      </div>
      <div className="header-status">
        <div className="backend-url-wrap">
          <span>后端 API:</span>
          <input
            id="backendUrlInput"
            type="text"
            value={inputUrl}
            onChange={(e) => setInputUrl(e.target.value)}
            onBlur={handleUrlBlur}
            onKeyDown={handleKeyDown}
          />
        </div>
        <div
          id="connectionStatus"
          className={`status-indicator ${isConnected ? '' : 'offline'}`}
          title={engineInfo}
        >
          <span className="status-dot"></span>
          <span>{isConnected ? `在线 (${engineInfo.split(' ')[0]})` : '未连接 (请启动 server.py)'}</span>
        </div>
      </div>
    </header>
  );
}
