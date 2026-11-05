# Sistema de Solicitações Digitais (OS-001/2026)

Recepção e acompanhamento de solicitações digitais com perfis de acesso, tramitação, auditoria e relatórios.
Projeto da minuta de contrato DG-CONT-001 (não assinada). Requisitos em `docs/MATRIZ_REQUISITOS.md`,
arquitetura em `docs/ARQUITETURA.md`, pendências formais e perguntas da entrevista em `docs/PENDENCIAS_ENTREVISTA.md`.

## Rodar

```bash
pip install -r requirements.txt
export SD_BANCO_URL=sqlite:///./solicitacoes.db      # ou postgresql+psycopg://usuario:senha@host/banco
python -m solicitacoes migrar                          # idempotente
python -m solicitacoes criar-admin admin@orgao.gov.br "Nome do Administrador"
python -m solicitacoes servidor --porta 8000           # documentação em http://127.0.0.1:8000/docs
```

Fora de desenvolvimento, `SD_AMBIENTE=producao` exige `SD_SEGREDO` com ao menos 32 caracteres.

## Testes

```bash
python -m pytest                                              # SQLite
SD_TESTE_PG=postgresql+psycopg://u:s@localhost/sd_teste python -m pytest   # PostgreSQL
```

## Medição da OS (UST)

`medicao/plano_os001.json` distribui as 1.000 UST ajustadas da OS em 10 dias de ~100. `medicao/registro.py` registra
início e fim reais de cada entrega, evidências com SHA-256, commit e verificação por testes; `medicao/relatorios/`
traz o relatório de cada dia. Nenhuma UST é homologada pelo sistema: a homologação é ato do contratante.
O executor registrado é o agente de IA que fez o trabalho; horas humanas só entram com participação comprovada.
