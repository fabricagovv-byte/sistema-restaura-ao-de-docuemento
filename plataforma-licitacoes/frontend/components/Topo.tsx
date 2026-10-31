"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { sair } from "@/lib/api";

export default function Topo() {
  const [usuario, setUsuario] = useState<string | null>(null);
  useEffect(() => {
    try {
      const u = JSON.parse(localStorage.getItem("lic_usuario") || "null");
      setUsuario(u?.nome || null);
    } catch {}
  }, []);
  return (
    <header className="topo">
      <nav>
        <span className="marca">Licitações 5.0</span>
        <Link href="/">Painel</Link>
        <Link href="/busca">Busca</Link>
        <Link href="/monitoramentos">Monitoramentos</Link>
        <Link href="/qualidade">Qualidade</Link>
        <span className="direita">
          {usuario ? (
            <>
              {usuario} · <a href="#" onClick={(e) => { e.preventDefault(); sair(); }}>Sair</a>
            </>
          ) : (
            <Link href="/login">Entrar</Link>
          )}
        </span>
      </nav>
    </header>
  );
}
