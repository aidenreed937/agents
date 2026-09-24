import React, { useEffect, useRef } from 'react';
import { useExpenseStore } from '../../store/useExpenseStore';

export function LiveTerminal() {
  const logs = useExpenseStore((state) => state.logs);
  const terminalRef = useRef(null);

  useEffect(() => {
    if (terminalRef.current) {
      terminalRef.current.scrollTop = terminalRef.current.scrollHeight;
    }
  }, [logs]);

  return (
    <div className="terminal-window" id="terminalLog" ref={terminalRef}>
      {logs.map((log) => {
        let textCls = '';
        if (log.type === 'highlight') textCls = 'log-text-highlight';
        if (log.type === 'warn') textCls = 'log-text-warn';
        if (log.type === 'danger') textCls = 'log-text-danger';

        return (
          <div key={log.id} className="log-entry">
            <span className="log-time">[{log.time}]</span>
            <span className="log-node">&lt;{log.node}&gt;</span>
            <span className={textCls}>{log.text}</span>
          </div>
        );
      })}
    </div>
  );
}
