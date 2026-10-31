"use client";

import { useState } from "react";
import { enviar } from "@/lib/api";

export default function Login() {
  const [email, setEmail] = useState("");
  const [senha, setSenha] = useState("");
  const [erro, setErro] = useState("");
  async function entrar(e: React.FormEvent) {
    e.preventDefault();
    setErro("");
    try {
      const r = await enviar("/auth/login", { email, senha });
      localStorage.setItem("lic_token", r.token);
      localStorage.setItem("lic_usuario", JSON.stringify(r.usuario));
      window.location.href = "/";
    } catch (err: any) {
      setErro(err.message);
    }
  }
  return (
    <form className="cartao" style={{ maxWidth: 380, display: "grid", gap: 12 }} onSubmit={entrar}>
      <h1>Entrar</h1>
      <label htmlFor="email">E-mail<input id="email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required /></label>
      <label htmlFor="senha">Senha<input id="senha" type="password" value={senha} onChange={(e) => setSenha(e.target.value)} required /></label>
      {erro && <p className="erro">{erro}</p>}
      <button className="primario" type="submit">Entrar</button>
      <p className="meta">O primeiro usuário é criado no servidor: <code>python -m licitacoes.cli criar-usuario email nome senha --papel admin</code></p>
    </form>
  );
}
