import { useEffect, useState } from "react";
import { createPortal } from "react-dom";

interface Props {
  title: string;
  description: string;
  modelOptions: string[];
  initialModel: string;
  confirmLabel?: string;
  onConfirm: (model: string) => void;
  onCancel: () => void;
}

export function WikiSyncStartModal({
  title,
  description,
  modelOptions,
  initialModel,
  confirmLabel = "시작",
  onConfirm,
  onCancel,
}: Props) {
  const fallback = modelOptions[0] || initialModel || "";
  const [model, setModel] = useState(
    modelOptions.includes(initialModel) ? initialModel : fallback,
  );

  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") onCancel();
      if (e.key === "Enter" && model.trim()) onConfirm(model.trim());
    }
    window.addEventListener("keydown", onKeyDown);
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", onKeyDown);
      document.body.style.overflow = prev;
    };
  }, [model, onCancel, onConfirm]);

  return createPortal(
    <div
      className="modal-overlay"
      role="dialog"
      aria-modal="true"
      aria-labelledby="wiki-sync-start-title"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onCancel();
      }}
    >
      <div className="modal wiki-sync-start-modal">
        <h2 id="wiki-sync-start-title">{title}</h2>
        <p className="wiki-sync-start-desc">{description}</p>

        <label className="llm-gateway-field">
          <span>모델</span>
          <select
            value={model}
            onChange={(e) => setModel(e.target.value)}
            aria-label="Wiki Sync 모델"
          >
            {modelOptions.length === 0 ? (
              <option value={model || ""}>{model || "모델 없음"}</option>
            ) : (
              modelOptions.map((name) => (
                <option key={name} value={name}>
                  {name}
                </option>
              ))
            )}
          </select>
        </label>
        <p className="llm-gateway-muted">
          채팅에서 선택한 모델과 동일하게 Wiki PDF/그래프 추출에 사용합니다.
        </p>

        <div className="modal-actions">
          <button type="button" className="modal-btn-secondary" onClick={onCancel}>
            취소
          </button>
          <button
            type="button"
            className="modal-btn-primary"
            disabled={!model.trim()}
            onClick={() => onConfirm(model.trim())}
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>,
    document.body,
  );
}
