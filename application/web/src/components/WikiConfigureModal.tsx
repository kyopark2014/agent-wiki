import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { api, type WikiBrowseResult } from "../api";

const SOURCE_SLOTS = 3;

interface Props {
  onClose: () => void;
}

function emptySlots(values: string[] = [], count = SOURCE_SLOTS): string[] {
  const next = [...values];
  while (next.length < count) next.push("");
  return next.slice(0, count);
}

function shortPath(path: string): string {
  const home = "/Users/";
  if (path.startsWith(home)) {
    const rest = path.slice(home.length);
    const slash = rest.indexOf("/");
    if (slash >= 0) return `~${rest.slice(slash)}`;
  }
  if (path.startsWith("/home/")) {
    const parts = path.split("/");
    if (parts.length > 3) return `~/${parts.slice(3).join("/")}`;
  }
  return path;
}

export function WikiConfigureModal({ onClose }: Props) {
  const [sourceSlots, setSourceSlots] = useState<string[]>(emptySlots());
  const [urlInput, setUrlInput] = useState("");
  const [urlHistory, setUrlHistory] = useState<string[]>([]);
  const [wikiDir, setWikiDir] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [addingUrl, setAddingUrl] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [menuIndex, setMenuIndex] = useState<number | null>(null);
  const sourceBtnRefs = useRef<Array<HTMLButtonElement | null>>([]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const data = await api.getWikiSources();
        if (cancelled) return;
        setWikiDir(data.wiki_dir || "");
        setSourceSlots(emptySlots(data.folders || [], data.max_sources || SOURCE_SLOTS));
        setUrlHistory(data.urls || []);
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : String(err));
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") {
        if (menuIndex !== null) {
          setMenuIndex(null);
          return;
        }
        if (!busy && !addingUrl) onClose();
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [busy, addingUrl, menuIndex, onClose]);

  async function handleSaveSources() {
    setBusy(true);
    setError(null);
    setSuccess(null);
    try {
      const folders = sourceSlots.map((s) => s.trim()).filter(Boolean);
      const saved = await api.putWikiSources({ folders });
      setSourceSlots(emptySlots(saved.folders || [], saved.max_sources || SOURCE_SLOTS));
      setUrlHistory(saved.urls || []);
      setSuccess(
        saved.folders.length > 0
          ? `Source ${saved.folders.length}개를 저장했습니다. Sync 시 해당 폴더를 추출합니다.`
          : "Sources를 비웠습니다. Sync 시 raw(또는 Wiki 루트)를 사용합니다.",
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  async function handleAddUrl() {
    const url = urlInput.trim();
    if (!url) {
      setError("URL을 입력하세요.");
      return;
    }
    setAddingUrl(true);
    setError(null);
    setSuccess(null);
    try {
      const result = await api.ingestWikiUrl(url);
      setUrlInput("");
      setUrlHistory(result.urls || []);
      setSuccess(
        `URL을 ${result.path || `${wikiDir || "wiki"}/raw`}에 저장했습니다.`,
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setAddingUrl(false);
    }
  }

  function applySourcePath(index: number, path: string) {
    const next = [...sourceSlots];
    next[index] = path;
    setSourceSlots(next);
    setMenuIndex(null);
    setSuccess(null);
    setError(null);
  }

  function clearSourcePath(index: number) {
    applySourcePath(index, "");
  }

  const historyNewestFirst = [...urlHistory].reverse();

  return createPortal(
    <div
      className="modal-overlay"
      role="dialog"
      aria-modal="true"
      aria-labelledby="wiki-configure-title"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget && !busy && !addingUrl && menuIndex === null) {
          onClose();
        }
      }}
    >
      <div className="modal wiki-configure-modal">
        <h2 id="wiki-configure-title">Wiki Configure</h2>
        <p className="wiki-configure-help">
          Sync Source는 최대 {SOURCE_SLOTS}개까지 지정할 수 있습니다. Source를
          선택하면 폴더 메뉴가 열립니다. URL은 입력 즉시{" "}
          <code>{wikiDir || ".session_storage/{user}/wiki"}/raw</code>에
          저장되고, 이력·Sources는{" "}
          <code>{wikiDir || ".session_storage/{user}/wiki"}/wiki_sources.json</code>
          에 쌓입니다. Sources를 비우면{" "}
          <code>{wikiDir || "wiki"}/raw</code>(없으면 Wiki 루트)를 Sync합니다.
        </p>
        {loading ? (
          <p className="llm-gateway-muted">불러오는 중…</p>
        ) : (
          <>
            <div className="wiki-configure-section-label">Sources</div>
            <div className="wiki-configure-sources">
              {sourceSlots.map((value, index) => (
                <button
                  key={`source-${index}`}
                  ref={(el) => {
                    sourceBtnRefs.current[index] = el;
                  }}
                  type="button"
                  className={`wiki-configure-source-btn${menuIndex === index ? " is-open" : ""}`}
                  disabled={busy || addingUrl}
                  aria-haspopup="dialog"
                  aria-expanded={menuIndex === index}
                  onClick={() =>
                    setMenuIndex((cur) => (cur === index ? null : index))
                  }
                >
                  <span className="wiki-configure-source-label">
                    Source {index + 1}
                  </span>
                  <span className="wiki-configure-source-path">
                    {value ? shortPath(value) : "경로 선택…"}
                  </span>
                </button>
              ))}
            </div>
            {menuIndex !== null ? (
              <SourceFolderMenu
                index={menuIndex}
                currentPath={sourceSlots[menuIndex] || ""}
                wikiDir={wikiDir}
                anchorEl={sourceBtnRefs.current[menuIndex]}
                onSelect={(path) => applySourcePath(menuIndex, path)}
                onClear={() => clearSourcePath(menuIndex)}
                onClose={() => setMenuIndex(null)}
              />
            ) : null}
            <div className="wiki-configure-section-label">URL</div>
            <div className="wiki-configure-url-row">
              <label className="llm-gateway-field wiki-configure-url-field">
                <span>문서 URL</span>
                <input
                  type="url"
                  value={urlInput}
                  placeholder="예: https://example.com/article"
                  disabled={busy || addingUrl}
                  autoComplete="off"
                  onChange={(e) => setUrlInput(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") {
                      e.preventDefault();
                      void handleAddUrl();
                    }
                  }}
                />
              </label>
              <button
                type="button"
                className="modal-btn-primary wiki-configure-url-add"
                disabled={busy || addingUrl || !urlInput.trim()}
                onClick={() => void handleAddUrl()}
              >
                {addingUrl ? "저장 중…" : "추가"}
              </button>
            </div>
            {historyNewestFirst.length > 0 ? (
              <div className="wiki-configure-url-history">
                <div className="wiki-configure-section-label">URL 이력</div>
                <ul>
                  {historyNewestFirst.map((url, index) => (
                    <li key={`${url}-${urlHistory.length - index}`}>
                      <a href={url} target="_blank" rel="noreferrer">
                        {url}
                      </a>
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}
          </>
        )}
        {error ? (
          <p className="modal-error" role="alert">
            {error}
          </p>
        ) : null}
        {success ? <p className="llm-gateway-success">{success}</p> : null}
        <div className="modal-actions">
          <button
            type="button"
            className="modal-btn-secondary"
            disabled={busy || addingUrl}
            onClick={onClose}
          >
            닫기
          </button>
          <button
            type="button"
            className="modal-btn-primary"
            disabled={busy || addingUrl || loading}
            onClick={() => void handleSaveSources()}
          >
            {busy ? "저장 중…" : "Sources 저장"}
          </button>
        </div>
      </div>
    </div>,
    document.body,
  );
}

interface SourceFolderMenuProps {
  index: number;
  currentPath: string;
  wikiDir: string;
  anchorEl: HTMLElement | null;
  onSelect: (path: string) => void;
  onClear: () => void;
  onClose: () => void;
}

function SourceFolderMenu({
  index,
  currentPath,
  wikiDir,
  anchorEl,
  onSelect,
  onClear,
  onClose,
}: SourceFolderMenuProps) {
  const menuRef = useRef<HTMLDivElement>(null);
  const [browse, setBrowse] = useState<WikiBrowseResult | null>(null);
  const [pathDraft, setPathDraft] = useState(currentPath);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [position, setPosition] = useState<{
    left: number;
    top: number;
    width: number;
  } | null>(null);

  async function loadBrowse(path?: string) {
    setLoading(true);
    setError(null);
    try {
      const data = await api.browseWikiSources(path);
      setBrowse(data);
      setPathDraft(data.path);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadBrowse(currentPath || wikiDir || undefined);
  }, [currentPath, wikiDir]);

  function updatePosition() {
    if (!anchorEl) return;
    const rect = anchorEl.getBoundingClientRect();
    const width = Math.max(rect.width, 320);
    const left = Math.min(
      Math.max(8, rect.left),
      window.innerWidth - width - 8,
    );
    const top = Math.min(rect.bottom + 6, window.innerHeight - 360);
    setPosition({ left, top, width });
  }

  useLayoutEffect(() => {
    updatePosition();
  }, [anchorEl]);

  useEffect(() => {
    if (!anchorEl) return;
    updatePosition();
    window.addEventListener("resize", updatePosition);
    window.addEventListener("scroll", updatePosition, true);

    function onPointerDown(e: MouseEvent) {
      const target = e.target as Node;
      if (menuRef.current?.contains(target)) return;
      if (anchorEl?.contains(target)) return;
      onClose();
    }

    document.addEventListener("mousedown", onPointerDown);
    return () => {
      window.removeEventListener("resize", updatePosition);
      window.removeEventListener("scroll", updatePosition, true);
      document.removeEventListener("mousedown", onPointerDown);
    };
  }, [anchorEl, onClose]);

  if (!position) return null;

  return createPortal(
    <div
      ref={menuRef}
      className="wiki-source-menu"
      role="dialog"
      aria-label={`Source ${index + 1} 폴더 선택`}
      style={{
        left: position.left,
        top: position.top,
        width: position.width,
      }}
    >
      <div className="wiki-source-menu-header">Source {index + 1}</div>
      <div className="wiki-source-menu-shortcuts">
        {(browse?.shortcuts || []).map((item) => (
          <button
            key={item.path}
            type="button"
            className="wiki-source-menu-chip"
            onClick={() => void loadBrowse(item.path)}
          >
            {item.name}
          </button>
        ))}
      </div>
      <div className="wiki-source-menu-pathrow">
        <input
          type="text"
          value={pathDraft}
          placeholder="폴더 경로"
          autoComplete="off"
          onChange={(e) => setPathDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              void loadBrowse(pathDraft.trim());
            }
          }}
        />
        <button
          type="button"
          className="modal-btn-secondary"
          onClick={() => void loadBrowse(pathDraft.trim())}
        >
          이동
        </button>
      </div>
      {error ? (
        <p className="modal-error" role="alert">
          {error}
        </p>
      ) : null}
      <div className="wiki-source-menu-list">
        {loading ? (
          <div className="wiki-source-menu-empty">불러오는 중…</div>
        ) : (
          <>
            {browse?.parent ? (
              <button
                type="button"
                className="wiki-source-menu-item"
                onClick={() => void loadBrowse(browse.parent || undefined)}
              >
                ← ..
              </button>
            ) : null}
            {(browse?.dirs || []).length === 0 ? (
              <div className="wiki-source-menu-empty">하위 폴더가 없습니다.</div>
            ) : (
              browse?.dirs.map((dir) => (
                <button
                  key={dir.path}
                  type="button"
                  className="wiki-source-menu-item"
                  onClick={() => void loadBrowse(dir.path)}
                >
                  {dir.name}/
                </button>
              ))
            )}
          </>
        )}
      </div>
      <div className="wiki-source-menu-actions">
        <button type="button" className="modal-btn-secondary" onClick={onClear}>
          비우기
        </button>
        <button
          type="button"
          className="modal-btn-primary"
          disabled={!browse?.path}
          onClick={() => {
            if (browse?.path) onSelect(browse.path);
          }}
        >
          이 폴더 선택
        </button>
      </div>
    </div>,
    document.body,
  );
}
