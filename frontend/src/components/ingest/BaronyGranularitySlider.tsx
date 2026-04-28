import { useState } from 'react'

export type BaronyCount = 50 | 250 | 1000 | 'all'

const PRESETS: { value: BaronyCount; label: string }[] = [
  { value: 50, label: '50' },
  { value: 250, label: '250' },
  { value: 1000, label: '1000' },
  { value: 'all', label: 'Todos' },
]

interface Props {
  value?: BaronyCount
  onChange: (count: BaronyCount) => void
}

export function BaronyGranularitySlider({ value = 250, onChange }: Props) {
  const [selected, setSelected] = useState<BaronyCount>(value)
  const handleClick = (v: BaronyCount) => {
    setSelected(v)
    onChange(v)
  }
  return (
    <div className="flex flex-col gap-2">
      <label className="text-sm font-medium">Granularidade de baronies</label>
      <div className="flex gap-2">
        {PRESETS.map((p) => (
          <button
            key={String(p.value)}
            type="button"
            onClick={() => handleClick(p.value)}
            className={
              'px-3 py-1 rounded border text-sm ' +
              (selected === p.value
                ? 'bg-blue-600 text-white border-blue-600'
                : 'bg-white text-gray-700 border-gray-300 hover:bg-gray-50')
            }
          >
            {p.label}
          </button>
        ))}
      </div>
      <p className="text-xs text-gray-500">
        Selecionado:{' '}
        <strong>{selected === 'all' ? 'Todos os municípios' : selected}</strong>
      </p>
    </div>
  )
}
