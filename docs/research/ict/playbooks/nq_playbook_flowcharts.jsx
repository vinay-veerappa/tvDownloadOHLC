import React, { useState } from 'react';

// Color scheme - trading-focused
const colors = {
  bg: '#0d1117',
  card: '#161b22',
  cardHover: '#1f2937',
  border: '#30363d',
  text: '#e6edf3',
  textMuted: '#8b949e',
  green: '#3fb950',
  greenBg: 'rgba(63,185,80,0.15)',
  yellow: '#d29922',
  yellowBg: 'rgba(210,153,34,0.15)',
  red: '#f85149',
  redBg: 'rgba(248,81,73,0.15)',
  blue: '#58a6ff',
  blueBg: 'rgba(88,166,255,0.15)',
  purple: '#a371f7',
  purpleBg: 'rgba(163,113,247,0.15)',
  cyan: '#39d0d6',
};

// Probability badge component
const ProbBadge = ({ value, size = 'md' }) => {
  const num = parseFloat(value);
  let bg, color;
  if (num >= 75) { bg = colors.greenBg; color = colors.green; }
  else if (num >= 60) { bg = colors.yellowBg; color = colors.yellow; }
  else { bg = colors.redBg; color = colors.red; }
  
  const sizeStyles = {
    sm: { fontSize: '11px', padding: '2px 6px' },
    md: { fontSize: '13px', padding: '3px 8px' },
    lg: { fontSize: '15px', padding: '4px 10px' },
  };
  
  return (
    <span style={{
      background: bg,
      color: color,
      borderRadius: '4px',
      fontWeight: 600,
      fontFamily: 'JetBrains Mono, monospace',
      ...sizeStyles[size],
    }}>
      {value}%
    </span>
  );
};

// Decision node component
const DecisionNode = ({ title, description, children, color = colors.blue, expanded = true }) => (
  <div style={{
    background: colors.card,
    border: `1px solid ${colors.border}`,
    borderLeft: `3px solid ${color}`,
    borderRadius: '8px',
    padding: '12px 16px',
    marginBottom: '8px',
  }}>
    <div style={{ fontWeight: 600, color: colors.text, marginBottom: description ? '4px' : 0 }}>
      {title}
    </div>
    {description && (
      <div style={{ fontSize: '13px', color: colors.textMuted }}>{description}</div>
    )}
    {children}
  </div>
);

// Arrow connector
const Arrow = ({ direction = 'down', label }) => (
  <div style={{ 
    display: 'flex', 
    flexDirection: direction === 'down' ? 'column' : 'row',
    alignItems: 'center', 
    margin: '4px 0',
    color: colors.textMuted,
  }}>
    {direction === 'down' ? (
      <>
        <div style={{ width: '2px', height: '16px', background: colors.border }} />
        {label && <span style={{ fontSize: '11px', margin: '2px 0' }}>{label}</span>}
        <div style={{ fontSize: '12px' }}>▼</div>
      </>
    ) : (
      <>
        <div style={{ height: '2px', width: '20px', background: colors.border }} />
        <div style={{ fontSize: '12px' }}>▶</div>
      </>
    )}
  </div>
);

// Branch container
const Branch = ({ children, label }) => (
  <div style={{ 
    display: 'flex', 
    gap: '12px', 
    marginTop: '8px',
    flexWrap: 'wrap',
  }}>
    {children}
  </div>
);

// Outcome box
const Outcome = ({ bias, prob, action, color }) => (
  <div style={{
    background: color === 'green' ? colors.greenBg : color === 'red' ? colors.redBg : colors.yellowBg,
    border: `1px solid ${color === 'green' ? colors.green : color === 'red' ? colors.red : colors.yellow}`,
    borderRadius: '6px',
    padding: '10px 14px',
    minWidth: '140px',
    flex: '1',
  }}>
    <div style={{ 
      fontWeight: 700, 
      color: color === 'green' ? colors.green : color === 'red' ? colors.red : colors.yellow,
      fontSize: '14px',
      marginBottom: '4px',
    }}>
      {bias}
    </div>
    <div style={{ fontSize: '20px', fontWeight: 700, color: colors.text, fontFamily: 'JetBrains Mono, monospace' }}>
      {prob}%
    </div>
    <div style={{ fontSize: '12px', color: colors.textMuted, marginTop: '4px' }}>{action}</div>
  </div>
);

// Session card component
const SessionCard = ({ time, name, objective, status, onClick, active }) => (
  <div 
    onClick={onClick}
    style={{
      background: active ? colors.blueBg : colors.card,
      border: `1px solid ${active ? colors.blue : colors.border}`,
      borderRadius: '8px',
      padding: '16px',
      cursor: 'pointer',
      transition: 'all 0.2s',
      minWidth: '160px',
    }}
  >
    <div style={{ fontSize: '12px', color: colors.blue, fontFamily: 'JetBrains Mono, monospace', marginBottom: '4px' }}>
      {time}
    </div>
    <div style={{ fontWeight: 700, color: colors.text, fontSize: '16px', marginBottom: '6px' }}>{name}</div>
    <div style={{ fontSize: '12px', color: colors.textMuted }}>{objective}</div>
    <div style={{ 
      marginTop: '8px',
      fontSize: '11px',
      padding: '2px 8px',
      borderRadius: '4px',
      display: 'inline-block',
      background: status === 'TRADE' ? colors.greenBg : status === 'OBSERVE' ? colors.purpleBg : colors.yellowBg,
      color: status === 'TRADE' ? colors.green : status === 'OBSERVE' ? colors.purple : colors.yellow,
      fontWeight: 600,
    }}>
      {status}
    </div>
  </div>
);

// Main Session Flow
const MainSessionFlow = ({ onSessionClick, activeSession }) => (
  <div>
    <h2 style={{ color: colors.text, marginBottom: '20px', fontSize: '20px' }}>
      📊 Session Flow Overview
    </h2>
    <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', alignItems: 'center' }}>
      <SessionCard 
        time="19:30-02:30" 
        name="ASIA" 
        objective="Establish Range" 
        status="OBSERVE"
        onClick={() => onSessionClick('asia')}
        active={activeSession === 'asia'}
      />
      <div style={{ color: colors.textMuted, fontSize: '20px' }}>→</div>
      <SessionCard 
        time="02:30-08:00" 
        name="LONDON" 
        objective="Manipulation Pattern" 
        status="OBSERVE"
        onClick={() => onSessionClick('london')}
        active={activeSession === 'london'}
      />
      <div style={{ color: colors.textMuted, fontSize: '20px' }}>→</div>
      <SessionCard 
        time="09:30-12:00" 
        name="NY AM" 
        objective="Execute Reversal" 
        status="TRADE"
        onClick={() => onSessionClick('nyam')}
        active={activeSession === 'nyam'}
      />
      <div style={{ color: colors.textMuted, fontSize: '20px' }}>→</div>
      <SessionCard 
        time="12:00-13:30" 
        name="LUNCH" 
        objective="Track H/L" 
        status="MANAGE"
        onClick={() => onSessionClick('lunch')}
        active={activeSession === 'lunch'}
      />
      <div style={{ color: colors.textMuted, fontSize: '20px' }}>→</div>
      <SessionCard 
        time="13:30-16:00" 
        name="NY PM" 
        objective="Manage Runner" 
        status="MANAGE"
        onClick={() => onSessionClick('pm')}
        active={activeSession === 'pm'}
      />
    </div>
  </div>
);

// London Pattern Decision Tree
const LondonPatternTree = () => (
  <div>
    <h3 style={{ color: colors.text, marginBottom: '16px' }}>🔍 London Pattern Classification</h3>
    
    <DecisionNode title="Did London sweep Asia High?" color={colors.cyan}>
      <Branch>
        <div style={{ flex: 1 }}>
          <div style={{ color: colors.green, fontWeight: 600, marginBottom: '8px' }}>✓ YES</div>
          <DecisionNode title="Did London also sweep Asia Low?" color={colors.purple}>
            <Branch>
              <div style={{ flex: 1 }}>
                <div style={{ color: colors.green, fontWeight: 600, marginBottom: '8px' }}>✓ YES</div>
                <Outcome bias="LONDON ENGULFS" prob="—" action="Both swept = volatile" color="yellow" />
              </div>
              <div style={{ flex: 1 }}>
                <div style={{ color: colors.red, fontWeight: 600, marginBottom: '8px' }}>✗ NO</div>
                <Outcome bias="PARTIAL UP" prob="64" action="Bearish manipulation" color="red" />
              </div>
            </Branch>
          </DecisionNode>
        </div>
        <div style={{ flex: 1 }}>
          <div style={{ color: colors.red, fontWeight: 600, marginBottom: '8px' }}>✗ NO</div>
          <DecisionNode title="Did London sweep Asia Low?" color={colors.purple}>
            <Branch>
              <div style={{ flex: 1 }}>
                <div style={{ color: colors.green, fontWeight: 600, marginBottom: '8px' }}>✓ YES</div>
                <Outcome bias="PARTIAL DOWN" prob="64" action="Bullish manipulation" color="green" />
              </div>
              <div style={{ flex: 1 }}>
                <div style={{ color: colors.red, fontWeight: 600, marginBottom: '8px' }}>✗ NO</div>
                <Outcome bias="ASIA INSIDE" prob="—" action="No manipulation = skip" color="yellow" />
              </div>
            </Branch>
          </DecisionNode>
        </div>
      </Branch>
    </DecisionNode>
  </div>
);

// 72-Scenario Decision Tree (Simplified)
const ScenarioDecisionTree = () => (
  <div>
    <h3 style={{ color: colors.text, marginBottom: '16px' }}>🎯 72-Scenario Decision Tree</h3>
    <p style={{ color: colors.textMuted, fontSize: '13px', marginBottom: '16px' }}>
      Asia Range × London Pattern × NY Position × Alignment → Probability
    </p>
    
    {/* Best Setups */}
    <div style={{ marginBottom: '20px' }}>
      <div style={{ color: colors.green, fontWeight: 700, marginBottom: '12px', display: 'flex', alignItems: 'center', gap: '8px' }}>
        <span style={{ fontSize: '18px' }}>🟢</span> BEST SETUPS (75%+)
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '12px' }}>
        <div style={{ background: colors.greenBg, border: `1px solid ${colors.green}`, borderRadius: '8px', padding: '12px' }}>
          <div style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: '12px', color: colors.textMuted, marginBottom: '8px' }}>
            Small Asia + Partial Down + Above Mid
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ color: colors.green, fontWeight: 700 }}>LONG</span>
            <span style={{ fontSize: '24px', fontWeight: 700, color: colors.text }}>88.6%</span>
          </div>
        </div>
        <div style={{ background: colors.greenBg, border: `1px solid ${colors.green}`, borderRadius: '8px', padding: '12px' }}>
          <div style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: '12px', color: colors.textMuted, marginBottom: '8px' }}>
            Small Asia + Partial Up + Below Mid
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ color: colors.red, fontWeight: 700 }}>SHORT</span>
            <span style={{ fontSize: '24px', fontWeight: 700, color: colors.text }}>87.5%</span>
          </div>
        </div>
        <div style={{ background: colors.greenBg, border: `1px solid ${colors.green}`, borderRadius: '8px', padding: '12px' }}>
          <div style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: '12px', color: colors.textMuted, marginBottom: '8px' }}>
            Any Asia + Aligned + Position Confirms
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ color: colors.blue, fontWeight: 700 }}>ALIGNED</span>
            <span style={{ fontSize: '24px', fontWeight: 700, color: colors.text }}>84-86%</span>
          </div>
        </div>
      </div>
    </div>
    
    {/* Medium Setups */}
    <div style={{ marginBottom: '20px' }}>
      <div style={{ color: colors.yellow, fontWeight: 700, marginBottom: '12px', display: 'flex', alignItems: 'center', gap: '8px' }}>
        <span style={{ fontSize: '18px' }}>🟡</span> MEDIUM SETUPS (60-75%)
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '12px' }}>
        <div style={{ background: colors.yellowBg, border: `1px solid ${colors.yellow}`, borderRadius: '8px', padding: '12px' }}>
          <div style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: '12px', color: colors.textMuted, marginBottom: '8px' }}>
            Medium Asia + Partial Down + Above Mid
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ color: colors.green, fontWeight: 700 }}>LONG</span>
            <span style={{ fontSize: '24px', fontWeight: 700, color: colors.text }}>73.2%</span>
          </div>
        </div>
        <div style={{ background: colors.yellowBg, border: `1px solid ${colors.yellow}`, borderRadius: '8px', padding: '12px' }}>
          <div style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: '12px', color: colors.textMuted, marginBottom: '8px' }}>
            Large Asia + Any Pattern
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ color: colors.yellow, fontWeight: 700 }}>VARIABLE</span>
            <span style={{ fontSize: '24px', fontWeight: 700, color: colors.text }}>61-68%</span>
          </div>
        </div>
      </div>
    </div>
    
    {/* Skip Setups */}
    <div>
      <div style={{ color: colors.red, fontWeight: 700, marginBottom: '12px', display: 'flex', alignItems: 'center', gap: '8px' }}>
        <span style={{ fontSize: '18px' }}>🔴</span> SKIP SETUPS (&lt;60%)
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '12px' }}>
        <div style={{ background: colors.redBg, border: `1px solid ${colors.red}`, borderRadius: '8px', padding: '12px' }}>
          <div style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: '12px', color: colors.textMuted, marginBottom: '8px' }}>
            Misaligned: Bearish Manip + Above Mid
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ color: colors.textMuted, fontWeight: 700 }}>CONFLICT</span>
            <span style={{ fontSize: '24px', fontWeight: 700, color: colors.text }}>49-56%</span>
          </div>
        </div>
        <div style={{ background: colors.redBg, border: `1px solid ${colors.red}`, borderRadius: '8px', padding: '12px' }}>
          <div style={{ fontFamily: 'JetBrains Mono, monospace', fontSize: '12px', color: colors.textMuted, marginBottom: '8px' }}>
            Misaligned: Bullish Manip + Below Mid
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ color: colors.textMuted, fontWeight: 700 }}>CONFLICT</span>
            <span style={{ fontSize: '24px', fontWeight: 700, color: colors.text }}>49-56%</span>
          </div>
        </div>
      </div>
    </div>
  </div>
);

// NY AM Execution Tree
const NYAMExecutionTree = () => (
  <div>
    <h3 style={{ color: colors.text, marginBottom: '16px' }}>⚡ NY AM Execution Decision Tree</h3>
    
    <DecisionNode title="09:30 - Where does NY open vs London Mid?" color={colors.blue}>
      <Branch>
        <div style={{ flex: 1 }}>
          <DecisionNode title="ABOVE London Mid" color={colors.green}>
            <p style={{ fontSize: '13px', color: colors.textMuted, margin: '8px 0' }}>
              Position Signal: <strong style={{ color: colors.green }}>LONG BIAS (78%)</strong>
            </p>
            <DecisionNode title="What did London do?" color={colors.purple}>
              <Branch>
                <div style={{ flex: 1 }}>
                  <Outcome 
                    bias="Partial Down (Aligned)" 
                    prob="84-88" 
                    action="✓ TAKE LONG" 
                    color="green" 
                  />
                </div>
                <div style={{ flex: 1 }}>
                  <Outcome 
                    bias="Partial Up (Conflict)" 
                    prob="49-56" 
                    action="✗ SKIP" 
                    color="red" 
                  />
                </div>
              </Branch>
            </DecisionNode>
          </DecisionNode>
        </div>
        
        <div style={{ flex: 1 }}>
          <DecisionNode title="BELOW London Mid" color={colors.red}>
            <p style={{ fontSize: '13px', color: colors.textMuted, margin: '8px 0' }}>
              Position Signal: <strong style={{ color: colors.red }}>SHORT BIAS (73%)</strong>
            </p>
            <DecisionNode title="What did London do?" color={colors.purple}>
              <Branch>
                <div style={{ flex: 1 }}>
                  <Outcome 
                    bias="Partial Up (Aligned)" 
                    prob="84-87" 
                    action="✓ TAKE SHORT" 
                    color="green" 
                  />
                </div>
                <div style={{ flex: 1 }}>
                  <Outcome 
                    bias="Partial Down (Conflict)" 
                    prob="49-56" 
                    action="✗ SKIP" 
                    color="red" 
                  />
                </div>
              </Branch>
            </DecisionNode>
          </DecisionNode>
        </div>
      </Branch>
    </DecisionNode>
    
    {/* Timing */}
    <div style={{ marginTop: '20px', background: colors.card, border: `1px solid ${colors.border}`, borderRadius: '8px', padding: '16px' }}>
      <h4 style={{ color: colors.cyan, marginBottom: '12px' }}>⏰ Reversal Timing Distribution</h4>
      <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
        {[
          { time: '09:30-10:00', pct: '60.6%', color: colors.green },
          { time: '10:00-10:30', pct: '20.2%', color: colors.yellow },
          { time: '10:30-11:00', pct: '10.1%', color: colors.yellow },
          { time: '11:00-12:00', pct: '9.1%', color: colors.red },
        ].map((t, i) => (
          <div key={i} style={{ 
            background: colors.bg, 
            padding: '8px 12px', 
            borderRadius: '6px',
            border: `1px solid ${colors.border}`,
            textAlign: 'center',
          }}>
            <div style={{ fontSize: '11px', color: colors.textMuted }}>{t.time}</div>
            <div style={{ fontSize: '18px', fontWeight: 700, color: t.color }}>{t.pct}</div>
          </div>
        ))}
      </div>
      <p style={{ fontSize: '12px', color: colors.textMuted, marginTop: '12px' }}>
        80.8% of reversals happen by 10:30 AM. If no setup by 11:00, opportunity missed.
      </p>
    </div>
  </div>
);

// Gap Confluence Tree
const GapConfluenceTree = () => (
  <div>
    <h3 style={{ color: colors.text, marginBottom: '16px' }}>📈 Gap Confluence Analysis</h3>
    
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '16px' }}>
      <div style={{ background: colors.card, border: `1px solid ${colors.border}`, borderRadius: '8px', padding: '16px' }}>
        <h4 style={{ color: colors.green, marginBottom: '12px' }}>Gap CHASING Sweep (+18% Edge)</h4>
        <div style={{ fontSize: '13px', color: colors.textMuted, marginBottom: '12px' }}>
          Gap direction matches sweep direction
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', padding: '8px', background: colors.greenBg, borderRadius: '4px' }}>
            <span style={{ color: colors.text }}>London swept Low + Gap Up</span>
            <span style={{ color: colors.green, fontWeight: 700 }}>78.5%</span>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', padding: '8px', background: colors.greenBg, borderRadius: '4px' }}>
            <span style={{ color: colors.text }}>London swept High + Gap Down</span>
            <span style={{ color: colors.green, fontWeight: 700 }}>76.2%</span>
          </div>
        </div>
      </div>
      
      <div style={{ background: colors.card, border: `1px solid ${colors.border}`, borderRadius: '8px', padding: '16px' }}>
        <h4 style={{ color: colors.yellow, marginBottom: '12px' }}>Gap FADING Sweep (Baseline)</h4>
        <div style={{ fontSize: '13px', color: colors.textMuted, marginBottom: '12px' }}>
          Gap direction opposes sweep direction
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', padding: '8px', background: colors.yellowBg, borderRadius: '4px' }}>
            <span style={{ color: colors.text }}>London swept Low + Gap Down</span>
            <span style={{ color: colors.yellow, fontWeight: 700 }}>60.3%</span>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', padding: '8px', background: colors.yellowBg, borderRadius: '4px' }}>
            <span style={{ color: colors.text }}>London swept High + Gap Up</span>
            <span style={{ color: colors.yellow, fontWeight: 700 }}>58.1%</span>
          </div>
        </div>
      </div>
    </div>
    
    <div style={{ marginTop: '16px', padding: '12px', background: colors.blueBg, borderRadius: '6px', border: `1px solid ${colors.blue}` }}>
      <strong style={{ color: colors.blue }}>💡 Key Insight:</strong>
      <span style={{ color: colors.text, marginLeft: '8px' }}>
        A "chasing" gap adds ~18% to reversal probability. Check gap direction every morning!
      </span>
    </div>
  </div>
);

// PM Management Tree
const PMManagementTree = () => (
  <div>
    <h3 style={{ color: colors.text, marginBottom: '16px' }}>🌅 PM Session Management</h3>
    
    <div style={{ background: colors.card, border: `1px solid ${colors.border}`, borderRadius: '8px', padding: '16px', marginBottom: '16px' }}>
      <h4 style={{ color: colors.purple, marginBottom: '12px' }}>PM Behavior After AM</h4>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '12px' }}>
        <div style={{ textAlign: 'center', padding: '12px', background: colors.greenBg, borderRadius: '6px' }}>
          <div style={{ fontSize: '11px', color: colors.textMuted }}>PM Continues AM</div>
          <div style={{ fontSize: '28px', fontWeight: 700, color: colors.green }}>52%</div>
        </div>
        <div style={{ textAlign: 'center', padding: '12px', background: colors.redBg, borderRadius: '6px' }}>
          <div style={{ fontSize: '11px', color: colors.textMuted }}>PM Reverses AM</div>
          <div style={{ fontSize: '28px', fontWeight: 700, color: colors.red }}>20-23%</div>
        </div>
        <div style={{ textAlign: 'center', padding: '12px', background: colors.yellowBg, borderRadius: '6px' }}>
          <div style={{ fontSize: '11px', color: colors.textMuted }}>Neutral/Chop</div>
          <div style={{ fontSize: '28px', fontWeight: 700, color: colors.yellow }}>25-28%</div>
        </div>
      </div>
    </div>
    
    <DecisionNode title="Do you have a position from AM?" color={colors.cyan}>
      <Branch>
        <div style={{ flex: 1 }}>
          <div style={{ color: colors.green, fontWeight: 600, marginBottom: '8px' }}>✓ YES - In Profit</div>
          <div style={{ background: colors.greenBg, padding: '12px', borderRadius: '6px', border: `1px solid ${colors.green}` }}>
            <div style={{ fontWeight: 600, color: colors.green, marginBottom: '8px' }}>HOLD WITH BE STOP</div>
            <ul style={{ margin: 0, paddingLeft: '20px', fontSize: '13px', color: colors.textMuted }}>
              <li>Move stop to breakeven</li>
              <li>Target: Lunch H/L (only level &gt;50% hit in PM)</li>
              <li>PM continues AM 2-3x more than reverses</li>
            </ul>
          </div>
        </div>
        <div style={{ flex: 1 }}>
          <div style={{ color: colors.red, fontWeight: 600, marginBottom: '8px' }}>✗ NO - Flat</div>
          <div style={{ background: colors.yellowBg, padding: '12px', borderRadius: '6px', border: `1px solid ${colors.yellow}` }}>
            <div style={{ fontWeight: 600, color: colors.yellow, marginBottom: '8px' }}>DO NOT INITIATE</div>
            <ul style={{ margin: 0, paddingLeft: '20px', fontSize: '13px', color: colors.textMuted }}>
              <li>PM is for managing, not initiating</li>
              <li>Edge significantly lower in PM</li>
              <li>Wait for tomorrow's setup</li>
            </ul>
          </div>
        </div>
      </Branch>
    </DecisionNode>
  </div>
);

// CBDR Sigma Targets
const CBDRTargets = () => (
  <div>
    <h3 style={{ color: colors.text, marginBottom: '16px' }}>📏 CBDR Sigma Targets (DOL)</h3>
    
    <p style={{ color: colors.textMuted, fontSize: '13px', marginBottom: '16px' }}>
      Once manipulation direction is known, sigma targets become asymmetric
    </p>
    
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: '16px' }}>
      <div style={{ background: colors.card, border: `1px solid ${colors.green}`, borderRadius: '8px', padding: '16px' }}>
        <h4 style={{ color: colors.green, marginBottom: '12px' }}>Bullish Manipulation</h4>
        <div style={{ fontSize: '12px', color: colors.textMuted, marginBottom: '12px' }}>
          (London swept Asia Low)
        </div>
        <table style={{ width: '100%', fontSize: '13px', borderCollapse: 'collapse' }}>
          <tbody>
            {[
              ['-2σ (Manip Leg)', '58.3%', colors.green],
              ['-1σ', '73.1%', colors.green],
              ['+1σ', '41.2%', colors.yellow],
              ['+2σ (Target)', '25.6%', colors.red],
            ].map(([level, pct, color], i) => (
              <tr key={i} style={{ borderBottom: `1px solid ${colors.border}` }}>
                <td style={{ padding: '8px 0', color: colors.text }}>{level}</td>
                <td style={{ padding: '8px 0', textAlign: 'right', color, fontWeight: 600 }}>{pct}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      
      <div style={{ background: colors.card, border: `1px solid ${colors.red}`, borderRadius: '8px', padding: '16px' }}>
        <h4 style={{ color: colors.red, marginBottom: '12px' }}>Bearish Manipulation</h4>
        <div style={{ fontSize: '12px', color: colors.textMuted, marginBottom: '12px' }}>
          (London swept Asia High)
        </div>
        <table style={{ width: '100%', fontSize: '13px', borderCollapse: 'collapse' }}>
          <tbody>
            {[
              ['+2σ (Manip Leg)', '56.8%', colors.red],
              ['+1σ', '71.4%', colors.red],
              ['-1σ', '43.7%', colors.yellow],
              ['-2σ (Target)', '27.2%', colors.green],
            ].map(([level, pct, color], i) => (
              <tr key={i} style={{ borderBottom: `1px solid ${colors.border}` }}>
                <td style={{ padding: '8px 0', color: colors.text }}>{level}</td>
                <td style={{ padding: '8px 0', textAlign: 'right', color, fontWeight: 600 }}>{pct}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  </div>
);

// Quick Reference Card
const QuickReference = () => (
  <div style={{ background: colors.card, border: `1px solid ${colors.blue}`, borderRadius: '8px', padding: '16px' }}>
    <h3 style={{ color: colors.blue, marginBottom: '16px' }}>⚡ Quick Reference: Morning Checklist</h3>
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '12px' }}>
      <div>
        <div style={{ fontWeight: 600, color: colors.text, marginBottom: '8px' }}>1. Asia Range Size</div>
        <div style={{ fontSize: '13px', color: colors.textMuted }}>
          Small = 🟢 66.8%<br/>
          Medium = 🟡 60.6%<br/>
          Large = 🔴 54.0%
        </div>
      </div>
      <div>
        <div style={{ fontWeight: 600, color: colors.text, marginBottom: '8px' }}>2. London Pattern</div>
        <div style={{ fontSize: '13px', color: colors.textMuted }}>
          Partial Down = Bullish<br/>
          Partial Up = Bearish<br/>
          Engulfs = Volatile
        </div>
      </div>
      <div>
        <div style={{ fontWeight: 600, color: colors.text, marginBottom: '8px' }}>3. Gap Direction</div>
        <div style={{ fontSize: '13px', color: colors.textMuted }}>
          Chasing = +18% edge<br/>
          Fading = Baseline
        </div>
      </div>
      <div>
        <div style={{ fontWeight: 600, color: colors.text, marginBottom: '8px' }}>4. NY Position</div>
        <div style={{ fontSize: '13px', color: colors.textMuted }}>
          Above Mid = Long 78%<br/>
          Below Mid = Short 73%
        </div>
      </div>
    </div>
    
    <div style={{ marginTop: '16px', padding: '12px', background: colors.greenBg, borderRadius: '6px' }}>
      <strong style={{ color: colors.green }}>Trade Only When Aligned:</strong>
      <span style={{ color: colors.text, marginLeft: '8px' }}>
        Position + Manipulation agree = 84-88%. Conflict = 49-56% (skip).
      </span>
    </div>
  </div>
);

// Main App
export default function PlaybookFlowcharts() {
  const [activeView, setActiveView] = useState('overview');
  const [activeSession, setActiveSession] = useState(null);
  
  const views = [
    { id: 'overview', label: 'Overview' },
    { id: 'london', label: 'London Pattern' },
    { id: 'scenarios', label: '72 Scenarios' },
    { id: 'execution', label: 'NY AM Execution' },
    { id: 'gap', label: 'Gap Confluence' },
    { id: 'cbdr', label: 'CBDR Targets' },
    { id: 'pm', label: 'PM Management' },
  ];
  
  return (
    <div style={{ 
      background: colors.bg, 
      minHeight: '100vh', 
      padding: '24px',
      fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
    }}>
      {/* Header */}
      <div style={{ marginBottom: '24px' }}>
        <h1 style={{ color: colors.text, margin: 0, fontSize: '28px' }}>
          NQ Playbook — Visual Flowcharts
        </h1>
        <p style={{ color: colors.textMuted, margin: '8px 0 0' }}>
          5,165 Trading Days | Decision Trees with Probabilities
        </p>
      </div>
      
      {/* Navigation */}
      <div style={{ 
        display: 'flex', 
        gap: '8px', 
        marginBottom: '24px', 
        flexWrap: 'wrap',
        borderBottom: `1px solid ${colors.border}`,
        paddingBottom: '16px',
      }}>
        {views.map(v => (
          <button
            key={v.id}
            onClick={() => setActiveView(v.id)}
            style={{
              background: activeView === v.id ? colors.blue : 'transparent',
              color: activeView === v.id ? '#fff' : colors.textMuted,
              border: `1px solid ${activeView === v.id ? colors.blue : colors.border}`,
              borderRadius: '6px',
              padding: '8px 16px',
              cursor: 'pointer',
              fontSize: '14px',
              fontWeight: activeView === v.id ? 600 : 400,
              transition: 'all 0.2s',
            }}
          >
            {v.label}
          </button>
        ))}
      </div>
      
      {/* Content */}
      <div style={{ maxWidth: '1200px' }}>
        {activeView === 'overview' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
            <MainSessionFlow onSessionClick={setActiveSession} activeSession={activeSession} />
            <QuickReference />
          </div>
        )}
        {activeView === 'london' && <LondonPatternTree />}
        {activeView === 'scenarios' && <ScenarioDecisionTree />}
        {activeView === 'execution' && <NYAMExecutionTree />}
        {activeView === 'gap' && <GapConfluenceTree />}
        {activeView === 'cbdr' && <CBDRTargets />}
        {activeView === 'pm' && <PMManagementTree />}
      </div>
      
      {/* Footer */}
      <div style={{ 
        marginTop: '40px', 
        paddingTop: '16px', 
        borderTop: `1px solid ${colors.border}`,
        color: colors.textMuted,
        fontSize: '12px',
      }}>
        Based on ICT Methodology | Data: 2006-2026 | All probabilities from historical NQ analysis
      </div>
    </div>
  );
}
