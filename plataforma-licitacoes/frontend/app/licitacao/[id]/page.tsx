"use client";

import { useEffect, useState } from "react";
import { baixar, brl, data, enviar, obter } from "@/lib/api";

const NATUREZA: Record<string, [string, string]> = {
  oficial: ["Oficial", "p-ok"], calculo: ["Cálculo", "p-acento"], estimativa_ia: ["Estimativa da IA", "p-alerta"],
  nao_encontrado: ["Não encontrado", "p-cinza"],
};

function Citacoes({ cits }: { cits: any[] }) {
  if (!cits?.length) return null;
  return (
    <>
      {cits.map((c, i) => (
        <div key={i} className={`citacao ${c.verificada ? "ok" : "nao"}`}>
          {c.verificada ? "✓ conferido" : "✗ não conferido"} · {c.documento}{c.pagina ? `, p. ${c.pagina}` : ""}
          {(c.clausula || c.clausula_detectada) ? `, ${c.clausula || c.clausula_detectada}` : ""}
          {c.trecho && <div>“{c.trecho.slice(0, 300)}”</div>}
          {!c.verificada && c.motivo && <div className="erro">{c.motivo}</div>}
        </div>
      ))}
    </>
  );
}

function Proposta({ id, valor }: { id: number; valor: number | null }) {
  const [linhas, setLinhas] = useState([{ descricao: "", unidade: "pagina", quantidade: 0, custo_unitario: 0, item_edital: "" }]);
  const [par, setPar] = useState({ tributos_pct: 14.25, despesas_adm_pct: 8, margem_pct: 12, prazo_meses: 12 });
  const [res, setRes] = useState<any>(null);
  const [erro, setErro] = useState("");
  const UN = { pagina: "Página", caixa: "Caixa", metro_linear: "Metro linear", gb: "GB", tb: "TB", profissional: "Profissional/mês",
    hora: "Hora técnica", mes: "Mês", unidade: "Unidade", fixo: "Valor fixo" };
  function mudar(i: number, k: string, v: string) {
    setLinhas((ls) => ls.map((l, j) => (j === i ? { ...l, [k]: ["quantidade", "custo_unitario"].includes(k) ? Number(v) : v } : l)));
  }
  async function calcular() {
    setErro("");
    try {
      setRes(await enviar(`/licitacoes/${id}/propostas`, { nome: "Proposta", linhas: linhas.filter((l) => l.descricao), ...par }));
    } catch (e: any) { setErro(e.message); }
  }
  return (
    <section className="cartao" id="proposta">
      <h2>Gerar proposta</h2>
      <p className="meta">Informe seus custos. O preço é calculado por você; o valor estimado do edital ({brl(valor)}) é só referência.</p>
      <div className="tabela"><table><thead><tr><th>Item do edital</th><th>Descrição</th><th>Unidade</th><th>Quantidade</th><th>Custo unitário (R$)</th></tr></thead>
        <tbody>{linhas.map((l, i) => (
          <tr key={i}>
            <td><input aria-label="Item" value={l.item_edital} onChange={(e) => mudar(i, "item_edital", e.target.value)} /></td>
            <td><input aria-label="Descrição" value={l.descricao} onChange={(e) => mudar(i, "descricao", e.target.value)} /></td>
            <td><select aria-label="Unidade" value={l.unidade} onChange={(e) => mudar(i, "unidade", e.target.value)}>
              {Object.entries(UN).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></td>
            <td><input aria-label="Quantidade" type="number" value={l.quantidade} onChange={(e) => mudar(i, "quantidade", e.target.value)} /></td>
            <td><input aria-label="Custo" type="number" step="0.0001" value={l.custo_unitario} onChange={(e) => mudar(i, "custo_unitario", e.target.value)} /></td>
          </tr>))}</tbody></table></div>
      <div className="filtros">
        <button type="button" onClick={() => setLinhas((l) => [...l, { descricao: "", unidade: "pagina", quantidade: 0, custo_unitario: 0, item_edital: "" }])}>+ linha de custo</button>
        {(["tributos_pct", "despesas_adm_pct", "margem_pct", "prazo_meses"] as const).map((k) => (
          <label key={k} htmlFor={k}>{{ tributos_pct: "Tributos (% do preço)", despesas_adm_pct: "Despesas adm. (% do custo)", margem_pct: "Margem (% do preço)", prazo_meses: "Prazo (meses)" }[k]}
            <input id={k} type="number" value={par[k]} onChange={(e) => setPar({ ...par, [k]: Number(e.target.value) })} /></label>
        ))}
        <button className="primario" type="button" onClick={calcular}>Calcular</button>
      </div>
      {erro && <p className="erro">{erro}</p>}
      {res && (
        <>
          <p className="aviso">{res.aviso}</p>
          <div className="grade">
            {[["Custo total", res.custo_total], ["Preço total", res.preco_total], ["Preço mensal", res.preco_mensal], ["Margem", res.margem]].map(([r, v]) => (
              <div key={r as string} className="cartao kpi"><div className="rot">{r}</div><div className="num">{brl(v as number)}</div></div>))}
          </div>
          {res.referencia_edital && <p className="meta">Desconto implícito sobre o valor estimado do edital: {res.referencia_edital.desconto_implicito_pct}%</p>}
          <div className="tabela"><table><thead><tr><th>Desconto</th><th className="num">Preço</th><th className="num">Margem</th><th className="num">Margem %</th></tr></thead>
            <tbody>{res.simulacoes.map((s: any) => <tr key={s.desconto_pct}><td>{s.desconto_pct}%</td><td className="num">{brl(s.preco)}</td>
              <td className={`num ${s.prejuizo ? "erro" : ""}`}>{brl(s.margem_valor)}</td><td className="num">{s.margem_pct}%</td></tr>)}</tbody></table></div>
          <div className="botoes">
            <button onClick={() => baixar(`/propostas/${res.id}/xlsx`, `proposta-${res.id}.xlsx`)}>Planilha Excel (editável)</button>
            <button onClick={() => baixar(`/propostas/${res.id}/pdf`, `proposta-${res.id}.pdf`)}>Relatório PDF</button>
          </div>
        </>
      )}
    </section>
  );
}

export default function Detalhe({ params }: { params: { id: string } }) {
  const id = Number(params.id);
  const [l, setL] = useState<any>(null);
  const [an, setAn] = useState<any>(null);
  const [msg, setMsg] = useState("");
  const [ocupado, setOcupado] = useState(false);
  function carregar() {
    obter(`/licitacoes/${id}`).then(setL).catch((e) => setMsg(e.message));
    obter(`/licitacoes/${id}/analise`).then(setAn).catch(() => setAn(null));
  }
  useEffect(carregar, [id]);
  async function preparar(analisar: boolean) {
    setOcupado(true);
    setMsg(analisar ? "Buscando documentos e analisando com IA… pode levar alguns minutos." : "Buscando documentos…");
    try {
      const r = await enviar(`/licitacoes/${id}/preparar?analisar=${analisar}`);
      setMsg(r.enfileirado ? "Enviado para a fila de processamento." : "Concluído.");
      carregar();
    } catch (e: any) { setMsg(e.message); } finally { setOcupado(false); }
  }
  if (!l) return <p className="meta">{msg || "Carregando…"}</p>;
  const rel = an?.relatorio;
  return (
    <>
      <section className="cartao">
        <div className="meta">{l.orgao} · {l.municipio ? `${l.municipio}/` : ""}{l.uf} · {l.modalidade}{l.numero ? ` nº ${l.numero}` : ""}</div>
        <h1 style={{ fontSize: "1.25rem" }}>{l.objeto}</h1>
        <div className="meta">
          <span className="valor">{l.valor_estimado ? brl(l.valor_estimado) : "Sem valor divulgado"}</span>
          <span>Abertura {data(l.data_abertura)}</span><span>Propostas até {data(l.data_encerramento)}</span>
          <span>Situação: {l.situacao || "—"}</span><span>Fontes: {(l.fontes || []).join(", ")}</span>
          {l.processo && <span>Processo {l.processo}</span>}
        </div>
        <div className="botoes" style={{ marginTop: 8 }}>
          {l.link_pncp && <a className="botao" href={l.link_pncp} target="_blank" rel="noopener">VER NO PNCP</a>}
          {l.link_origem && <a className="botao" href={l.link_origem} target="_blank" rel="noopener">PORTAL DA DISPUTA</a>}
          <button disabled={ocupado} className="primario" onClick={() => preparar(true)}>ANALISAR COM IA</button>
          <button disabled={ocupado} onClick={() => preparar(false)}>Buscar documentos</button>
          <button disabled={ocupado || !l.documentos.length} onClick={() => baixar(`/licitacoes/${id}/zip`, `licitacao-${id}.zip`).catch((e) => setMsg(e.message))}>BAIXAR ZIP</button>
          <button onClick={() => enviar(`/licitacoes/${id}/monitorar`).then(() => setMsg("Monitorando este edital."))}>MONITORAR</button>
          <button onClick={() => enviar(`/licitacoes/${id}/favorito`).then((r) => setMsg(r.favorito ? "Favoritado." : "Removido dos favoritos."))}>Favoritar</button>
        </div>
        {msg && <p className="meta">{msg}</p>}
        {l.duplicata_de_id && <p className="aviso">Este edital parece republicação do <a href={`/licitacao/${l.duplicata_de_id}`}>edital {l.duplicata_de_id}</a>.</p>}
      </section>

      <div className="duas">
        <section className="cartao">
          <h2>Documentos</h2>
          {l.documentos.length === 0 && <p className="meta">Ainda não buscados. Use “Buscar documentos”.</p>}
          <div className="tabela"><table><tbody>{l.documentos.map((d: any) => (
            <tr key={d.id}><td>{d.url ? <a href={d.url} target="_blank" rel="noopener">{d.titulo}</a> : d.titulo}</td><td>{d.tipo}</td>
              <td><span className={`pilula ${d.status === "baixado" ? "p-ok" : d.status === "pendente" ? "p-cinza" : "p-erro"}`}>{d.status}</span></td></tr>))}</tbody></table></div>
          <h2 style={{ marginTop: 14 }}>Checklist</h2>
          <div className="botoes">{l.checklist_documentos.map((c: any) => (
            <span key={c.tipo} className={`pilula ${c.publicado ? "p-ok" : "p-cinza"}`} title={c.observacao || ""}>{c.publicado ? "✓" : "—"} {c.nome}</span>))}</div>
        </section>
        <section className="cartao">
          <h2>Itens (PNCP)</h2>
          {l.itens.length === 0 && <p className="meta">Itens ainda não buscados.</p>}
          <div className="tabela"><table><thead><tr><th>Nº</th><th>Descrição</th><th className="num">Qtd.</th><th>Un.</th><th className="num">Unitário</th><th className="num">Total</th></tr></thead>
            <tbody>{l.itens.map((i: any) => <tr key={i.numero}><td>{i.numero}</td><td>{i.descricao.slice(0, 160)}</td><td className="num">{i.quantidade}</td>
              <td>{i.unidade}</td><td className="num">{brl(i.valor_unitario)}</td><td className="num">{brl(i.valor_total)}</td></tr>)}</tbody></table></div>
        </section>
      </div>

      <section className="cartao" id="analise">
        <h2>Análise do edital {an && <span className={`pilula ${an.status === "concluida" ? "p-ok" : "p-alerta"}`}>{an.status}</span>}</h2>
        {!an && <p className="meta">Sem análise. Use “ANALISAR COM IA”.</p>}
        {an?.erro && <p className="aviso">{an.erro}</p>}
        {an?.verificacao?.total > 0 && <p className="meta">Citações conferidas no texto: {an.verificacao.verificadas} de {an.verificacao.total}.</p>}
        {rel && (
          <>
            <div className="botoes">{Object.entries(NATUREZA).map(([k, [n, c]]) => <span key={k} className={`pilula ${c}`}>{n}: {rel.legenda?.[k]}</span>)}</div>
            <div className="tabela"><table><tbody>
              {Object.entries(rel.campos).map(([k, c]: any) => (
                <tr key={k}><th style={{ width: 200 }}>{c.rotulo}</th>
                  <td><span className={`pilula ${NATUREZA[c.natureza]?.[1] || "p-cinza"}`}>{NATUREZA[c.natureza]?.[0] || c.natureza}</span> {c.valor || "—"}
                    {c.valor_nos_documentos && <div className="meta">Nos documentos: {c.valor_nos_documentos}</div>}
                    {c.observacao && <div className="meta">{c.observacao}</div>}
                    <Citacoes cits={[...(c.citacoes || []).filter((x: any) => x.pagina), ...(c.citacoes_documentos || [])]} />
                  </td></tr>))}
            </tbody></table></div>
            {rel.itens_documento?.length > 0 && (<>
              <h2 style={{ marginTop: 14 }}>Itens e lotes nos documentos</h2>
              <div className="tabela"><table><thead><tr><th>Lote</th><th>Item</th><th>Descrição</th><th>Qtd.</th><th>Un.</th><th>Unitário</th><th>Total</th></tr></thead>
                <tbody>{rel.itens_documento.map((i: any, n: number) => <tr key={n}><td>{i.lote}</td><td>{i.numero}</td><td>{i.descricao}<Citacoes cits={i.citacoes} /></td>
                  <td>{i.quantidade}</td><td>{i.unidade}</td><td>{i.valor_unitario}</td><td>{i.valor_total}</td></tr>)}</tbody></table></div></>)}
            {(["riscos", "custos_operacionais", "oportunidades"] as const).map((k) => rel[k]?.length > 0 && (
              <div key={k}><h2 style={{ marginTop: 14 }}>{{ riscos: "Riscos de execução", custos_operacionais: "Custos operacionais estimados", oportunidades: "Oportunidades" }[k]}</h2>
                <div className="lista">{rel[k].map((x: any, n: number) => (
                  <div key={n} className="item"><div><span className={`pilula ${NATUREZA[x.natureza]?.[1]}`}>{NATUREZA[x.natureza]?.[0]}</span>{" "}
                    <span className={`pilula ${x.gravidade === "alta" ? "p-erro" : x.gravidade === "media" ? "p-alerta" : "p-cinza"}`}>{x.gravidade}</span> {x.descricao}</div>
                    {x.base && <div className="meta">Base: {x.base}</div>}<Citacoes cits={x.citacoes} /></div>))}</div></div>))}
            {rel.documentos_citados_nao_enviados?.length > 0 && <p className="aviso">Documentos citados no edital que não estão publicados: {rel.documentos_citados_nao_enviados.join(", ")}</p>}
            {rel.paginas_nao_enviadas?.length > 0 && <p className="aviso">Páginas não enviadas à IA por limite de tamanho: {rel.paginas_nao_enviadas.length}</p>}
          </>
        )}
      </section>

      <Proposta id={id} valor={l.valor_estimado} />

      {l.historico?.length > 0 && (
        <section className="cartao"><h2>Histórico de alterações</h2>
          <div className="tabela"><table><tbody>{l.historico.map((h: any, i: number) => (
            <tr key={i}><td>{data(h.em)}</td><td>{h.evento}</td><td>{h.campo}</td><td>{h.antes} → {h.depois}</td></tr>))}</tbody></table></div>
        </section>
      )}
    </>
  );
}
