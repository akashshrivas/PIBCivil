"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect } from "react";

export default function Modal({ children }: { children: React.ReactNode }) {
  const router = useRouter();

  // router.back() rather than router.push("/") -- this is what makes the
  // URL in the address bar revert to wherever the person actually came
  // from (including any filters/search they had applied), not just "/".
  const close = useCallback(() => router.back(), [router]);

  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") close();
    }
    document.addEventListener("keydown", onKeyDown);
    document.body.style.overflow = "hidden"; // lock background scroll while open
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      document.body.style.overflow = "";
    };
  }, [close]);

  return (
    <div className="modal-overlay" onClick={close}>
      <div
        className="modal-panel"
        role="dialog"
        aria-modal="true"
        onClick={(e) => e.stopPropagation()}
      >
        <button type="button" className="modal-close" onClick={close} aria-label="Close">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
            <line x1="18" y1="6" x2="6" y2="18" />
            <line x1="6" y1="6" x2="18" y2="18" />
          </svg>
        </button>
        {children}
      </div>
    </div>
  );
}
