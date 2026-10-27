import './AiProcessingOverlay.css';

interface AiProcessingOverlayProps {
  active: boolean;
  message: string;
}

export default function AiProcessingOverlay({ active, message }: AiProcessingOverlayProps) {
  if (!active) return null;

  return (
    <div className="ai-processing-backdrop" role="status" aria-live="polite" aria-label={message}>
      <div className="ai-processing-card">
        <video
          className="ai-processing-video"
          src="/ai-loading.mp4"
          autoPlay
          loop
          muted
          playsInline
          preload="auto"
          aria-hidden="true"
        />
        <div className="ai-processing-copy">
          <span className="ai-processing-eyebrow">SoftSync AI</span>
          <h2>{message}</h2>
          <p>Đang xử lý yêu cầu của bạn. Vui lòng chờ trong giây lát.</p>
          <p className="ai-processing-promo">
            Trong lúc chờ, bạn có thể vào trải nghiệm trang web{' '}
            <a href="https://softsync-tech.vercel.app/" target="_blank" rel="noreferrer">
              SoftSync Space
            </a>{' '}
            chính thức.
          </p>
          <span className="ai-processing-dots" aria-hidden="true"><i /><i /><i /></span>
        </div>
      </div>
    </div>
  );
}
