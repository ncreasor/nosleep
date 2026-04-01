'use client'
import { useState } from 'react'
import { Folder } from 'lucide-react'
import { COLOR_PALETTE } from '@/lib/folderColors'

export default function FolderColorPicker({
  selectedColor,
  previewName,
  previewDocType,
  onSelect,
}) {
  const [hoverColor, setHoverColor] = useState(null)
  const displayColor = hoverColor || selectedColor

  return (
    <div className="flex flex-col gap-2">
      <label className="text-xs font-medium text-gray-600">Цвет папки</label>
      <div className="flex gap-4 items-start">
        {/* Swatches grid — 6 per row, 2 rows */}
        <div className="grid grid-cols-6 gap-2 flex-shrink-0">
          {COLOR_PALETTE.map(({ hex, label }) => (
            <button
              key={hex}
              type="button"
              title={label}
              onMouseEnter={() => setHoverColor(hex)}
              onMouseLeave={() => setHoverColor(null)}
              onClick={() => onSelect(hex)}
              className="w-6 h-6 rounded-full transition-transform hover:scale-110 focus:outline-none"
              style={{
                backgroundColor: hex,
                outline: selectedColor === hex ? `2px solid ${hex}` : 'none',
                outlineOffset: '2px',
              }}
            />
          ))}
        </div>

        {/* Live preview folder card */}
        <div
          className="flex flex-col items-center justify-center rounded-xl p-3 border border-gray-100 w-24 h-24 flex-shrink-0"
          style={{ backgroundColor: `${displayColor}18` }}
        >
          <Folder size={28} style={{ color: displayColor }} />
          <p className="text-xs font-semibold text-ink mt-1 text-center line-clamp-2 leading-tight">
            {previewName || 'Папка'}
          </p>
          <p className="text-[10px] text-gray-400 mt-0.5 text-center truncate w-full">
            {previewDocType}
          </p>
        </div>
      </div>
    </div>
  )
}
