interface SavedCvPanelProps {
  count: number;
  onToggle: () => void;
}

export default function SavedCvPanel({ count, onToggle }: SavedCvPanelProps) {
  return (
    <aside className="saved-cv-panel">
      <div className="saved-cv-panel-head">
        <div>
          <span>Kho CV</span>
          <strong>{count}</strong>
        </div>
        <button className="saved-cv-toggle" onClick={onToggle}>
          Xem CV đã lưu
        </button>
      </div>
    </aside>
  );
}
