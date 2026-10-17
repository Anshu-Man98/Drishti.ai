import React from 'react';
import { Receipt } from 'lucide-react';
import { Claim } from '../../types';
import { formatINR } from '../../utils/formatters';

interface BillLineItemsTableProps {
  claim: Claim;
}

export const BillLineItemsTable: React.FC<BillLineItemsTableProps> = ({ claim }) => {
  return (
    <div className="bg-surface/80 border border-white/8 rounded-[20px] p-5 sm:p-6 shadow-2xs backdrop-blur-md space-y-4">
      <div className="flex items-center justify-between border-b border-white/8 pb-3">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-muted flex items-center gap-1.5">
          <Receipt className="w-3.5 h-3.5 text-amber-primary" />
          <span>Itemized Medical Bill Breakdown ({claim.line_items.length} items)</span>
        </h3>
        <span className="text-[10px] font-mono text-muted">
          Deterministic Math Validation
        </span>
      </div>

      <div className="overflow-x-auto rounded-xl border border-white/8">
        <table className="w-full text-left text-xs text-text-primary">
          <thead className="bg-surface-elevated/80 border-b border-white/8 text-muted">
            <tr>
              <th className="py-2.5 px-3.5 font-semibold">Description</th>
              <th className="py-2.5 px-3.5 text-right font-semibold">Qty / Days</th>
              <th className="py-2.5 px-3.5 text-right font-semibold">Unit Price</th>
              <th className="py-2.5 px-3.5 text-right font-semibold">Amount</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-white/6 bg-surface-elevated/40">
            {claim.line_items.map((item, idx) => (
              <tr
                key={idx}
                className="hover:bg-white/3 transition-colors"
              >
                <td className="py-2.5 px-3.5 font-medium text-text-primary">
                  <div className="flex items-center gap-2">
                    <span>{item.description}</span>
                    {item.bbox && (
                      <span
                        className="text-[9px] px-1.5 py-0.2 rounded-full bg-amber-primary/10 text-amber-primary font-mono border border-amber-primary/20"
                        title="Document AI Extracted Bounding Box"
                      >
                        docai
                      </span>
                    )}
                  </div>
                </td>
                <td className="py-2.5 px-3.5 text-right font-mono tabular-nums text-text-secondary">
                  {item.qty}
                </td>
                <td className="py-2.5 px-3.5 text-right font-mono tabular-nums text-text-secondary">
                  {formatINR(item.unit_price)}
                </td>
                <td className="py-2.5 px-3.5 text-right font-mono tabular-nums font-semibold text-text-primary">
                  {formatINR(item.amount)}
                </td>
              </tr>
            ))}
            <tr className="bg-surface-elevated/60 font-medium text-text-secondary">
              <td colSpan={3} className="py-2.5 px-3.5 text-right text-muted">
                Subtotal:
              </td>
              <td className="py-2.5 px-3.5 text-right font-mono tabular-nums text-text-primary">
                {formatINR(claim.subtotal)}
              </td>
            </tr>
            <tr className="bg-surface-elevated/60 text-text-secondary">
              <td colSpan={3} className="py-2 px-3.5 text-right text-muted">
                Tax / GST:
              </td>
              <td className="py-2 px-3.5 text-right font-mono tabular-nums text-text-primary">
                {formatINR(claim.tax)}
              </td>
            </tr>
            <tr className="bg-surface-elevated font-bold text-text-primary border-t border-white/8">
              <td colSpan={3} className="py-3 px-3.5 text-right text-amber-primary text-sm">
                Total Claimed:
              </td>
              <td className="py-3 px-3.5 text-right font-mono tabular-nums text-base text-amber-primary">
                {formatINR(claim.total_claimed)}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  );
};
