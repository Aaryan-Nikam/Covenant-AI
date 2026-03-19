import React, { useState, useEffect } from 'react';

export default function Violations({ apiBase }) {
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        fetch(`${apiBase}/dashboard/violations?limit=20`)
            .then(res => res.json())
            .then(d => { setData(d); setLoading(false); })
            .catch(() => setLoading(false));
    }, [apiBase]);

    if (loading) return <div style={{ textAlign: 'center', padding: '40px', color: '#94a3b8' }}>Loading...</div>;
    if (!data) return <div style={{ textAlign: 'center', padding: '40px', color: '#ef4444' }}>Failed to load</div>;

    return (
        <div>
            <h2 style={{ fontSize: '18px', fontWeight: 600, marginBottom: '20px' }}>
                Violations <span style={{ fontSize: '14px', color: '#94a3b8', fontWeight: 400 }}>({data.total} total)</span>
            </h2>
            {data.violations.length === 0 ? (
                <div style={{ background: '#1e293b', borderRadius: '12px', padding: '40px', textAlign: 'center', color: '#94a3b8', border: '1px solid #334155' }}>
                    ✅ No violations recorded yet
                </div>
            ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                    {data.violations.map(v => (
                        <div key={v.entry_id} style={{ background: '#1e293b', borderRadius: '8px', padding: '16px', border: '1px solid #dc2626', borderLeftWidth: '4px' }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
                                <span style={{ fontWeight: 600, color: '#ef4444' }}>🚫 {v.outcome}</span>
                                <span style={{ fontSize: '12px', color: '#94a3b8' }}>{new Date(v.timestamp).toLocaleString()}</span>
                            </div>
                            <div style={{ fontSize: '13px', color: '#cbd5e1' }}>
                                Agent: <strong>{v.agent_id}</strong> | Rulesets: {v.rulesets_used.join(', ')}
                            </div>
                            <div style={{ fontSize: '12px', color: '#94a3b8', marginTop: '4px' }}>
                                {v.detections.length} detection(s), {v.actions_taken.length} action(s)
                            </div>
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
}
