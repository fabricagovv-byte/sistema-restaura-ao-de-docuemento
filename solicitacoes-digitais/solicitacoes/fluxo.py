"""Máquina de estados da tramitação (REQ-003) e regras de visibilidade.

Estados e transições conforme docs/PROCESSO_TRAMITACAO.md. Cada transição diz quem pode fazê-la e o que exige.
"""

from __future__ import annotations

from dataclasses import dataclass

from .modelos import Solicitacao, Usuario

ESTADOS = ("recebida", "em_triagem", "em_atendimento", "aguardando_solicitante", "concluida", "indeferida", "cancelada")
FINAIS = frozenset({"concluida", "indeferida", "cancelada"})


@dataclass(frozen=True)
class Transicao:
    de: str
    para: str
    perfis: frozenset[str]          # perfis que podem fazer
    exige_comentario: bool = False  # motivo, pedido ou resposta obrigatórios
    exige_responsavel: bool = False
    so_responsavel: bool = False    # operador só pode se for o responsável
    so_dono: bool = False           # solicitante só pode na própria


ATENDE = frozenset({"operador", "gestor"})

TRANSICOES: dict[tuple[str, str], Transicao] = {(t.de, t.para): t for t in [
    Transicao("recebida", "em_triagem", ATENDE),
    Transicao("recebida", "cancelada", frozenset({"solicitante"}), exige_comentario=True, so_dono=True),
    Transicao("em_triagem", "em_atendimento", ATENDE, exige_responsavel=True, so_responsavel=True),
    Transicao("em_triagem", "indeferida", ATENDE, exige_comentario=True),
    Transicao("em_atendimento", "aguardando_solicitante", ATENDE, exige_comentario=True, so_responsavel=True),
    Transicao("em_atendimento", "concluida", ATENDE, exige_comentario=True, so_responsavel=True),
    Transicao("em_atendimento", "indeferida", ATENDE, exige_comentario=True, so_responsavel=True),
    Transicao("aguardando_solicitante", "em_atendimento", ATENDE | {"solicitante"}, exige_comentario=True, so_responsavel=True, so_dono=True),
    Transicao("aguardando_solicitante", "cancelada", frozenset({"solicitante"}), exige_comentario=True, so_dono=True),
    # reabertura: só o gestor, com motivo
    Transicao("concluida", "em_triagem", frozenset({"gestor"}), exige_comentario=True),
    Transicao("indeferida", "em_triagem", frozenset({"gestor"}), exige_comentario=True),
]}


class TransicaoInvalida(Exception):
    def __init__(self, mensagem: str, codigo: int = 409):
        super().__init__(mensagem)
        self.codigo = codigo


def validar(s: Solicitacao, para: str, ator: Usuario, comentario: str | None) -> Transicao:
    """Confere a transição; levanta TransicaoInvalida com o motivo (409 regra de negócio, 403 permissão, 422 dado)."""
    if para not in ESTADOS:
        raise TransicaoInvalida(f"status desconhecido: {para}", 422)
    if s.arquivada:
        raise TransicaoInvalida("solicitação arquivada não tramita; peça ao gestor para desarquivar")
    t = TRANSICOES.get((s.status, para))
    if t is None:
        permitidos = sorted(p for (d, p) in TRANSICOES if d == s.status)
        raise TransicaoInvalida(f"não é possível ir de {s.status} para {para}; a partir de {s.status}: "
                                + (", ".join(permitidos) or "nenhuma transição"))
    if ator.perfil not in t.perfis:
        raise TransicaoInvalida(f"o perfil {ator.perfil} não pode levar a solicitação de {s.status} para {para}", 403)
    if t.so_dono and ator.perfil == "solicitante" and s.solicitante_id != ator.id:
        raise TransicaoInvalida("só o próprio solicitante pode fazer esta ação", 403)
    if t.exige_responsavel and s.responsavel_id is None:
        raise TransicaoInvalida("atribua um responsável antes de iniciar o atendimento")
    if t.so_responsavel and ator.perfil == "operador" and s.responsavel_id != ator.id:
        raise TransicaoInvalida("só o operador responsável pode fazer esta ação; peça a atribuição ao gestor ou assuma a solicitação", 403)
    if t.exige_comentario and not (comentario and comentario.strip()):
        raise TransicaoInvalida("informe o motivo ou a resposta no comentário", 422)
    return t


def pode_ver(s: Solicitacao, u: Usuario) -> bool:
    if u.perfil == "gestor":
        return True
    if u.perfil == "operador":
        return s.responsavel_id == u.id or (s.responsavel_id is None and s.status in ("recebida", "em_triagem"))
    if u.perfil == "solicitante":
        return s.solicitante_id == u.id
    return False


def pode_editar(s: Solicitacao, u: Usuario) -> bool:
    """Conteúdo editável pelo dono enquanto recebida; pelo gestor enquanto não finalizada."""
    if s.arquivada or s.status in FINAIS:
        return False
    if u.perfil == "gestor":
        return True
    return u.perfil == "solicitante" and s.solicitante_id == u.id and s.status == "recebida"
