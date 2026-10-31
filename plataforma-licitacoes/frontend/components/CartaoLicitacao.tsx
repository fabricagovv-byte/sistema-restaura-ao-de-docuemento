"use client";

import Link from "next/link";
import { useState } from "react";
import { baixar, brl, data, diasAte, enviar } from "@/lib/api";

export type Lic = {
  id: number; orgao: string; uf: string; municipio: string; objeto: string; valor_estimado: number | null;
  data_encerramento: string | null; data_abertura?: string | null; modalidade: string; situacao?: string;
  link_pncp?: string | null; link_origem?: string | null; link?: string | null; aderencia: number;
  categorias: any[]; plataforma_origem?: string | null; numero?: string | null; orcamento_sigiloso?: boolean;
  numero_controle_pncp?: string | null;
};

export default function CartaoLicitacao({ l }: { l: Lic }) {
  const [msg, setMsg] = useState("");
  const [ocupado, setOcupado] = useState(false);
  const dias = diasAte(l.data_encerramento);
  const link = l.link_pncp || l.link_origem || l.link;
  const cats = (l.categorias || []).map((c: any) => (typeof c === "string" ? c : c.nome));

  async function agir(fn: () => Promise<any>, ok: string) {
    setOcupado(true);
    setMsg("");
    try {
      await fn();
      setMsg(ok);
    } catch (e: any) {
      setMsg(e.message);
    } finally {
      setOcupado(false);
    }
  }

  return (
    <article className="item">
      <div className="meta" style={{ justifyContent: "space-between" }}>
        <span><b>{l.orgao}</b> · {l.municipio ? `${l.municipio}/` : ""}{l.uf}</span>
        <span>
          {dias !== null && (
            <span className={`pilula ${dias <= 2 ? "p-erro" : dias <= 7 ? "p-alerta" : "p-ok"}`}>
              {dias < 0 ? "encerrada" : dias === 0 ? "encerra hoje" : `${dias} dias`}
            </span>
          )}{" "}
          <span className="pilula p-acento" title="Aderência ao perfil (0 a 100)">{Math.round(l.aderencia)}</span>
        </span>
      </div>
      <h3>{l.objeto.length > 260 ? l.objeto.slice(0, 260) + "…" : l.objeto}</h3>
      <div className="meta">
        <span className="valor">{l.valor_estimado ? brl(l.valor_estimado) : "Sem valor divulgado (sigiloso ou não informado)"}</span>
        <span>Propostas até {data(l.data_encerramento)}</span>
        <span>{l.modalidade}{l.numero ? ` nº ${l.numero}` : ""}</span>
        {l.plataforma_origem && <span>Disputa: {l.plataforma_origem}</span>}
      </div>
      {cats.length > 0 && <div className="botoes">{cats.slice(0, 4).map((c: string) => <span key={c} className="pilula p-cinza">{c}</span>)}</div>}
      <div className="botoes">
        {link ? <a className="botao" href={link} target="_blank" rel="noopener">VER EDITAL</a> : <span className="pilula p-cinza">sem link oficial</span>}
        <button disabled={ocupado} onClick={() => agir(async () => {
          const r = await enviar(`/licitacoes/${l.id}/preparar`);
          if (!r.enfileirado) window.location.href = `/licitacao/${l.id}#analise`;
        }, "Análise enviada para a fila; acompanhe na página do edital.")}>ANALISAR COM IA</button>
        <button disabled={ocupado} onClick={() => agir(() => baixar(`/licitacoes/${l.id}/zip`, `licitacao-${l.id}.zip`), "Download iniciado.")}>BAIXAR ZIP</button>
        <Link className="botao" href={`/licitacao/${l.id}#proposta`}>GERAR PROPOSTA</Link>
        <button disabled={ocupado} onClick={() => agir(() => enviar(`/licitacoes/${l.id}/monitorar`), "Monitorando prazo, retificações e suspensão.")}>MONITORAR</button>
        <Link className="botao" href={`/licitacao/${l.id}`}>Detalhes</Link>
      </div>
      {msg && <p className="meta">{msg}</p>}
    </article>
  );
}
