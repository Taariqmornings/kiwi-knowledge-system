type IconProps = { className?: string; active?: boolean };

export const Search = ({ className }: IconProps) => (
  <svg className={className ?? "w-5 h-5"} fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" /></svg>
);

export const Library = ({ className }: IconProps) => (
  <svg className={className ?? "w-5 h-5"} fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M8 14v3m4-3v3m4-3v3M3 21h18M3 10h18M3 7l9-4 9 4M4 10h16v11H4V10z" /></svg>
);

export const Settings = ({ className }: IconProps) => (
  <svg className={className ?? "w-5 h-5"} fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" /><path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" /></svg>
);

export const Bookmark = ({ className, active }: IconProps) => (
  <svg className={className ?? "w-5 h-5"} fill={active ? "currentColor" : "none"} stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M5 5a2 2 0 012-2h10a2 2 0 012 2v16l-7-3.5L5 21V5z" /></svg>
);

export const History = ({ className }: IconProps) => (
  <svg className={className ?? "w-5 h-5"} fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
);

export const Send = ({ className }: IconProps) => (
  <svg className={className ?? "w-4 h-4"} fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" d="M5 12l14-7-4 14-3-5-7-2z" />
  </svg>
);

export const Trash = ({ className }: IconProps) => (
  <svg className={className ?? "w-4 h-4"} fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" /></svg>
);

export const ArrowLeft = ({ className }: IconProps) => (
  <svg className={className ?? "w-4 h-4"} fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M10 19l-7-7m0 0l7-7m-7 7h18" /></svg>
);

export const ArrowRight = ({ className }: IconProps) => (
  <svg className={className ?? "w-4 h-4"} fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M14 5l7 7m0 0l-7 7m7-7H3" /></svg>
);

export const Refresh = ({ className }: IconProps) => (
  <svg className={className ?? "w-4 h-4"} fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" d="M3 12a9 9 0 0115.59-6.36L21 8m0 0V3m0 5h-5" />
    <path strokeLinecap="round" strokeLinejoin="round" d="M21 12a9 9 0 01-15.59 6.36L3 16m0 0v5m0-5h5" />
  </svg>
);

export const Plus = ({ className }: IconProps) => (
  <svg className={className ?? "w-4 h-4"} fill="none" stroke="currentColor" strokeWidth="2.5" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" d="M12 5v14M5 12h14" />
  </svg>
);

export const Sparkle = ({ className }: IconProps) => (
  <svg className={className ?? "w-4 h-4"} fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" d="M12 3l1.7 5.3L19 10l-5.3 1.7L12 17l-1.7-5.3L5 10l5.3-1.7z" />
  </svg>
);

export const Close = ({ className }: IconProps) => (
  <svg className={className ?? "w-3 h-3"} fill="none" stroke="currentColor" strokeWidth="2.5" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" /></svg>
);

export const Moon = ({ className }: IconProps) => (
  <svg className={className ?? "w-5 h-5"} fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z" /></svg>
);

export const Sun = ({ className }: IconProps) => (
  <svg className={className ?? "w-5 h-5"} fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364-6.364l-.707.707M6.343 17.657l-.707.707m0-12.728l.707.707m12.728 12.728l.707.707M12 8a4 4 0 100 8 4 4 0 000-8z" /></svg>
);

export const Play = ({ className }: IconProps) => (
  <svg className={className ?? "w-4 h-4"} fill="currentColor" viewBox="0 0 24 24"><path d="M8 5v14l11-7z" /></svg>
);

export const Pause = ({ className }: IconProps) => (
  <svg className={className ?? "w-4 h-4"} fill="currentColor" viewBox="0 0 24 24"><path d="M6 19h4V5H6v14zm8-14v14h4V5h-4z" /></svg>
);