"use client";

import { useEffect, useState } from "react";
import { data, obter } from "@/lib/api";

const SAUDE: Record<string, string> = { funcionando: "p-ok", com_falha: "p-erro", nunca_sincronizado: "p-alerta", via_pncp: "p-acento",
  requer_credencial: "p-alerta", nao_integrado: "p-cinza" };

export default function Qualidade() {
  const [q, setQ] = useState<any>(null);
  const [erro, setErro] = useState("");
  useEffect(() => { obter("/qualidade").then(setQ).catch((e) => setErro(e.message)); }, []);
  if (erro) return <p className="erro">{erro}</p>;
  if (!q) return <p className="meta">Carregando…</p>;
  const c = q.cobertura;
  return (
    <>
      <h1>Controle de qualidade</h1>
      <section className="grade">
        {[["Portais cadastrados", q.portais_cadastrados], ["Funcionando", q.funcionando], ["Com falha", q.com_falha],
          ["Editais coletados", q.editais_coletados.toLocaleString("pt-BR")], ["Atualizados em 24 h", q.atualizados_24h.toLocaleString("pt-BR")],
          ["Editais com anexos", q.com_anexos], ["Anexos baixados", q.anexos_baixados], ["Anexos indisponíveis", q.anexos_indisponiveis],
          ["Republicações ligadas", q.duplicatas_ligadas], ["Excluídos detectados", q.excluidos_detectados]].map(([r, v]) => (
          <div key={r as string} className="cartao kpi"><div className="rot">{r}</div><div className="num">{v}</div></div>))}
      </section>
      <section className="cartao">
        <h2>Cobertura comprovada: {c.percentual_comprovado === null ? "lista do IBGE não carregada" : `${c.percentual_comprovado}% dos municípios`}</h2>
        <p className="meta">{c.municipios_com_edital_90d.toLocaleString("pt-BR")} de {c.municipios_na_base_ibge.toLocaleString("pt-BR")} municípios. Método: {c.metodo}.
          Última sincronização: {data(q.ultima_sincronizacao)}.</p>
        <div className="tabela"><table><thead><tr><th>UF</th><th className="num">Municípios</th><th className="num">Com edital</th><th className="num">Sem edital</th><th className="num">%</th></tr></thead>
          <tbody>{c.por_uf.map((u: any) => <tr key={u.uf}><td>{u.uf}</td><td className="num">{u.municipios}</td><td className="num">{u.com_edital}</td>
            <td className="num">{u.sem_edital}</td><td className="num">{u.percentual}%</td></tr>)}</tbody></table></div>
      </section>
      <section className="cartao">
        <h2>Fontes e portais</h2>
        <div className="tabela"><table><thead><tr><th>Fonte</th><th>Situação</th><th className="num">Editais</th><th>Última sincronização</th><th>Como é coberto / o que falta</th></tr></thead>
          <tbody>{q.fontes.map((f: any) => (
            <tr key={f.codigo}><td><b>{f.nome}</b></td><td><span className={`pilula ${SAUDE[f.saude] || "p-cinza"}`}>{f.saude.replaceAll("_", " ")}</span></td>
              <td className="num">{f.editais.toLocaleString("pt-BR")}</td><td>{data(f.ultima_sincronizacao)}</td>
              <td>{f.como_coberto}<div className="meta">{f.procedimento}</div>{f.ultimo_erro && <div className="erro">{f.ultimo_erro}</div>}</td></tr>))}</tbody></table></div>
      </section>
      <section className="cartao">
        <h2>Editais por plataforma de disputa</h2>
        <div className="tabela"><table><tbody>{q.por_plataforma_origem.map((p: any) => (
          <tr key={p.plataforma}><td>{p.plataforma}</td><td className="num">{p.editais.toLocaleString("pt-BR")}</td></tr>))}</tbody></table></div>
      </section>
    </>
  );
}
