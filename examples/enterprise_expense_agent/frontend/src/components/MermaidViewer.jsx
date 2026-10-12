import React, { useEffect, useRef, useState } from 'react';
import mermaid from 'mermaid';

// 初始化 Mermaid 配置，使用 base 主题与精细暗色变量
mermaid.initialize({
  startOnLoad: false,
  theme: 'base',
  themeVariables: {
    darkMode: true,
    background: '#090d16',
    mainBkg: '#1e293b',
    nodeBorder: '#0284c7',
    nodeTextColor: '#f8fafc',
    primaryColor: '#1e293b',
    primaryTextColor: '#f8fafc',
    primaryBorderColor: '#0284c7',
    lineColor: '#64748b',
    secondaryColor: '#0f172a',
    secondaryTextColor: '#94a3b8',
    secondaryBorderColor: '#475569',
    tertiaryColor: '#1e1b4b',
    tertiaryTextColor: '#e9d5ff',
    tertiaryBorderColor: '#a855f7',
    fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace',
    fontSize: '12px',
  },
  securityLevel: 'loose',
  flowchart: {
    htmlLabels: true,
    curve: 'linear',
    useMaxWidth: true,
  },
});

function prepareLangGraphMermaid(chartStr) {
  if (!chartStr || typeof chartStr !== 'string') return '';
  let str = chartStr.trim();

  // 1. 去除 LangGraph 导出的 <p> 标签，避免 foreignObject 样式污染
  str = str.replace(/<p>(.*?)<\/p>/gi, '$1');

  // 2. 清洗掉 LangGraph 原生写死的浅色 classDef 规则 (比如 fill:#f2f0ff, fill:#bfb6fc 等)
  str = str.replace(/classDef\s+[^\n;]+;?/g, '');

  // 3. 注入针对深色界面的标准高对比度 classDef 规则
  const darkThemeClassDefs = [
    'classDef default fill:#1e293b,stroke:#0284c7,stroke-width:1.5px,color:#f8fafc;',
    'classDef first fill:#0f172a,stroke:#475569,stroke-width:1.5px,color:#94a3b8;',
    'classDef last fill:#1e1b4b,stroke:#a855f7,stroke-width:1.5px,color:#e9d5ff;'
  ].join('\n');

  return str.trim() + '\n' + darkThemeClassDefs;
}

export function MermaidViewer({ chart, className = '' }) {
  const containerRef = useRef(null);
  const [svgContent, setSvgContent] = useState('');
  const [error, setError] = useState(null);
  const [viewMode, setViewMode] = useState('diagram'); // 'diagram' | 'source'

  useEffect(() => {
    if (!chart || typeof chart !== 'string' || !chart.trim()) {
      setSvgContent('');
      setError(null);
      return;
    }

    let isMounted = true;
    const uniqueId = `mermaid-${Math.random().toString(36).substring(2, 9)}`;

    // 对 LangGraph 拓扑图执行暗黑模式适配
    const cleanChart = prepareLangGraphMermaid(chart);

    async function renderChart() {
      try {
        setError(null);
        const { svg } = await mermaid.render(uniqueId, cleanChart);
        if (isMounted) {
          setSvgContent(svg);
        }
      } catch (err) {
        console.error('Mermaid render error:', err);
        if (isMounted) {
          setError(err?.message || 'Mermaid 语法解析失败');
        }
      }
    }

    renderChart();

    return () => {
      isMounted = false;
      const tempElement = document.getElementById(uniqueId);
      if (tempElement) {
        tempElement.remove();
      }
    };
  }, [chart]);

  return (
    <div className={`mermaid-viewer ${className}`} style={{ marginTop: '8px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
        <span style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>
          {viewMode === 'diagram' ? '交互式拓扑矢量图 (SVG)' : 'Mermaid DSL 原始定义'}
        </span>
        <div style={{ display: 'flex', gap: '6px' }}>
          <button
            type="button"
            className={`btn-small ${viewMode === 'diagram' ? 'btn-small-active' : ''}`}
            style={{ fontSize: '0.74rem', padding: '3px 8px' }}
            onClick={() => setViewMode('diagram')}
          >
            矢量图渲染
          </button>
          <button
            type="button"
            className={`btn-small ${viewMode === 'source' ? 'btn-small-active' : ''}`}
            style={{ fontSize: '0.74rem', padding: '3px 8px' }}
            onClick={() => setViewMode('source')}
          >
            查看源码
          </button>
        </div>
      </div>

      {viewMode === 'source' || error ? (
        <div className="terminal-window" style={{ maxHeight: '360px', overflowY: 'auto' }}>
          {error && (
            <div style={{ color: '#ef4444', fontSize: '0.75rem', marginBottom: '8px' }}>
              渲染遇到提示：{error}，已自动展示源码模式：
            </div>
          )}
          <pre style={{ color: '#94a3b8', fontSize: '0.74rem', whiteSpace: 'pre-wrap', margin: 0 }}>
            {chart}
          </pre>
        </div>
      ) : (
        <div
          ref={containerRef}
          className="mermaid-svg-container"
          style={{
            background: 'rgba(15, 23, 42, 0.75)',
            border: '1px solid var(--border-color)',
            borderRadius: '8px',
            padding: '16px',
            overflowX: 'auto',
            minHeight: '200px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
          dangerouslySetInnerHTML={{ __html: svgContent || '<div style="color: var(--text-muted); font-size: 0.8rem;">正在渲染状态机拓扑...</div>' }}
        />
      )}
    </div>
  );
}
