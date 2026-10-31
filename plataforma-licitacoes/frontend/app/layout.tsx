import "./globals.css";
import type { Metadata } from "next";
import Topo from "@/components/Topo";

export const metadata: Metadata = {
  title: "Plataforma Nacional de Licitações",
  description: "Descoberta, análise e monitoramento de licitações públicas",
};

export default function Layout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="pt-BR">
      <body>
        <Topo />
        <main>{children}</main>
      </body>
    </html>
  );
}
