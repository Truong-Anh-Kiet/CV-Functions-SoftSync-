interface StructuredDataViewerProps {
  data: any;
}

export default function StructuredDataViewer({ data }: StructuredDataViewerProps) {
  if (!data) return <span className="structured-empty-text">(Không có dữ liệu)</span>;
  const entries = Object.entries(data);

  const formatValueText = (text: string) => {
    const lowerText = text.toLowerCase();
    if (lowerText === 'missing_section') return <span className="json-val-missing">"{text}"</span>;

    const items = text.split(/\n|(?<=\s|^)[•●\-\*]\s/g).filter(item => item.trim() !== "");

    return (
      <span className="json-val-found">
        "
        {items.map((content, i) => (
          <span key={i} style={{
            display: 'block',
            paddingLeft: '14px',
            marginBottom: '4px',
            textIndent: '-14px'
          }}>
            {i > 0 ? "• " : ""}{content.trim()}
          </span>
        ))}
        "
      </span>
    );
  };

  return (
    <div className="structured-json-viewer">
      {"{"}
      {entries.map(([key, value], index) => (
        <div key={key} style={{ paddingLeft: '20px', marginBottom: '20px' }}>
          <span className="json-key">"{key}"</span>:{" "}
          {formatValueText(String(value))}
          {index < entries.length - 1 ? "," : ""}
        </div>
      ))}
      {"}"}
    </div>
  );
}
