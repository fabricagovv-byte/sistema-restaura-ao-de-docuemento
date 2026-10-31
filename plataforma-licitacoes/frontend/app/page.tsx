"use client";

import { useEffect, useState } from "react";
import CartaoLicitacao from "@/components/CartaoLicitacao";
import MapaBrasil from "@/components/MapaBrasil";
import { brl, brlCurto, data, obter } from "@/lib/api";

export default function Painel() {
  const [p, setP] = useState<any>(null);
  const [erro, setErro] = useState("");
  useEffect(() => {
    obter("/painel").then(setP).catch((e) => setErro(e.message));
  }, []);
  if (erro) return <p className="erro">{erro}</p>;
  if (!p) return <p className="meta">Carregando o painel…</p>;
  const kpis = [
    ["Editais coletados", p.total_coletado.toLocaleString("pt-BR")],
    ["Abertos", p.abertos.toLocaleString("pt-BR")],
    ["Publicados nas últimas 24 h", p.publicados_24h.toLocaleString("pt-BR")],
    ["Valor estimado aberto", brlCurto(p.valor_estimado_abertos)],
    ["Abertos sem valor", p.sem_valor_abertos.toLocaleString("pt-BR")],
    ["Editais analisados", p.analisados.toLocaleString("pt-BR")],
  ];
  return (
    <>
      <div className="meta" style={{ justifyContent: "space-between" }}>
        <h1>Painel</h1>
        <span>Atualizado em {data(p.atualizado_em)}</span>
      </div>
      <section className="grade">
        {kpis.map(([r, v]) => (
          <div key={r} className="cartao kpi"><div className="rot">{r}</div><div className="num">{v}</div></div>
        ))}
      </section>
      <section className="cartao">
        <h2>Editais abertos por estado</h2>
        <MapaBrasil dados={p.por_uf} />
      </section>
      <div className="duas">
        <section className="cartao">
          <h2>Prazos nos próximos 7 dias</h2>
          <div className="lista">{p.prazos_proximos.map((l: any) => <CartaoLicitacao key={l.id} l={l} />)}</div>
        </section>
        <section className="cartao">
          <h2>Maior aderência ao perfil</h2>
          <div className="lista">{p.maior_aderencia.map((l: any) => <CartaoLicitacao key={l.id} l={l} />)}</div>
        </section>
      </div>
      <div className="duas">
        <section className="cartao">
          <h2>Maiores valores abertos</h2>
          <div className="tabela"><table><tbody>
            {p.maiores_valores.map((l: any) => (
              <tr key={l.id}><td><a href={`/licitacao/${l.id}`}>{l.orgao}</a><div className="meta">{l.objeto.slice(0, 120)}</div></td>
                <td className="num">{brl(l.valor_estimado)}</td><td>{data(l.data_encerramento, false)}</td></tr>
            ))}
          </tbody></table></div>
        </section>
        <section className="cartao">
          <h2>Municípios com mais editais abertos</h2>
          <div className="tabela"><table><tbody>
            {p.por_municipio.map((m: any) => (
              <tr key={m.uf + m.municipio}><td><a href={`/busca?uf=${m.uf}&municipio=${encodeURIComponent(m.municipio)}`}>{m.municipio}/{m.uf}</a></td>
                <td className="num">{m.abertos}</td></tr>
            ))}
          </tbody></table></div>
        </section>
      </div>
      <section className="cartao">
        <h2>Favoritas</h2>
        {p.favoritos.length === 0 ? <p className="meta">Nenhuma licitação favoritada ainda.</p> :
          <div className="lista">{p.favoritos.map((l: any) => <CartaoLicitacao key={l.id} l={l} />)}</div>}
      </section>
    </>
  );
}
