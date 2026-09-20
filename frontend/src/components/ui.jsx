import { useEffect, useRef, useState } from 'react'

export function Button({ variant = 'primary', loading, children, className = '', ...props }) {
  return <button className={`button button--${variant} ${className}`} disabled={loading || props.disabled} {...props}>{loading ? 'Please wait…' : children}</button>
}
export function Card({ children, className = '', ...props }) { return <section className={`card ${className}`} {...props}>{children}</section> }
const labels = { pending: 'Pending', confirmed: 'Confirmed', rejected: 'Rejected', cancelled: 'Cancelled', completed: 'Completed', no_show: 'No-show' }
export function StatusBadge({ status }) { return <span className={`badge badge--${status}`}>{labels[status] ?? status}</span> }
export function Input({ label, id, ...props }) { return <label className="field" htmlFor={id}><span>{label}</span><input id={id} {...props} /></label> }
export function SearchInput({ label = 'Search', ...props }) { return <Input label={label} type="search" {...props} /> }
export function Select({ label, id, children, ...props }) { return <label className="field" htmlFor={id}><span>{label}</span><select id={id} {...props}>{children}</select></label> }
export function Textarea({ label, id, ...props }) { return <label className="field" htmlFor={id}><span>{label}</span><textarea id={id} {...props} /></label> }
export function StatCard({ label, value, trend }) { return <Card className="stat-card"><span>{label}</span><strong>{value}</strong>{trend && <small>{trend}</small>}</Card> }
export function Avatar({ name = 'User' }) { return <span className="avatar" aria-label={name}>{name.split(' ').map(x => x[0]).join('').slice(0, 2)}</span> }
export function EmptyState({ title = 'Nothing here yet', children }) { return <Card className="state"><h2>{title}</h2><p>{children}</p></Card> }
export function LoadingState() { return <div className="skeleton" aria-label="Loading" /> }
export function ErrorState({ children = 'Something went wrong.' }) { return <Card className="state state--error" role="alert">{children}</Card> }
export function Tabs({ items, active, onChange }) { return <div className="tabs" role="tablist">{items.map(item => <button key={item.id} role="tab" aria-selected={active === item.id} onClick={() => onChange(item.id)}>{item.label}</button>)}</div> }
export function Tooltip({ label, children }) { return <span className="tooltip" tabIndex="0">{children}<span role="tooltip">{label}</span></span> }
export function Modal({ open, title, children, onClose }) { if (!open) return null; return <div className="dialog-backdrop" role="presentation"><section className="dialog" role="dialog" aria-modal="true" aria-label={title}><header><h2>{title}</h2><button onClick={onClose} aria-label="Close dialog">×</button></header>{children}</section></div> }
export function AppointmentSummary({ doctor, specialty, startAt, status }) { return <Card className="appointment-summary"><StatusBadge status={status} /><h3>{doctor}</h3><p>{specialty}</p><time>{startAt}</time></Card> }
export function MedicalModel({ src, alt = 'Medical model placeholder' }) { const [failed, setFailed] = useState(false); return <div className="model-stage" aria-label={alt}>{src && !failed ? <model-viewer src={src} alt={alt} camera-controls onError={() => setFailed(true)} /> : <p>3D medical visual ready when an optimized GLB/GLTF asset is supplied.</p>}</div> }
