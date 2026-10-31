"use client";

export const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export function token(): string | null {
  try {
    return localStorage.getItem("lic_token");
  } catch {
    return null;
  }
}

export function sair() {
  try {
    localStorage.removeItem("lic_token");
    localStorage.removeItem("lic_usuario");
  } catch {}
  window.location.href = "/login";
}

async function req(caminho: string, opcoes: RequestInit = {}): Promise<Response> {
  const t = token();
  const r = await fetch(`${API}${caminho}`, {
    ...opcoes,
    headers: {
      ...(opcoes.body ? { "Content-Type": "application/json" } : {}),
      ...(t ? { Authorization: `Bearer ${t}` } : {}),
      ...(opcoes.headers || {}),
    },
  });
  if (r.status === 401 && typeof window !== "undefined" && !caminho.startsWith("/auth/login")) {
    sair();
  }
  return r;
}

export async function obter<T = any>(caminho: string): Promise<T> {
  const r = await req(caminho);
  if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || `Erro ${r.status}`);
  return r.json();
}

export async function enviar<T = any>(caminho: string, corpo?: unknown, metodo = "POST"): Promise<T> {
  const r = await req(caminho, { method: metodo, body: corpo === undefined ? undefined : JSON.stringify(corpo) });
  if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || `Erro ${r.status}`);
  return r.json();
}

/** Baixa um arquivo autenticado (ZIP, XLSX, PDF) e entrega ao navegador. */
export async function baixar(caminho: string, nome: string) {
  const r = await req(caminho);
  if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || `Erro ${r.status}`);
  const blob = await r.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = nome;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

export function brl(v: number | null | undefined): string {
  if (v === null || v === undefined) return "Sem valor divulgado";
  return v.toLocaleString("pt-BR", { style: "currency", currency: "BRL", maximumFractionDigits: 0 });
}

/** Valor curto para cartões: R$ 44,3 bi, R$ 3,2 mi, R$ 850 mil. */
export function brlCurto(v: number | null | undefined): string {
  if (v === null || v === undefined) return "—";
  const f = (x: number) => x.toLocaleString("pt-BR", { maximumFractionDigits: 1 });
  if (v >= 1e9) return `R$ ${f(v / 1e9)} bi`;
  if (v >= 1e6) return `R$ ${f(v / 1e6)} mi`;
  if (v >= 1e3) return `R$ ${f(v / 1e3)} mil`;
  return brl(v);
}

export function data(v: string | null | undefined, comHora = true): string {
  if (!v) return "—";
  const d = new Date(v);
  return d.toLocaleString("pt-BR", comHora ? { dateStyle: "short", timeStyle: "short" } : { dateStyle: "short" });
}

export function diasAte(v: string | null | undefined): number | null {
  if (!v) return null;
  return Math.ceil((new Date(v).getTime() - Date.now()) / 86400000);
}
