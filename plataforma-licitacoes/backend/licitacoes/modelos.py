"""Tabelas da plataforma."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    JSON, Boolean, DateTime, Float, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def agora() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Fonte(Base):
    """Um portal ou API de onde vêm licitações."""

    __tablename__ = "fonte"
    id: Mapped[int] = mapped_column(primary_key=True)
    codigo: Mapped[str] = mapped_column(String(60), unique=True)
    nome: Mapped[str] = mapped_column(String(200))
    tipo: Mapped[str] = mapped_column(String(40))  # api_oficial, diario_oficial, espelho, portal_proprio
    url_base: Mapped[str | None] = mapped_column(String(300))
    status_integracao: Mapped[str] = mapped_column(String(40))  # ativo, requer_credencial, via_pncp, nao_integrado
    como_coberto: Mapped[str | None] = mapped_column(Text)
    procedimento: Mapped[str | None] = mapped_column(Text)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
    ultima_sincronizacao: Mapped[datetime | None] = mapped_column(DateTime)
    ultimo_sucesso: Mapped[datetime | None] = mapped_column(DateTime)
    ultimo_erro: Mapped[str | None] = mapped_column(Text)
    falhas_consecutivas: Mapped[int] = mapped_column(Integer, default=0)


class Sincronizacao(Base):
    __tablename__ = "sincronizacao"
    id: Mapped[int] = mapped_column(primary_key=True)
    fonte_id: Mapped[int] = mapped_column(ForeignKey("fonte.id"), index=True)
    inicio: Mapped[datetime] = mapped_column(DateTime, default=agora)
    fim: Mapped[datetime | None] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(20), default="rodando")  # rodando, ok, parcial, erro
    parametros: Mapped[dict] = mapped_column(JSON, default=dict)
    lidos: Mapped[int] = mapped_column(Integer, default=0)
    novos: Mapped[int] = mapped_column(Integer, default=0)
    atualizados: Mapped[int] = mapped_column(Integer, default=0)
    erros: Mapped[int] = mapped_column(Integer, default=0)
    chamadas: Mapped[int] = mapped_column(Integer, default=0)
    mensagem: Mapped[str | None] = mapped_column(Text)
    fonte: Mapped[Fonte] = relationship()


class Orgao(Base):
    __tablename__ = "orgao"
    id: Mapped[int] = mapped_column(primary_key=True)
    cnpj: Mapped[str | None] = mapped_column(String(20), unique=True)
    nome: Mapped[str] = mapped_column(String(300))
    esfera: Mapped[str | None] = mapped_column(String(2))  # F, E, M, D
    poder: Mapped[str | None] = mapped_column(String(2))
    uf: Mapped[str | None] = mapped_column(String(2), index=True)
    municipio: Mapped[str | None] = mapped_column(String(120))
    codigo_ibge: Mapped[str | None] = mapped_column(String(10), index=True)


class Municipio(Base):
    """Lista oficial do IBGE, usada para medir a cobertura comprovada."""

    __tablename__ = "municipio"
    codigo_ibge: Mapped[str] = mapped_column(String(10), primary_key=True)
    nome: Mapped[str] = mapped_column(String(120))
    uf: Mapped[str] = mapped_column(String(2), index=True)


class Licitacao(Base):
    __tablename__ = "licitacao"
    id: Mapped[int] = mapped_column(primary_key=True)
    chave: Mapped[str] = mapped_column(String(120), unique=True)
    numero_controle_pncp: Mapped[str | None] = mapped_column(String(60), index=True)
    fonte_id: Mapped[int] = mapped_column(ForeignKey("fonte.id"), index=True)
    orgao_id: Mapped[int | None] = mapped_column(ForeignKey("orgao.id"), index=True)
    tipo_registro: Mapped[str] = mapped_column(String(30), default="contratacao")  # contratacao, aviso_diario
    cnpj_orgao: Mapped[str | None] = mapped_column(String(20), index=True)
    orgao_nome: Mapped[str | None] = mapped_column(String(300))
    unidade_nome: Mapped[str | None] = mapped_column(String(300))
    esfera: Mapped[str | None] = mapped_column(String(2))
    ano: Mapped[int | None] = mapped_column(Integer)
    sequencial: Mapped[int | None] = mapped_column(Integer)
    numero_compra: Mapped[str | None] = mapped_column(String(60), index=True)
    processo: Mapped[str | None] = mapped_column(String(120), index=True)
    modalidade_id: Mapped[int | None] = mapped_column(Integer, index=True)
    modalidade: Mapped[str | None] = mapped_column(String(80))
    modo_disputa: Mapped[str | None] = mapped_column(String(80))
    situacao: Mapped[str | None] = mapped_column(String(80), index=True)
    srp: Mapped[bool | None] = mapped_column(Boolean)
    objeto: Mapped[str] = mapped_column(Text)
    informacao_complementar: Mapped[str | None] = mapped_column(Text)
    valor_estimado: Mapped[float | None] = mapped_column(Numeric(18, 2))
    valor_homologado: Mapped[float | None] = mapped_column(Numeric(18, 2))
    orcamento_sigiloso: Mapped[bool] = mapped_column(Boolean, default=False)
    data_publicacao: Mapped[datetime | None] = mapped_column(DateTime, index=True)
    data_abertura: Mapped[datetime | None] = mapped_column(DateTime, index=True)
    data_encerramento: Mapped[datetime | None] = mapped_column(DateTime, index=True)
    uf: Mapped[str | None] = mapped_column(String(2), index=True)
    municipio: Mapped[str | None] = mapped_column(String(120), index=True)
    codigo_ibge: Mapped[str | None] = mapped_column(String(10), index=True)
    link_pncp: Mapped[str | None] = mapped_column(String(300))
    link_origem: Mapped[str | None] = mapped_column(String(600))
    plataforma_origem: Mapped[str | None] = mapped_column(String(80), index=True)
    categorias: Mapped[list] = mapped_column(JSON, default=list)
    aderencia: Mapped[float] = mapped_column(Float, default=0.0, index=True)
    texto_busca: Mapped[str] = mapped_column(Text, default="")
    hash_conteudo: Mapped[str | None] = mapped_column(String(64))
    excluida: Mapped[bool] = mapped_column(Boolean, default=False)
    duplicata_de_id: Mapped[int | None] = mapped_column(ForeignKey("licitacao.id"))
    fontes_vistas: Mapped[list] = mapped_column(JSON, default=list)
    bruto: Mapped[dict] = mapped_column(JSON, default=dict)
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=agora, index=True)
    atualizado_em: Mapped[datetime] = mapped_column(DateTime, default=agora, index=True)
    conferido_em: Mapped[datetime | None] = mapped_column(DateTime)

    fonte: Mapped[Fonte] = relationship()
    itens: Mapped[list[Item]] = relationship(back_populates="licitacao", cascade="all, delete-orphan")
    documentos: Mapped[list[Documento]] = relationship(back_populates="licitacao", cascade="all, delete-orphan")


class HistoricoAlteracao(Base):
    __tablename__ = "historico_alteracao"
    id: Mapped[int] = mapped_column(primary_key=True)
    licitacao_id: Mapped[int] = mapped_column(ForeignKey("licitacao.id", ondelete="CASCADE"), index=True)
    em: Mapped[datetime] = mapped_column(DateTime, default=agora, index=True)
    campo: Mapped[str] = mapped_column(String(60))
    antes: Mapped[str | None] = mapped_column(Text)
    depois: Mapped[str | None] = mapped_column(Text)
    evento: Mapped[str] = mapped_column(String(30))  # prazo, situacao, valor, documento, excluida
    fonte_codigo: Mapped[str | None] = mapped_column(String(60))


class Item(Base):
    __tablename__ = "item"
    id: Mapped[int] = mapped_column(primary_key=True)
    licitacao_id: Mapped[int] = mapped_column(ForeignKey("licitacao.id", ondelete="CASCADE"), index=True)
    numero: Mapped[int] = mapped_column(Integer)
    descricao: Mapped[str] = mapped_column(Text)
    material_servico: Mapped[str | None] = mapped_column(String(20))
    quantidade: Mapped[float | None] = mapped_column(Numeric(18, 4))
    unidade: Mapped[str | None] = mapped_column(String(60))
    valor_unitario: Mapped[float | None] = mapped_column(Numeric(18, 4))
    valor_total: Mapped[float | None] = mapped_column(Numeric(18, 2))
    situacao: Mapped[str | None] = mapped_column(String(80))
    criterio_julgamento: Mapped[str | None] = mapped_column(String(80))
    bruto: Mapped[dict] = mapped_column(JSON, default=dict)
    licitacao: Mapped[Licitacao] = relationship(back_populates="itens")
    __table_args__ = (UniqueConstraint("licitacao_id", "numero"),)


class Documento(Base):
    __tablename__ = "documento"
    id: Mapped[int] = mapped_column(primary_key=True)
    licitacao_id: Mapped[int] = mapped_column(ForeignKey("licitacao.id", ondelete="CASCADE"), index=True)
    sequencial: Mapped[int | None] = mapped_column(Integer)
    titulo: Mapped[str] = mapped_column(String(500))
    tipo_fonte: Mapped[str | None] = mapped_column(String(120))  # como a fonte chama (ex.: tipoDocumentoNome)
    tipo: Mapped[str] = mapped_column(String(60))  # classificação própria (edital, termo_referencia...)
    url: Mapped[str | None] = mapped_column(String(600))
    publicado_em: Mapped[datetime | None] = mapped_column(DateTime)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
    status: Mapped[str] = mapped_column(String(30), default="pendente")
    # pendente, baixado, indisponivel, requer_autenticacao, erro
    caminho: Mapped[str | None] = mapped_column(String(600))
    tamanho: Mapped[int | None] = mapped_column(Integer)
    sha256: Mapped[str | None] = mapped_column(String(64))
    mime: Mapped[str | None] = mapped_column(String(120))
    paginas: Mapped[int | None] = mapped_column(Integer)
    erro: Mapped[str | None] = mapped_column(Text)
    baixado_em: Mapped[datetime | None] = mapped_column(DateTime)
    licitacao: Mapped[Licitacao] = relationship(back_populates="documentos")
    __table_args__ = (UniqueConstraint("licitacao_id", "sequencial", "titulo"),)


class Analise(Base):
    __tablename__ = "analise"
    id: Mapped[int] = mapped_column(primary_key=True)
    licitacao_id: Mapped[int] = mapped_column(ForeignKey("licitacao.id", ondelete="CASCADE"), index=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=agora)
    modelo: Mapped[str | None] = mapped_column(String(60))
    status: Mapped[str] = mapped_column(String(30))  # concluida, parcial, ia_indisponivel, erro, recusada
    relatorio: Mapped[dict] = mapped_column(JSON, default=dict)
    verificacao: Mapped[dict] = mapped_column(JSON, default=dict)
    uso_tokens: Mapped[dict] = mapped_column(JSON, default=dict)
    erro: Mapped[str | None] = mapped_column(Text)


class Usuario(Base):
    __tablename__ = "usuario"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(200), unique=True)
    nome: Mapped[str] = mapped_column(String(200))
    senha_hash: Mapped[str] = mapped_column(String(300))
    papel: Mapped[str] = mapped_column(String(20), default="analista")  # admin, analista, leitor
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
    telefone_whatsapp: Mapped[str | None] = mapped_column(String(30))
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=agora)


class Proposta(Base):
    __tablename__ = "proposta"
    id: Mapped[int] = mapped_column(primary_key=True)
    licitacao_id: Mapped[int] = mapped_column(ForeignKey("licitacao.id", ondelete="CASCADE"), index=True)
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuario.id"))
    nome: Mapped[str] = mapped_column(String(200))
    parametros: Mapped[dict] = mapped_column(JSON, default=dict)
    resultado: Mapped[dict] = mapped_column(JSON, default=dict)
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=agora)


class Categoria(Base):
    __tablename__ = "categoria"
    id: Mapped[int] = mapped_column(primary_key=True)
    codigo: Mapped[str] = mapped_column(String(60), unique=True)
    nome: Mapped[str] = mapped_column(String(120))
    segmento: Mapped[str] = mapped_column(String(60))
    termos: Mapped[list] = mapped_column(JSON, default=list)
    excluir: Mapped[list] = mapped_column(JSON, default=list)
    ativa: Mapped[bool] = mapped_column(Boolean, default=True)
    personalizada: Mapped[bool] = mapped_column(Boolean, default=False)


class Monitoramento(Base):
    __tablename__ = "monitoramento"
    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuario.id"))
    nome: Mapped[str] = mapped_column(String(200))
    licitacao_id: Mapped[int | None] = mapped_column(ForeignKey("licitacao.id", ondelete="CASCADE"))
    termos: Mapped[list] = mapped_column(JSON, default=list)
    categorias: Mapped[list] = mapped_column(JSON, default=list)
    ufs: Mapped[list] = mapped_column(JSON, default=list)
    modalidades: Mapped[list] = mapped_column(JSON, default=list)
    valor_min: Mapped[float | None] = mapped_column(Float)
    valor_max: Mapped[float | None] = mapped_column(Float)
    eventos: Mapped[list] = mapped_column(JSON, default=lambda: [
        "novo", "alto_valor", "prazo_proximo", "retificacao", "suspensa", "reaberta",
    ])
    canais: Mapped[dict] = mapped_column(JSON, default=lambda: {"painel": True})
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=agora)
    ultima_avaliacao: Mapped[datetime | None] = mapped_column(DateTime)


class Alerta(Base):
    __tablename__ = "alerta"
    id: Mapped[int] = mapped_column(primary_key=True)
    monitoramento_id: Mapped[int] = mapped_column(ForeignKey("monitoramento.id", ondelete="CASCADE"), index=True)
    licitacao_id: Mapped[int] = mapped_column(ForeignKey("licitacao.id", ondelete="CASCADE"), index=True)
    tipo: Mapped[str] = mapped_column(String(30))
    chave_dedupe: Mapped[str] = mapped_column(String(200), unique=True)
    mensagem: Mapped[str] = mapped_column(Text)
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=agora, index=True)
    entrega: Mapped[dict] = mapped_column(JSON, default=dict)
    lido: Mapped[bool] = mapped_column(Boolean, default=False)


class Favorito(Base):
    __tablename__ = "favorito"
    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuario.id", ondelete="CASCADE"))
    licitacao_id: Mapped[int] = mapped_column(ForeignKey("licitacao.id", ondelete="CASCADE"))
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=agora)
    __table_args__ = (UniqueConstraint("usuario_id", "licitacao_id"),)


class LogAuditoria(Base):
    __tablename__ = "log_auditoria"
    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuario.id"))
    acao: Mapped[str] = mapped_column(String(80))
    alvo: Mapped[str | None] = mapped_column(String(200))
    detalhes: Mapped[dict] = mapped_column(JSON, default=dict)
    em: Mapped[datetime] = mapped_column(DateTime, default=agora, index=True)
