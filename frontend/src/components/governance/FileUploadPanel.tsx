import { useCallback } from 'react'
import { useDropzone } from 'react-dropzone'
import { ArrowUpTrayIcon, DocumentIcon, XMarkIcon } from '@heroicons/react/24/outline'

interface Props {
  accept?: string[]
  maxSizeMB?: number
  file: File | null
  onChange: (file: File | null) => void
  disabled?: boolean
  label?: string
}

export default function FileUploadPanel({
  accept = ['.csv', '.zip'],
  maxSizeMB = 200,
  file,
  onChange,
  disabled = false,
  label = 'Upload CSV or ZIP',
}: Props) {
  const onDrop = useCallback(
    (accepted: File[]) => {
      if (accepted.length > 0) onChange(accepted[0])
    },
    [onChange],
  )

  const { getRootProps, getInputProps, isDragActive, fileRejections } = useDropzone({
    onDrop,
    accept: Object.fromEntries(
      accept.map((ext) => [
        ext === '.csv' ? 'text/csv' : 'application/zip',
        [ext],
      ]),
    ),
    maxFiles: 1,
    maxSize: maxSizeMB * 1024 * 1024,
    disabled,
  })

  const sizeLabel = file
    ? file.size > 1024 * 1024
      ? `${(file.size / 1024 / 1024).toFixed(1)} MB`
      : `${(file.size / 1024).toFixed(0)} KB`
    : null

  return (
    <div>
      {file ? (
        <div className="flex items-center gap-3 p-4 bg-blue-50 border border-blue-200 rounded-xl">
          <DocumentIcon className="w-8 h-8 text-blue-500 flex-shrink-0" />
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium text-gray-900 truncate">{file.name}</p>
            {sizeLabel && <p className="text-xs text-gray-500">{sizeLabel}</p>}
          </div>
          {!disabled && (
            <button
              onClick={() => onChange(null)}
              className="flex-shrink-0 p-1 text-gray-400 hover:text-red-500 rounded-lg hover:bg-red-50 transition-colors"
              aria-label="Remove file"
            >
              <XMarkIcon className="w-4 h-4" />
            </button>
          )}
        </div>
      ) : (
        <div
          {...getRootProps()}
          className={`border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-colors ${
            isDragActive
              ? 'border-blue-400 bg-blue-50'
              : disabled
              ? 'border-gray-200 bg-gray-50 cursor-not-allowed'
              : 'border-gray-300 hover:border-blue-400 hover:bg-blue-50'
          }`}
        >
          <input {...getInputProps()} />
          <ArrowUpTrayIcon className="w-8 h-8 mx-auto text-gray-400 mb-3" />
          <p className="text-sm font-medium text-gray-700">{label}</p>
          <p className="mt-1 text-xs text-gray-400">
            Drag and drop or click to browse · {accept.join(', ')} · max {maxSizeMB} MB
          </p>
          <p className="mt-2 text-xs text-amber-600 font-medium">
            ⚠ Only CSV or ZIP content packages. Do not upload the Excel dashboard.
          </p>
        </div>
      )}

      {fileRejections.length > 0 && (
        <p className="mt-2 text-xs text-red-600">
          File rejected: {fileRejections[0].errors.map((e) => e.message).join(', ')}
        </p>
      )}
    </div>
  )
}
