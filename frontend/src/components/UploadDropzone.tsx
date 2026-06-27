import { useCallback, useState } from 'react'
import { useDropzone, type FileRejection } from 'react-dropzone'
import { ArrowUpTrayIcon, DocumentIcon, XMarkIcon } from '@heroicons/react/24/outline'
import toast from 'react-hot-toast'

interface Props {
  onFilesSelected: (files: File[]) => void
  maxSizeMb?: number
  accept?: Record<string, string[]>
  multiple?: boolean
}

const DEFAULT_ACCEPT = {
  'application/pdf': ['.pdf'],
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
  'text/plain': ['.txt'],
  'image/png': ['.png'],
  'image/jpeg': ['.jpg', '.jpeg'],
}

function formatBytes(bytes: number) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1_048_576) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1_048_576).toFixed(1)} MB`
}

export default function UploadDropzone({
  onFilesSelected,
  maxSizeMb = 50,
  accept = DEFAULT_ACCEPT,
  multiple = false,
}: Props) {
  const [pendingFiles, setPendingFiles] = useState<File[]>([])

  const onDrop = useCallback(
    (accepted: File[], rejected: FileRejection[]) => {
      rejected.forEach(({ file, errors }) => {
        toast.error(`${file.name}: ${errors[0]?.message ?? 'Rejected'}`)
      })
      if (accepted.length > 0) {
        setPendingFiles(multiple ? (prev) => [...prev, ...accepted] : accepted)
        onFilesSelected(multiple ? [...pendingFiles, ...accepted] : accepted)
      }
    },
    [multiple, onFilesSelected, pendingFiles],
  )

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept,
    maxSize: maxSizeMb * 1_048_576,
    multiple,
  })

  const remove = (name: string) => {
    const next = pendingFiles.filter((f) => f.name !== name)
    setPendingFiles(next)
    onFilesSelected(next)
  }

  return (
    <div className="space-y-3">
      <div
        {...getRootProps()}
        className={`
          relative border-2 border-dashed rounded-xl p-10 text-center cursor-pointer transition-colors
          ${isDragActive
            ? 'border-primary-400 bg-primary-50'
            : 'border-gray-300 hover:border-primary-300 hover:bg-gray-50'
          }
        `}
      >
        <input {...getInputProps()} />
        <ArrowUpTrayIcon className="mx-auto h-10 w-10 text-gray-400 mb-3" />
        <p className="text-sm font-medium text-gray-700">
          {isDragActive ? 'Drop your file here' : 'Drag & drop or click to browse'}
        </p>
        <p className="mt-1 text-xs text-gray-400">
          PDF, DOCX, TXT, PNG, JPG — max {maxSizeMb} MB
        </p>
      </div>

      {pendingFiles.length > 0 && (
        <ul className="space-y-2">
          {pendingFiles.map((f) => (
            <li
              key={f.name}
              className="flex items-center gap-3 px-3 py-2 bg-gray-50 rounded-lg border border-gray-200"
            >
              <DocumentIcon className="w-4 h-4 text-gray-400 flex-shrink-0" />
              <span className="text-sm text-gray-700 truncate flex-1">{f.name}</span>
              <span className="text-xs text-gray-400 flex-shrink-0">{formatBytes(f.size)}</span>
              <button
                type="button"
                onClick={() => remove(f.name)}
                className="flex-shrink-0 text-gray-400 hover:text-red-500 transition-colors"
              >
                <XMarkIcon className="w-4 h-4" />
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
