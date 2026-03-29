import '../ui/Skeleton.css';

export default function DashboardSkeleton() {
  return (
    <div className="dashboard-container dashboard-skeleton-wrap" dir="rtl">
      <div className="st-skel" style={{ height: 36, width: '55%', maxWidth: 320, marginBottom: 24 }} />
      <div style={{ display: 'flex', gap: 12, marginBottom: 20, flexWrap: 'wrap' }}>
        <div className="st-skel" style={{ height: 40, width: 120, borderRadius: 10 }} />
        <div className="st-skel" style={{ height: 40, width: 120, borderRadius: 10 }} />
        <div className="st-skel" style={{ height: 40, width: 120, borderRadius: 10 }} />
      </div>
      <div className="st-skel" style={{ height: 140, width: '100%', maxWidth: 720, marginBottom: 16 }} />
      <div className="st-skel" style={{ height: 140, width: '100%', maxWidth: 720, marginBottom: 16 }} />
      <div className="st-skel" style={{ height: 140, width: '100%', maxWidth: 720 }} />
      <p className="dashboard-skeleton-hint">טוען את האזור האישי…</p>
    </div>
  );
}
