# Publicar a Plataforma de Licitações — passo a passo

Situação em 12/11/2026. Marcação: ✅ feito · ⏳ depende de você · 🔧 eu faço quando você liberar.

## Etapa 0 — Já em uso (sem servidor)
✅ Painel publicado no Claude: busca, ficha do pregão, Precificar, CRM, mapa, pisos e **Gerar análise / checklist / perguntas**.
Cada pessoa abre com a própria conta do Claude; CRM, preços, análises e checklists ficam privados de cada um.
⏳ Para a equipe usar: no painel, menu **Compartilhar** → adicionar as pessoas. Limites: precisa ter conta no Claude e a
análise usa o limite de uso de quem clica.

## Etapa 1 — Decisões (você)
| Decisão | Opções | Recomendação |
|---|---|---|
| Quem acessa | só a equipe / clientes (venda como serviço) | começar com a equipe; venda exige contrato, termos de uso e LGPD |
| Domínio | ex.: `licitacoes.suaempresa.com.br` | subdomínio do domínio que a empresa já tem |
| Servidor | VPS no Brasil (Magalu Cloud, Locaweb, Hostinger, AWS São Paulo) | 4 vCPU, 8 GB, 100 GB SSD, Ubuntu 24.04; servidor no Brasil acessa o PNCP sem bloqueio |
| Análise no servidor | chave da API da Anthropic (pago por uso) ou só no painel do Claude | chave própria, com limite de gasto mensal configurado no console da Anthropic |
| E-mail dos alertas | SMTP da empresa ou serviço (SES, SendGrid) | o que a empresa já usa |

## Etapa 2 — Preparar o código para produção
✅ `docker-compose.producao.yml`: só as portas 80/443 abertas; HTTPS automático (Caddy + Let's Encrypt); senhas do banco e
do armazenamento lidas de `producao/.env`; API em `https://DOMINIO/api`; backup diário do banco (14 dias).
✅ API recusa subir em produção com segredo padrão, CORS aberto, autenticação desligada ou SQLite (`conferir_producao`).
✅ `producao/atualizar-dados.sh`: importa o pacote do coletor do GitHub a cada 6 horas (cron).
🔧 Tela de login e cadastro de usuários no frontend com papéis (admin, analista, leitor) — a API já tem.
🔧 Levar o botão **Gerar análise**, o checklist e as perguntas para o frontend do servidor, com o mesmo modelo de análise.
🔧 Pipeline: testes no GitHub Actions antes de cada atualização do servidor.

## Etapa 3 — Subir o servidor (com você, ~1 hora)
1. Criar a VPS e anotar o IP.
2. No DNS do domínio: registro **A** `licitacoes` → IP da VPS.
3. No servidor: `curl -fsSL https://get.docker.com | sh`
4. `git clone` do repositório em `/opt/licitacoes` (chave de deploy só de leitura).
5. `cp plataforma-licitacoes/producao/.env.exemplo plataforma-licitacoes/producao/.env` e preencher
   (`openssl rand -hex 24` para as senhas, `openssl rand -hex 32` para o segredo).
6. `cd plataforma-licitacoes && docker compose -f docker-compose.yml -f docker-compose.producao.yml --env-file producao/.env up -d --build`
7. Criar o primeiro administrador:
   `docker compose -f docker-compose.yml -f docker-compose.producao.yml --env-file producao/.env exec api python -m licitacoes.cli criar-usuario voce@empresa.com.br "Seu Nome" SENHA --papel admin`
8. Primeira carga: `sh producao/atualizar-dados.sh` e agendar no `crontab -e` (linha no topo do script).
9. Abrir `https://licitacoes.suaempresa.com.br` e conferir login, busca, ficha e análise.

## Etapa 4 — Operação
- Backup: `producao/backups/`; testar a restauração uma vez por mês (comando no topo de `producao/backup.sh`).
- Firewall: liberar só 22 (SSH com chave), 80 e 443.
- Atualizar: `git pull` e o mesmo `docker compose ... up -d --build`.
- Custos a acompanhar: VPS (mensal fixo), API da Anthropic (por análise), e-mail.

## Limites que continuam valendo
- Os dados vêm do PNCP, do Compras.gov.br e dos diários oficiais; não há garantia de 100% de cobertura.
- Valor estimado não é preço oficial de contratação.
- Análise da IA é apoio: conferir sempre as citações no edital antes de decidir ou assinar.
