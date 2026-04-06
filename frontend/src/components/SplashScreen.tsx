import { useState, useEffect } from 'react'

interface SplashScreenProps {
  onComplete: () => void
}

export default function SplashScreen({ onComplete }: SplashScreenProps) {
  const [phase, setPhase] = useState<'enter' | 'hold' | 'exit'>('enter')

  useEffect(() => {
    const enterTimer = setTimeout(() => setPhase('hold'), 100)
    const holdTimer = setTimeout(() => setPhase('exit'), 2800)
    const exitTimer = setTimeout(() => onComplete(), 3600)
    return () => {
      clearTimeout(enterTimer)
      clearTimeout(holdTimer)
      clearTimeout(exitTimer)
    }
  }, [onComplete])

  return (
    <div
      className={`fixed inset-0 z-[9999] flex items-center justify-center bg-[#0a0a1a] transition-opacity duration-700 ${
        phase === 'exit' ? 'opacity-0' : 'opacity-100'
      }`}
    >
      {/* Ambient background glow */}
      <div className="absolute inset-0 overflow-hidden">
        <div
          className={`absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] rounded-full transition-all duration-[2000ms] ease-out ${
            phase === 'enter'
              ? 'scale-0 opacity-0'
              : 'scale-100 opacity-100'
          }`}
          style={{
            background: 'radial-gradient(circle, rgba(99,102,241,0.15) 0%, rgba(139,92,246,0.08) 40%, transparent 70%)',
          }}
        />
      </div>

      {/* Particles */}
      <div className="absolute inset-0 overflow-hidden">
        {[...Array(20)].map((_, i) => (
          <div
            key={i}
            className="absolute w-1 h-1 rounded-full"
            style={{
              left: `${15 + Math.random() * 70}%`,
              top: `${20 + Math.random() * 60}%`,
              background: i % 3 === 0 ? '#22D3EE' : '#A78BFA',
              opacity: phase !== 'enter' ? 0.3 + Math.random() * 0.5 : 0,
              transform: phase !== 'enter'
                ? `translateY(${-20 - Math.random() * 40}px) scale(${0.5 + Math.random()})`
                : 'translateY(20px) scale(0)',
              transition: `all ${1500 + Math.random() * 1500}ms ease-out ${200 + i * 80}ms`,
            }}
          />
        ))}
      </div>

      {/* Main logo + text container */}
      <div className="relative flex flex-col items-center">
        {/* Logo SVG — scales in with glow */}
        <div
          className={`relative transition-all duration-[1800ms] ease-[cubic-bezier(0.16,1,0.3,1)] ${
            phase === 'enter'
              ? 'scale-[0.3] opacity-0'
              : 'scale-100 opacity-100'
          }`}
        >
          {/* Glow ring behind logo */}
          <div
            className={`absolute inset-0 -m-8 rounded-full transition-all duration-[2000ms] ${
              phase !== 'enter' ? 'opacity-60' : 'opacity-0'
            }`}
            style={{
              background: 'radial-gradient(circle, rgba(139,92,246,0.4) 0%, rgba(6,182,212,0.15) 50%, transparent 70%)',
              filter: 'blur(20px)',
            }}
          />

          <svg
            width={140}
            height={140}
            viewBox="0 0 100 100"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
          >
            <defs>
              <linearGradient id="splashLampGrad" x1="0%" y1="0%" x2="0%" y2="100%">
                <stop offset="0%" stopColor="#8B5CF6" />
                <stop offset="100%" stopColor="#6366F1" />
              </linearGradient>
              <linearGradient id="splashSmokeGrad" x1="50%" y1="100%" x2="50%" y2="0%">
                <stop offset="0%" stopColor="#8B5CF6" />
                <stop offset="40%" stopColor="#A78BFA" />
                <stop offset="100%" stopColor="#06B6D4" />
              </linearGradient>
              <linearGradient id="splashNodeGrad" x1="0%" y1="100%" x2="100%" y2="0%">
                <stop offset="0%" stopColor="#A78BFA" />
                <stop offset="100%" stopColor="#22D3EE" />
              </linearGradient>
              <filter id="splashGlow">
                <feGaussianBlur stdDeviation="2" result="coloredBlur"/>
                <feMerge>
                  <feMergeNode in="coloredBlur"/>
                  <feMergeNode in="SourceGraphic"/>
                </feMerge>
              </filter>
            </defs>

            {/* Lamp base */}
            <path d="M38 90 L62 90 Q63 88 62 86 L38 86 Q37 88 38 90 Z" fill="url(#splashLampGrad)" opacity="0.9" />
            {/* Lamp body */}
            <path d="M40 86 L38 80 Q36 74 40 70 L46 66 Q50 64 54 66 L60 70 Q64 74 62 80 L60 86 Z" fill="url(#splashLampGrad)" />
            {/* Lamp highlight */}
            <path d="M43 83 L42 78 Q41 75 43 72 L47 69 Q49 68 50 68" stroke="white" strokeWidth="1.5" strokeLinecap="round" opacity="0.3" fill="none" />
            {/* Spout */}
            <path d="M36 74 Q32 72 28 74 Q30 71 34 71 Q36 71 38 73" fill="url(#splashLampGrad)" />

            {/* Smoke trails */}
            <path d="M30 72 Q26 60 36 50 Q46 40 40 28 Q36 22 42 14" stroke="url(#splashSmokeGrad)" strokeWidth="3" strokeLinecap="round" fill="none" opacity="0.6" />
            <path d="M30 72 Q24 58 38 46 Q50 36 42 22 Q38 16 44 10" stroke="url(#splashSmokeGrad)" strokeWidth="1.5" strokeLinecap="round" fill="none" opacity="0.3" />

            {/* Knowledge nodes */}
            <g filter="url(#splashGlow)">
              <circle cx="36" cy="50" r="3.5" fill="url(#splashNodeGrad)" />
              <circle cx="42" cy="34" r="4" fill="url(#splashNodeGrad)" />
              <circle cx="30" cy="62" r="3" fill="url(#splashNodeGrad)" />
              <circle cx="55" cy="28" r="3" fill="url(#splashNodeGrad)" />
              <circle cx="28" cy="42" r="2.5" fill="url(#splashNodeGrad)" />
              <circle cx="50" cy="46" r="2.5" fill="url(#splashNodeGrad)" />
              <circle cx="44" cy="14" r="2" fill="#22D3EE" />
              <circle cx="60" cy="40" r="2" fill="url(#splashNodeGrad)" opacity="0.7" />
              <circle cx="22" cy="54" r="1.5" fill="url(#splashNodeGrad)" opacity="0.5" />
            </g>

            {/* Connection lines */}
            <g stroke="url(#splashNodeGrad)" strokeWidth="1" opacity="0.4">
              <line x1="30" y1="62" x2="36" y2="50" />
              <line x1="36" y1="50" x2="42" y2="34" />
              <line x1="42" y1="34" x2="55" y2="28" />
              <line x1="36" y1="50" x2="50" y2="46" />
              <line x1="50" y1="46" x2="60" y2="40" />
              <line x1="42" y1="34" x2="28" y2="42" />
              <line x1="28" y1="42" x2="22" y2="54" />
              <line x1="42" y1="34" x2="44" y2="14" />
              <line x1="55" y1="28" x2="60" y2="40" />
            </g>

            {/* Top sparkle */}
            <g filter="url(#splashGlow)">
              <path d="M44 8 L45.5 11 L49 12 L46 13.5 L46.5 17 L44 14.5 L41.5 17 L42 13.5 L39 12 L42.5 11 Z" fill="#22D3EE" />
            </g>

            {/* Document icon */}
            <g opacity="0.9">
              <rect x="39" y="30" rx="1" ry="1" width="6" height="8" fill="white" opacity="0.8" />
              <line x1="40.5" y1="33" x2="43.5" y2="33" stroke="#6366F1" strokeWidth="0.7" />
              <line x1="40.5" y1="35" x2="43.5" y2="35" stroke="#6366F1" strokeWidth="0.7" />
            </g>
          </svg>
        </div>

        {/* Brand text — fades in after logo */}
        <div
          className={`mt-8 flex flex-col items-center transition-all duration-[1200ms] ease-out ${
            phase === 'enter'
              ? 'opacity-0 translate-y-6'
              : 'opacity-100 translate-y-0'
          }`}
          style={{ transitionDelay: phase !== 'enter' ? '600ms' : '0ms' }}
        >
          <h1
            className="text-5xl font-bold tracking-tight"
            style={{
              background: 'linear-gradient(135deg, #A78BFA 0%, #8B5CF6 30%, #06B6D4 100%)',
              WebkitBackgroundClip: 'text',
              WebkitTextFillColor: 'transparent',
              backgroundClip: 'text',
            }}
          >
            RAGenie
          </h1>
          <p
            className={`mt-3 text-sm font-medium tracking-[0.3em] uppercase transition-all duration-[1000ms] ${
              phase === 'enter'
                ? 'opacity-0 tracking-[0.6em]'
                : 'opacity-60 tracking-[0.3em]'
            }`}
            style={{
              color: '#94A3B8',
              transitionDelay: phase !== 'enter' ? '1000ms' : '0ms',
            }}
          >
            AI Knowledge Assistant
          </p>
        </div>

        {/* Light sweep effect across the logo text */}
        <div
          className="absolute top-0 left-0 w-full h-full pointer-events-none overflow-hidden"
          style={{ mixBlendMode: 'screen' }}
        >
          <div
            className={`absolute top-0 w-[60px] h-full transition-all duration-[1500ms] ease-in-out ${
              phase !== 'enter' ? 'opacity-100' : 'opacity-0'
            }`}
            style={{
              background: 'linear-gradient(90deg, transparent, rgba(255,255,255,0.08), transparent)',
              left: phase !== 'enter' ? '120%' : '-20%',
              transitionDelay: '1200ms',
            }}
          />
        </div>
      </div>
    </div>
  )
}
