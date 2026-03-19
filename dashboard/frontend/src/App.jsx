import React, { useState, useEffect } from 'react';
import Overview from './pages/Overview';
import Violations from './pages/Violations';
import AuditLog from './pages/AuditLog';
import Rulesets from './pages/Rulesets';

const API_BASE = 'http://localhost:8000';

const TABS = [
    { id: 'overview', label: 'Overview', icon: '📊' },
    { id: 'violations', label: 'Violations', icon: '🚫' },
    { id: 'audit', label: 'Audit Log', icon: '📋' },
    { id: 'rulesets', label: 'Rulesets', icon: '📜' },
];

export default function App() {
    const [activeTab, setActiveTab] = useState('overview');
    const [health, setHealth] = useState(null);

    useEffect(() => {
        fetch(`${API_BASE}/health`)
            .then(res => res.json())
            .then(data => setHealth(data))
            .catch(() => setHealth({ status: 'unreachable' }));
    }, []);

    return (
        <div style={{ fontFamily: 'Inter, system-ui, sans-serif', background: '#0f172a', minHeight: '100vh', color: '#e2e8f0' }}>
            {/* Header */}
            <header style={{ background: '#1e293b', borderBottom: '1px solid #334155', padding: '16px 24px', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                    <span style={{ fontSize: '24px' }}>🛡️</span>
                    <h1 style={{ fontSize: '20px', fontWeight: 700, margin: 0, background: 'linear-gradient(135deg, #3b82f6, #8b5cf6)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
                        Ironpass
                    </h1>
                    <span style={{ fontSize: '12px', background: '#334155', padding: '2px 8px', borderRadius: '4px', color: '#94a3b8' }}>
                        v0.1.0
                    </span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: health?.status === 'healthy' ? '#22c55e' : '#ef4444' }}></span>
                    <span style={{ fontSize: '13px', color: '#94a3b8' }}>{health?.status || 'connecting...'}</span>
                </div>
            </header>

            {/* Navigation */}
            <nav style={{ background: '#1e293b', padding: '0 24px', display: 'flex', gap: '4px', borderBottom: '1px solid #334155' }}>
                {TABS.map(tab => (
                    <button
                        key={tab.id}
                        onClick={() => setActiveTab(tab.id)}
                        style={{
                            padding: '12px 16px',
                            background: 'none',
                            border: 'none',
                            color: activeTab === tab.id ? '#3b82f6' : '#94a3b8',
                            cursor: 'pointer',
                            fontSize: '14px',
                            fontWeight: activeTab === tab.id ? 600 : 400,
                            borderBottom: activeTab === tab.id ? '2px solid #3b82f6' : '2px solid transparent',
                            transition: 'all 0.2s',
                        }}
                    >
                        {tab.icon} {tab.label}
                    </button>
                ))}
            </nav>

            {/* Content */}
            <main style={{ padding: '24px', maxWidth: '1200px', margin: '0 auto' }}>
                {activeTab === 'overview' && <Overview apiBase={API_BASE} />}
                {activeTab === 'violations' && <Violations apiBase={API_BASE} />}
                {activeTab === 'audit' && <AuditLog apiBase={API_BASE} />}
                {activeTab === 'rulesets' && <Rulesets apiBase={API_BASE} />}
            </main>
        </div>
    );
}
