import React, { useState, useEffect } from 'react';

export default function Rulesets({ apiBase }) {
    const [rulesets, setRulesets] = useState([]);
    const [selected, setSelected] = useState(null);
    const [detail, setDetail] = useState(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        fetch(`${apiBase}/proxy/rulesets`)
            .then(res => res.json())
            .then(data => { setRulesets(data.rulesets || []); setLoading(false); })
            .catch(() => setLoading(false));
    }, [apiBase]);

    const selectRuleset = (id) => {
        setSelected(id);
        fetch(`${apiBase}/proxy/rulesets/${id}`)
            .then(res => res.json())
            .then(data => setDetail(data))
            .catch(() => setDetail(null));
    };

    const INDUSTRY_COLORS = { finance: '#f59e0b', healthcare: '#ef4444', general: '#3b82f6' };

    if (loading) return <div style={{ textAlign: 'center', padding: '40px', color: '#94a3b8' }}>Loading...</div>;

    return (
        <div>
            <h2 style={{ fontSize: '18px', fontWeight: 600, marginBottom: '20px' }}>Rulesets</h2>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: '16px', marginBottom: '24px' }}>
                {rulesets.map(r => (
                    <div
                        key={r.ruleset_id}
                        onClick={() => selectRuleset(r.ruleset_id)}
                        style={{
                            background: selected === r.ruleset_id ? '#1e3a5f' : '#1e293b',
                            borderRadius: '12px', padding: '16px', cursor: 'pointer',
                            border: selected === r.ruleset_id ? '2px solid #3b82f6' : '1px solid #334155',
                            transition: 'all 0.2s',
                        }}
                    >
                        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
                            <span style={{ fontWeight: 600, fontSize: '15px' }}>{r.name}</span>
                            <span style={{ fontSize: '11px', padding: '2px 8px', borderRadius: '4px', background: INDUSTRY_COLORS[r.industry] || '#334155', color: '#fff' }}>
                                {r.industry}
                            </span>
                        </div>
                        <div style={{ fontSize: '12px', color: '#94a3b8', marginBottom: '8px' }}>{r.description}</div>
                        <div style={{ fontSize: '12px', color: '#64748b' }}>
                            {r.detectors_count} detectors | v{r.version}
                        </div>
                    </div>
                ))}
            </div>

            {detail && (
                <div style={{ background: '#1e293b', borderRadius: '12px', padding: '20px', border: '1px solid #334155' }}>
                    <h3 style={{ fontSize: '16px', fontWeight: 600, marginBottom: '16px' }}>{detail.name} — Detectors</h3>
                    <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px' }}>
                        <thead>
                            <tr style={{ borderBottom: '1px solid #334155' }}>
                                {['Detector', 'Data Type', 'Layer', 'Confidence', 'Action'].map(h => (
                                    <th key={h} style={{ textAlign: 'left', padding: '8px 12px', color: '#94a3b8', fontWeight: 500 }}>{h}</th>
                                ))}
                            </tr>
                        </thead>
                        <tbody>
                            {detail.detectors.map(d => (
                                <tr key={d.id} style={{ borderBottom: '1px solid #1e293b' }}>
                                    <td style={{ padding: '8px 12px', fontWeight: 500 }}>{d.name}</td>
                                    <td style={{ padding: '8px 12px' }}>
                                        <code style={{ background: '#334155', padding: '2px 6px', borderRadius: '4px', fontSize: '12px' }}>{d.data_type}</code>
                                    </td>
                                    <td style={{ padding: '8px 12px' }}>
                                        <span style={{ color: d.layer === 1 ? '#22c55e' : d.layer === 3 ? '#8b5cf6' : '#94a3b8' }}>
                                            L{d.layer} {d.layer === 1 ? '(regex)' : d.layer === 3 ? '(NER)' : ''}
                                        </span>
                                    </td>
                                    <td style={{ padding: '8px 12px', color: '#94a3b8' }}>{(d.confidence_threshold * 100).toFixed(0)}%</td>
                                    <td style={{ padding: '8px 12px' }}>
                                        {detail.actions[d.data_type] && (
                                            <span style={{
                                                color: detail.actions[d.data_type].primary === 'block' ? '#ef4444' :
                                                    detail.actions[d.data_type].primary === 'tokenize' ? '#3b82f6' :
                                                        detail.actions[d.data_type].primary === 'mask' ? '#f59e0b' : '#8b5cf6',
                                                fontWeight: 600,
                                            }}>
                                                {detail.actions[d.data_type].primary}
                                            </span>
                                        )}
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            )}
        </div>
    );
}
