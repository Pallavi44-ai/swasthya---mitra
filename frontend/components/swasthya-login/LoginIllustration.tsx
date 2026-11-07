/**
 * Original inline-SVG illustration: an elderly woman with a friendly AI companion robot.
 * No external image files or licences needed. Decorative → hidden from screen readers.
 */
export function LoginIllustration({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 480 360" role="img" aria-hidden="true" focusable="false">
      <defs>
        <linearGradient id="sm-sky" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#e6fbf5" /><stop offset="1" stopColor="#b9efe2" />
        </linearGradient>
        <linearGradient id="sm-bot" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#ffffff" /><stop offset="1" stopColor="#d3f5ec" />
        </linearGradient>
      </defs>
      {/* backdrop */}
      <circle cx="240" cy="180" r="165" fill="url(#sm-sky)" />
      <circle cx="82" cy="90" r="20" fill="#ffffff" opacity=".7" />
      <circle cx="410" cy="70" r="12" fill="#ffffff" opacity=".8" />
      {/* plant */}
      <path d="M52 320c-2-34 4-58 20-76 4 30-2 54-20 76zM52 320c-12-26-12-46-2-64 10 22 8 44 2 64zM52 320c16-18 30-26 46-28-8 18-24 28-46 28z" fill="#2fa58f" />
      <rect x="36" y="318" width="34" height="28" rx="6" fill="#0f766e" />
      {/* sofa */}
      <rect x="92" y="236" width="206" height="96" rx="26" fill="#0f766e" />
      <rect x="82" y="262" width="40" height="70" rx="18" fill="#14917f" />
      <rect x="268" y="262" width="40" height="70" rx="18" fill="#14917f" />
      {/* elderly woman */}
      <g>
        <path d="M128 236c0-44 26-70 62-70s62 26 62 70v18H128z" fill="#f2b84b" />{/* cardigan */}
        <path d="M168 170h44l-8 40h-28z" fill="#ffffff" />
        <rect x="176" y="146" width="28" height="28" rx="12" fill="#e9b894" />{/* neck */}
        <circle cx="190" cy="120" r="36" fill="#f1c6a3" />{/* face */}
        <path d="M154 114c-6-32 20-52 42-48 24 2 38 22 30 50-8-18-20-26-36-26-14 0-26 8-36 24z" fill="#e8ecee" />{/* grey hair */}
        <circle cx="190" cy="62" r="17" fill="#e8ecee" />{/* bun */}
        <circle cx="176" cy="122" r="4" fill="#2b3a3a" /><circle cx="204" cy="122" r="4" fill="#2b3a3a" />
        <path d="M178 138q12 11 24 0" fill="none" stroke="#b0553f" strokeWidth="3.5" strokeLinecap="round" />
        <circle cx="168" cy="134" r="6" fill="#f09a8c" opacity=".5" /><circle cx="212" cy="134" r="6" fill="#f09a8c" opacity=".5" />
        <g fill="none" stroke="#0f766e" strokeWidth="3"><circle cx="176" cy="122" r="11" /><circle cx="204" cy="122" r="11" /><path d="M187 122h6" /></g>{/* glasses */}
        <path d="M232 206c26 6 44 4 62-14" fill="none" stroke="#f1c6a3" strokeWidth="16" strokeLinecap="round" />{/* arm reaching the bot */}
        <rect x="132" y="254" width="120" height="34" rx="14" fill="#6aa8c9" />{/* knees / skirt */}
      </g>
      {/* AI companion */}
      <g className="sm-bot-bob">
        <line x1="368" y1="132" x2="368" y2="112" stroke="#0f766e" strokeWidth="5" strokeLinecap="round" />
        <circle cx="368" cy="106" r="9" fill="#ff6b6b" className="sm-pulse-dot" />
        <rect x="318" y="132" width="100" height="84" rx="30" fill="url(#sm-bot)" stroke="#0f766e" strokeWidth="5" />
        <rect x="332" y="148" width="72" height="50" rx="22" fill="#0b4f4a" />
        <circle cx="352" cy="170" r="7" fill="#7ff5dc" /><circle cx="384" cy="170" r="7" fill="#7ff5dc" />
        <path d="M356 184q12 9 24 0" fill="none" stroke="#7ff5dc" strokeWidth="4" strokeLinecap="round" />
        <rect x="326" y="220" width="84" height="74" rx="26" fill="url(#sm-bot)" stroke="#0f766e" strokeWidth="5" />
        <path className="sm-heart" d="M368 280c-22-14-24-30-14-37 7-5 14-1 14 5 0-6 7-10 14-5 10 7 8 23-14 37z" fill="#ff6b6b" />
        <path d="M296 238c-10 0-16 6-22 14" fill="none" stroke="#0f766e" strokeWidth="14" strokeLinecap="round" />
        <circle cx="270" cy="256" r="11" fill="#ffffff" stroke="#0f766e" strokeWidth="4" />
      </g>
      {/* heartbeat line */}
      <path className="sm-ecg" d="M24 336h96l14-26 20 52 18-40 12 14h296" fill="none" stroke="#0f766e" strokeWidth="4" strokeLinecap="round" strokeLinejoin="round" opacity=".55" />
    </svg>
  );
}
