import React, { useState, useEffect } from 'react';

const CARD_STYLE = {
    background: '#1e293b',
    borderRadius: '12px',
    padding: '20px',
    border: '1px solid #334155',
};

export default function Overview({ apiBase }) {
    const [stats, setStats] = useState(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        fetch(`${apiBase}/dashboard/overview`)
            .then(res => res.json())
            .then(data => { setStats(data); setLoading(false); })
            .catch(() => setLoading(false));
    }, [apiBase]);

    if (loading) return <div style={{ textAlign: 'center', padding: '40px', color: '#94a3b8' }}>Loading...</div>;
    if (!stats) return <div style={{ textAlign: 'center', padding: '40px', color: '#ef4444' }}>Failed to load — is the database running?</div>;

    const cards = [
        { label: 'Total Requests', value: stats.total_requests, icon: '📡', color: '#3b82f6' },
        { label: 'Blocked', value: stats.total_blocked, icon: '🚫', color: '#ef4444' },
        { label: 'Last 24h', value: stats.requests_24h, icon: '⏱️', color: '#8b5cf6' },
        { label: 'Block Rate', value: `${stats.block_rate}%`, icon: '📊', color: '#f59e0b' },
        { label: 'Vault Tokens', value: stats.active_vault_tokens, icon: '🔐', color: '#22c55e' },
        { label: 'Avg Latency', value: `${stats.avg_latency_ms}ms`, icon: '⚡', color: '#06b6d4' },
    ];

    return (
        <div>
            <h2 style={{ fontSize: '18px', fontWeight: 600, marginBottom: '20px' }}>Overview</h2>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '16px' }}>
                {cards.map(card => (
                    <div key={card.label} style={CARD_STYLE}>
                        <div style={{ fontSize: '24px', marginBottom: '8px' }}>{card.icon}</div>
                        <div style={{ fontSize: '28px', fontWeight: 700, color: card.color }}>{card.value}</div>
                        <div style={{ fontSize: '13px', color: '#94a3b8', marginTop: '4px' }}>{card.label}</div>
                    </div>
                ))}
            </div>
        </div>
    );
}
