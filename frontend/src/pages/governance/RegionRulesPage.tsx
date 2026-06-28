import { MapPinIcon } from '@heroicons/react/24/outline'
import RegionBadge from '@/components/governance/RegionBadge'

const KNOWN_REGIONS = [
  {
    code: 'UK',
    name: 'United Kingdom',
    notes: 'GPhC-regulated; BNF/NICE standards; SPCs from MHRA; NICE guidelines required for clinical sign-off.',
  },
  {
    code: 'US',
    name: 'United States',
    notes: 'FDA/DEA-regulated; USP standards; NDC drug identifiers; state-level pharmacy board rules apply.',
  },
  {
    code: 'GCC',
    name: 'Gulf Cooperation Council',
    notes: 'Multiple national regulators (MOH UAE, SFDA KSA, etc.); Arabic transliteration considerations.',
  },
  {
    code: 'AU',
    name: 'Australia',
    notes: 'AHPRA/Pharmacy Board regulated; TGA standards; PBS formulary references.',
  },
]

export default function RegionRulesPage() {
  return (
    <div className="space-y-6 max-w-3xl">
      <div className="flex items-start gap-3 p-4 bg-blue-50 border border-blue-200 rounded-xl text-sm text-blue-700">
        <MapPinIcon className="w-5 h-5 flex-shrink-0 mt-0.5" />
        <div>
          <p className="font-semibold">Region publishing rules — read-only view</p>
          <p className="mt-1 text-xs text-blue-600">
            Region rules exist in the backend as <span className="font-mono">RegionPublishingRule</span> records
            and are seeded automatically during import. Management endpoints (create / update / delete) are not
            yet exposed in the API. To modify rules, update the seed data and re-run the migration or import.
          </p>
        </div>
      </div>

      <div className="space-y-3">
        {KNOWN_REGIONS.map((r) => (
          <div key={r.code} className="bg-white border border-gray-200 rounded-xl p-5">
            <div className="flex items-center gap-3 mb-2">
              <RegionBadge region={r.code} />
              <span className="font-semibold text-gray-800 text-sm">{r.name}</span>
            </div>
            <p className="text-xs text-gray-500">{r.notes}</p>
          </div>
        ))}
      </div>

      <div className="p-4 bg-gray-50 border border-gray-200 rounded-xl text-xs text-gray-500 space-y-1">
        <p className="font-medium text-gray-600">How regions work in this system</p>
        <ul className="list-disc list-inside space-y-0.5 mt-1">
          <li>Content items carry a <span className="font-mono">region_scope</span> array set at import time.</li>
          <li>Publishing is per-item per-region — a UK publish does not affect US availability.</li>
          <li>Approval batches are scoped to one or more regions at creation.</li>
          <li>Evidence sources can be region-specific or global.</li>
          <li>
            Region rules are checked at publish time by the backend; this UI shows the current known
            regions for reference only.
          </li>
        </ul>
      </div>
    </div>
  )
}
