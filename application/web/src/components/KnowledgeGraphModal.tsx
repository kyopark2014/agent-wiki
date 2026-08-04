import { useEffect } from "react";
import { createPortal } from "react-dom";
import { CloseIcon } from "./SidebarIcons";

interface Props {
  userId: string;
  title: string;
  onClose: () => void;
}

export function KnowledgeGraphModal({ userId, title, onClose }: Props) {
  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    window.addEventListener("keydown", onKeyDown);
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", onKeyDown);
      document.body.style.overflow = prev;
    };
  }, [onClose]);

  return createPortal(
    <div
      className="modal-overlay knowledge-graph-modal"
      role="dialog"
      aria-modal="true"
      aria-label={title}
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="knowledge-graph-panel">
        <button
          type="button"
          className="knowledge-graph-close"
          aria-label="닫기"
          onClick={onClose}
        >
          <CloseIcon className="sidebar-icon" />
        </button>
        <iframe
          className="knowledge-graph-frame"
          title={`${userId} knowledge graph`}
          src="/api/graph"
          sandbox="allow-scripts allow-same-origin allow-popups"
        />
      </div>
    </div>,
    document.body,
  );
}
