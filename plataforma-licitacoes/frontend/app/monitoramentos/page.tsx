"use client";

import { useEffect, useState } from "react";
import { data, enviar, obter } from "@/lib/api";

const EVENTOS: [string, string][] = [["novo", "Edital novo"], ["alto_valor", "Alto valor"], ["prazo_proximo", "Prazo próximo"],
  ["retificacao", "Retificação"], ["suspensa", "Suspensão"], ["reaberta", "Reabertura"]];

export default function Monitoramentos() {
  const [lista, setLista] = useState<any[]>([]);
  const [alertas, setAlertas] = useState<any[]>([]);
  const [cats, setCats] = useState<any[]>([]);
  const [msg, setMsg] = useState("");
  const [f, setF] = useState({ nome: "", termos: "", categorias: [] as string[], ufs: "", valor_min: "", email: "", whatsapp: "", webhook: "",
    eventos: EVENTOS.map(([k]) => k) });
  function carregar() {
    obter("/monitoramentos").then(setLista).catch((e) => setMsg(e.message));
    obter("/alertas").then(setAlertas).catch(() => {});
  }
  useEffect(() => { carregar(); obter("/categorias").then((c) => setCats(c.categorias)).catch(() => {}); }, []);
  async function criar(e: React.FormEvent) {
    e.preventDefault();
    const canais: any = { painel: true };
    if (f.email) canais.email = f.email;
    if (f.whatsapp) canais.whatsapp = f.whatsapp;
    if (f.webhook) canais.webhook = f.webhook;
    try {
      await enviar("/monitoramentos", { nome: f.nome || f.termos || "Monitoramento", termos: f.termos.split(",").map((x) => x.trim()).filter(Boolean),
        categorias: f.categorias, ufs: f.ufs.split(",").map((x) => x.trim().toUpperCase()).filter(Boolean),
        valor_min: f.valor_min ? Number(f.valor_min) : null, eventos: f.eventos, canais });
      setMsg("Monitoramento criado. A avaliação roda a cada 15 minutos.");
      carregar();
    } catch (err: any) { setMsg(err.message); }
  }
  return (
    <>
      <h1>Monitoramentos e alertas</h1>
      <form className="cartao filtros" onSubmit={criar}>
        <label htmlFor="nome">Nome<input id="nome" value={f.nome} onChange={(e) => setF({ ...f, nome: e.target.value })} /></label>
        <label htmlFor="termos">Palavras-chave (vírgula)<input id="termos" value={f.termos} onChange={(e) => setF({ ...f, termos: e.target.value })} placeholder="digitalização, sustentação de sistemas" /></label>
        <label htmlFor="ufs">UFs (vírgula, vazio = todas)<input id="ufs" value={f.ufs} onChange={(e) => setF({ ...f, ufs: e.target.value })} /></label>
        <label htmlFor="valor_min">Valor mínimo (R$)<input id="valor_min" type="number" value={f.valor_min} onChange={(e) => setF({ ...f, valor_min: e.target.value })} /></label>
        <label htmlFor="cats">Categorias<select id="cats" multiple size={4} value={f.categorias} onChange={(e) => setF({ ...f, categorias: Array.from(e.target.selectedOptions).map((o) => o.value) })}>
          {cats.map((c) => <option key={c.codigo} value={c.codigo}>{c.nome}</option>)}</select></label>
        <label htmlFor="email">E-mail<input id="email" type="email" value={f.email} onChange={(e) => setF({ ...f, email: e.target.value })} /></label>
        <label htmlFor="whatsapp">WhatsApp (com DDI, ex.: 5534999990000)<input id="whatsapp" value={f.whatsapp} onChange={(e) => setF({ ...f, whatsapp: e.target.value })} /></label>
        <label htmlFor="webhook">Webhook (push)<input id="webhook" type="url" value={f.webhook} onChange={(e) => setF({ ...f, webhook: e.target.value })} /></label>
        <fieldset style={{ gridColumn: "1 / -1", border: "none", padding: 0 }} className="botoes">
          {EVENTOS.map(([k, n]) => (
            <label key={k} style={{ display: "flex", gap: 6, alignItems: "center", fontSize: 13 }} htmlFor={`ev-${k}`}>
              <input id={`ev-${k}`} type="checkbox" style={{ width: "auto" }} checked={f.eventos.includes(k)}
                onChange={(e) => setF({ ...f, eventos: e.target.checked ? [...f.eventos, k] : f.eventos.filter((x) => x !== k) })} />{n}</label>))}
        </fieldset>
        <button className="primario" type="submit">Criar monitoramento</button>
      </form>
      {msg && <p className="meta">{msg}</p>}
      <section className="cartao">
        <h2>Ativos</h2>
        <div className="tabela"><table><tbody>{lista.map((m) => (
          <tr key={m.id}><td><b>{m.nome}</b><div className="meta">{[...m.termos, ...m.categorias].join(", ") || (m.licitacao_id ? `edital ${m.licitacao_id}` : "tudo")}
            {m.ufs?.length ? ` · ${m.ufs.join(", ")}` : ""}{m.valor_min ? ` · ≥ R$ ${m.valor_min.toLocaleString("pt-BR")}` : ""}</div></td>
            <td>{Object.keys(m.canais).join(", ")}</td>
            <td><button onClick={() => enviar(`/monitoramentos/${m.id}`, undefined, "DELETE").then(carregar)}>Remover</button></td></tr>))}</tbody></table></div>
      </section>
      <section className="cartao">
        <h2>Alertas recentes</h2>
        {alertas.length === 0 && <p className="meta">Nenhum alerta ainda.</p>}
        <div className="lista">{alertas.map((a) => (
          <div key={a.id} className="item"><div className="meta"><span className="pilula p-acento">{a.tipo}</span> {data(a.criado_em)} ·
            entrega: {Object.entries(a.entrega).map(([c, s]) => `${c} ${s}`).join(", ")}</div>
            <pre style={{ whiteSpace: "pre-wrap", margin: 0, font: "inherit" }}>{a.mensagem}</pre>
            <a href={`/licitacao/${a.licitacao_id}`}>Abrir edital</a></div>))}</div>
      </section>
    </>
  );
}
