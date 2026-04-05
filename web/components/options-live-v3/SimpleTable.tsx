import React from "react";

type SimpleTableProps = {
  title: string;
  columns: string[];
  rows: Array<Array<string>>;
  emptyLabel?: string;
};

export function SimpleTable({ title, columns, rows, emptyLabel = "No data" }: SimpleTableProps) {
  return (
    <div className="rounded-xl border border-zinc-800 bg-zinc-950 p-4">
      <h3 className="mb-3 text-sm font-semibold text-zinc-200">{title}</h3>
      {rows.length === 0 ? (
        <p className="text-sm text-zinc-500">{emptyLabel}</p>
      ) : (
        <div className="overflow-auto">
          <table className="min-w-full text-sm">
            <thead>
              <tr>
                {columns.map((col) => (
                  <th key={col} className="border-b border-zinc-800 px-2 py-2 text-left text-[11px] uppercase tracking-widest text-zinc-500">
                    {col}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row, idx) => (
                <tr key={idx} className="border-b border-zinc-900/60">
                  {row.map((cell, cidx) => (
                    <td key={`${idx}-${cidx}`} className="px-2 py-2 text-zinc-300">
                      {cell}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
