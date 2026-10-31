"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { brl, obter } from "@/lib/api";

// Mapa em grade: cada UF numa casa, na posição aproximada do mapa do Brasil.
const GRADE: (string | null)[][] = [
  [null, null, "RR", "AP", null, null, null],
  [null, "AM", "PA", "MA", "CE", "RN", null],
  ["AC", "RO", "TO", "PI", "PB", "PE", null],
  [null, "MT", "GO", "BA", "SE", "AL", null],
  [null, "MS", "DF", "MG", "ES", null, null],
  [null, "PR", "SP", "RJ", null, null, null],
  [null, "SC", null, null, null, null, null],
  [null, "RS", null, null, null, null, null],
];

type PorUf = { uf: string; abertos: number; valor: number };

export default function MapaBrasil({ dados }: { dados: PorUf[] }) {
  const [sel, setSel] = useState<string | null>(null);
  const [muns, setMuns] = useState<any[] | null>(null);
  const mapa = Object.fromEntries(dados.map((d) => [d.uf, d]));
  const max = Math.max(1, ...dados.map((d) => d.abertos));

  useEffect(() => {
    if (!sel) return;
    setMuns(null);
    obter(`/painel/municipios?uf=${sel}`).then(setMuns).catch(() => setMuns([]));
  }, [sel]);

  return (
    <div className="duas">
      <div className="mapa" role="group" aria-label="Editais abertos por estado">
        {GRADE.flat().map((uf, i) => {
          if (!uf) return <div key={i} className="uf vazio" />;
          const d = mapa[uf] || { abertos: 0, valor: 0 };
          const pct = d.abertos ? 12 + 78 * Math.log(1 + d.abertos) / Math.log(1 + max) : 0;
          return (
            <button key={uf} type="button" className={`uf ${sel === uf ? "sel" : ""}`} title={`${uf}: ${d.abertos} abertos · ${brl(d.valor)}`}
              style={{ background: `color-mix(in srgb, var(--acento) ${pct}%, var(--cartao))`, color: pct > 55 ? "var(--cartao)" : "var(--texto)" }}
              onClick={() => setSel(uf)}>
              <span>{uf}<small>{d.abertos}</small></span>
            </button>
          );
        })}
      </div>
      <div>
        {!sel && <p className="meta">Clique num estado para ver os municípios com editais abertos.</p>}
        {sel && (
          <>
            <h2>{sel} · <Link href={`/busca?uf=${sel}`}>ver todos</Link></h2>
            {!muns && <p className="meta">Carregando…</p>}
            {muns && muns.length === 0 && <p className="meta">Nenhum município com edital aberto na base.</p>}
            <div className="tabela" style={{ maxHeight: 340 }}>
              <table>
                <tbody>
                  {(muns || []).slice(0, 60).map((m) => (
                    <tr key={m.municipio}>
                      <td><Link href={`/busca?uf=${sel}&municipio=${encodeURIComponent(m.municipio)}`}>{m.municipio}</Link></td>
                      <td className="num">{m.abertos}</td>
                      <td className="num">{brl(m.valor)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
