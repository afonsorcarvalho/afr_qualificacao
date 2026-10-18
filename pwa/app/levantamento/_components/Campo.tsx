'use client'
import type { ReactNode } from 'react'

const BASE = 'min-h-[44px] w-full rounded-md border border-input bg-background px-3 text-sm'

export function Campo({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="block space-y-1">
      <span className="text-xs font-medium text-muted-foreground">{label}</span>
      {children}
    </label>
  )
}

export function CampoTexto({
  label, value, onChange, type = 'text', multiline = false,
}: {
  label: string
  value: unknown
  onChange: (v: string) => void
  type?: 'text' | 'number'
  multiline?: boolean
}) {
  const v = value === false || value === undefined || value === null ? '' : String(value)
  return (
    <Campo label={label}>
      {multiline ? (
        <textarea className={`${BASE} py-2`} rows={3} value={v} onChange={(e) => onChange(e.target.value)} />
      ) : (
        <input
          className={BASE}
          type={type}
          inputMode={type === 'number' ? 'decimal' : undefined}
          step={type === 'number' ? 'any' : undefined}
          value={v}
          onChange={(e) => onChange(e.target.value)}
        />
      )}
    </Campo>
  )
}

export function CampoSelect({
  label, value, onChange, options,
}: {
  label: string
  /** id numérico (many2one), string (selection) ou false/undefined. */
  value: unknown
  onChange: (v: string) => void
  options: { value: string; label: string }[]
}) {
  const v = value === false || value === undefined || value === null ? '' : String(value)
  return (
    <Campo label={label}>
      <select className={BASE} value={v} onChange={(e) => onChange(e.target.value)}>
        <option value="">—</option>
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
    </Campo>
  )
}
