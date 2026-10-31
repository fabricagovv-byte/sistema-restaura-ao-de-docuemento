"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import CartaoLicitacao from "@/components/CartaoLicitacao";
import { obter } from "@/lib/api";

const UFS = "AC AL AP AM BA CE DF ES GO MA MT MS MG PA PB PR PE PI RJ RN RS RO RR SC SP SE TO".split(" ");
const MODALIDADES: [number, string][] = [[6, "Pregão eletrônico"], [7, "Pregão presencial"], [4, "Concorrência eletrônica"],
  [5, "Concorrência presencial"], [8, "Dispensa"], [9, "Inexigibilidade"], [12, "Credenciamento"], [15, "Chamada pública"],
  [10, "Manifestação de interesse"], [11, "Pré-qualificação"], [1, "Leilão eletrônico"], [3, "Concurso"], [2, "Diálogo competitivo"]];
const CAMPOS = ["q", "uf", "municipio", "orgao", "numero", "processo", "modalidade", "categoria", "situacao", "valor_min",
  "valor_max", "incluir_sem_valor", "prazo_de", "prazo_ate", "publicacao_de", "publicacao_ate", "exigencia", "ordenar", "pagina"];

function Busca() {
  const sp = useSearchParams();
  const router = useRouter();
  const [f, setF] = useState<Record<string, string>>({});
  const [res, setRes] = useState<any>(null);
  const [cats, setCats] = useState<any[]>([]);
  const [erro, setErro] = useState("");

  useEffect(() => { obter("/categorias").then((c) => setCats(c.categorias)).catch(() => {}); }, []);
  useEffect(() => {
    const atual: Record<string, string> = { situacao: "aberta", ordenar: "prazo", incluir_sem_valor: "true" };
    CAMPOS.forEach((k) => { const v = sp.get(k); if (v !== null) atual[k] = v; });
    setF(atual);
    const qs = new URLSearchParams(Object.entries(atual).filter(([, v]) => v !== ""));
    setErro("");
    setRes(null);
    obter(`/licitacoes?${qs}`).then(setRes).catch((e) => setErro(e.message));
  }, [sp]);

  function mudar(k: string, v: string) { setF((x) => ({ ...x, [k]: v })); }
  function aplicar(e?: React.FormEvent, pagina = 1) {
    e?.preventDefault();
    const qs = new URLSearchParams(Object.entries({ ...f, pagina: String(pagina) }).filter(([, v]) => v !== ""));
    router.push(`/busca?${qs}`);
  }
  const grupos = res?.expansao?.grupos || [];
  const paginas = res ? Math.ceil(res.total / res.por_pagina) : 0;

  return (
    <>
      <h1>Busca de licitações</h1>
      <form className="cartao filtros" onSubmit={aplicar}>
        <label htmlFor="q" style={{ gridColumn: "1 / -1" }}>Palavra-chave (busca por significado; separe com vírgula)
          <input id="q" value={f.q || ""} onChange={(e) => mudar("q", e.target.value)} placeholder="digitalização, fábrica de software, tratamento de dados…" />
        </label>
        <label htmlFor="uf">Estado<select id="uf" value={f.uf || ""} onChange={(e) => mudar("uf", e.target.value)}>
          <option value="">Todos</option>{UFS.map((u) => <option key={u}>{u}</option>)}</select></label>
        <label htmlFor="valor_min">Valor mínimo (R$)<input id="valor_min" type="number" min="0" value={f.valor_min || ""} onChange={(e) => mudar("valor_min", e.target.value)} /></label>
        <label htmlFor="valor_max">Valor máximo (R$)<input id="valor_max" type="number" min="0" value={f.valor_max || ""} onChange={(e) => mudar("valor_max", e.target.value)} /></label>
        <label htmlFor="ordenar">Ordenar por<select id="ordenar" value={f.ordenar || "prazo"} onChange={(e) => mudar("ordenar", e.target.value)}>
          <option value="prazo">Prazo mais próximo</option><option value="valor">Maior valor</option>
          <option value="aderencia">Maior aderência</option><option value="publicacao">Mais recentes</option></select></label>
        <details className="mais-filtros" open={["municipio","orgao","numero","processo","modalidade","categoria","valor_max","prazo_de","prazo_ate","publicacao_de","exigencia"].some((k) => !!f[k]) || undefined}>
          <summary>Mais filtros</summary>
          <div className="filtros">
            <label htmlFor="municipio">Município<input id="municipio" value={f.municipio || ""} onChange={(e) => mudar("municipio", e.target.value)} /></label>
            <label htmlFor="orgao">Órgão (nome ou CNPJ)<input id="orgao" value={f.orgao || ""} onChange={(e) => mudar("orgao", e.target.value)} /></label>
            <label htmlFor="numero">Nº do edital<input id="numero" value={f.numero || ""} onChange={(e) => mudar("numero", e.target.value)} /></label>
            <label htmlFor="processo">Nº do processo<input id="processo" value={f.processo || ""} onChange={(e) => mudar("processo", e.target.value)} /></label>
            <label htmlFor="modalidade">Modalidade<select id="modalidade" value={f.modalidade || ""} onChange={(e) => mudar("modalidade", e.target.value)}>
          <option value="">Todas</option>{MODALIDADES.map(([c, n]) => <option key={c} value={c}>{n}</option>)}</select></label>
            <label htmlFor="categoria">Categoria<select id="categoria" value={f.categoria || ""} onChange={(e) => mudar("categoria", e.target.value)}>
          <option value="">Todas</option>{cats.map((c) => <option key={c.codigo} value={c.codigo}>{c.nome}</option>)}</select></label>
            <label htmlFor="situacao">Situação<select id="situacao" value={f.situacao || "aberta"} onChange={(e) => mudar("situacao", e.target.value)}>
          <option value="aberta">Abertas</option><option value="futura">Futuras (abertura ainda não começou)</option>
          <option value="em_andamento">Abertas + futuras</option><option value="encerrada">Encerradas</option><option value="todas">Todas (histórico)</option></select></label>
            <label htmlFor="incluir_sem_valor">Sem valor divulgado<select id="incluir_sem_valor" value={f.incluir_sem_valor || "true"} onChange={(e) => mudar("incluir_sem_valor", e.target.value)}>
          <option value="true">Incluir (sigilosos)</option><option value="false">Excluir</option></select></label>
            <label htmlFor="prazo_de">Prazo de<input id="prazo_de" type="date" value={f.prazo_de || ""} onChange={(e) => mudar("prazo_de", e.target.value)} /></label>
            <label htmlFor="prazo_ate">Prazo até<input id="prazo_ate" type="date" value={f.prazo_ate || ""} onChange={(e) => mudar("prazo_ate", e.target.value)} /></label>
            <label htmlFor="publicacao_de">Publicado desde<input id="publicacao_de" type="date" value={f.publicacao_de || ""} onChange={(e) => mudar("publicacao_de", e.target.value)} /></label>
            <label htmlFor="exigencia">Exigência técnica (nas análises)<input id="exigencia" value={f.exigencia || ""} onChange={(e) => mudar("exigencia", e.target.value)} placeholder="ISO 27001, atestado…" /></label>
          </div>
        </details>
        <button className="primario" type="submit">Buscar</button>
      </form>
      {grupos.length > 0 && (
        <details className="cartao">
          <summary>Como a busca entendeu: {grupos.map((g: any) => `"${g.consulta}" (${g.termos.length} termos)`).join(" + ")}</summary>
          {grupos.map((g: any) => <p key={g.consulta} className="meta">{g.termos.join(" · ")}</p>)}
        </details>
      )}
      {erro && <p className="erro">{erro}</p>}
      {!res && !erro && <p className="meta">Buscando…</p>}
      {res && (
        <>
          <p className="meta">{res.total.toLocaleString("pt-BR")} licitações encontradas</p>
          <div className="lista">{res.itens.map((l: any) => <CartaoLicitacao key={l.id} l={l} />)}</div>
          {paginas > 1 && (
            <div className="botoes">
              <button disabled={res.pagina <= 1} onClick={() => aplicar(undefined, res.pagina - 1)}>Anterior</button>
              <span className="meta">Página {res.pagina} de {paginas}</span>
              <button disabled={res.pagina >= paginas} onClick={() => aplicar(undefined, res.pagina + 1)}>Próxima</button>
            </div>
          )}
        </>
      )}
    </>
  );
}

export default function Pagina() {
  return <Suspense fallback={<p className="meta">Carregando…</p>}><Busca /></Suspense>;
}
