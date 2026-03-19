import React, { useState, useEffect } from 'react';

export default function AuditLog({ apiBase }) {
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(true);
    const [filter, setFilter] = useState('');

    const fetchData = (agentId) => {
        setLoading(true);
        const url = agentId
            ? `${apiBase}/dashboard/audit?limit=30&agent_id=${agentId}`
            : `${apiBase}/dashboard/audit?limit=30`;
        fetch(url)
            .then(res => res.json())
            .then(d => { setData(d); setLoading(false); })
            .catch(() => setLoading(false));
    };

    useEffect(() => { fetchData(filter || null); }, [apiBase, filter]);

    const OUTCOME_COLORS = { passed: '#22c55e', sanitized: '#f59e0b', blocked: '#ef4444', error: '#94a3b8' };

    return (
        <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
                <h2 style={{ fontSize: '18px', fontWeight: 600, margin: 0 }}>
                    Audit Log <span style={{ fontSize: '14px', color: '#94a3b8', fontWeight: 400 }}>({data?.total || 0} total)</span>
                </h2>
                <input
                    type="text"
                    placeholder="Filter by agent ID..."
                    value={filter}
                    onChange={e => setFilter(e.target.value)}
                    style={{ background: '#1e293b', border: '1px solid #334155', color: '#e2e8f0', padding: '8px 12px', borderRadius: '6px', fontSize: '13px', width: '220px' }}
                />
            </div>

            {loading && <div style={{ textAlign: 'center', padding: '40px', color: '#94a3b8' }}>Loading...</div>}

            {!loading && data && (
                <div style={{ overflowX: 'auto' }}>
                    <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px' }}>
                        <thead>
                            <tr style={{ borderBottom: '1px solid #334155' }}>
                                {['Time', 'Agent', 'Outcome', 'Detections', 'Actions', 'Latency', 'Rulesets'].map(h => (
                                    <th key={h} style={{ textAlign: 'left', padding: '10px 12px', color: '#94a3b8', fontWeight: 500 }}>{h}</th>
                                ))}
                            </tr>
                        </thead>
                        <tbody>
                            {data.entries.map(e => (
                                <tr key={e.entry_id} style={{ borderBottom: '1px solid #1e293b' }}>
                                    <td style={{ padding: '10px 12px', color: '#94a3b8' }}>{new Date(e.timestamp).toLocaleTimeString()}</td>
                                    <td style={{ padding: '10px 12px', fontWeight: 500 }}>{e.agent_id}</td>
                                    <td style={{ padding: '10px 12px' }}>
                                        <span style={{ color: OUTCOME_COLORS[e.outcome] || '#94a3b8', fontWeight: 600 }}>{e.outcome}</span>
                                    </td>
                                    <td style={{ padding: '10px 12px', textAlign: 'center' }}>{e.detections_count}</td>
                                    <td style={{ padding: '10px 12px', textAlign: 'center' }}>{e.actions_count}</td>
                                    <td style={{ padding: '10px 12px', color: '#94a3b8' }}>{e.latency_ms}ms</td>
                                    <td style={{ padding: '10px 12px', color: '#94a3b8' }}>{e.rulesets_used.join(', ')}</td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                    {data.entries.length === 0 && (
                        <div style={{ padding: '40px', textAlign: 'center', color: '#94a3b8' }}>No audit entries yet</div>
                    )}
                </div>
            )}
        </div>
    );
}
