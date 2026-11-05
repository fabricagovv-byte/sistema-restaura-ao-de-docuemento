import pytest

from solicitacoes import seguranca


def test_hash_de_senha_tem_sal_e_confere():
    a, b = seguranca.gerar_hash("Senha-Forte-2026", 1000), seguranca.gerar_hash("Senha-Forte-2026", 1000)
    assert a != b and a.startswith("pbkdf2_sha256$1000$")
    assert seguranca.conferir_senha("Senha-Forte-2026", a)
    assert not seguranca.conferir_senha("senha-forte-2026", a)
    assert not seguranca.conferir_senha("x", "formato-invalido")


@pytest.mark.parametrize("senha,ok", [("curta1A", False), ("semnumeroAAAaaa", False), ("tudominusculo123", False), ("Valida-Senha-123", True)])
def test_politica_de_senha(senha, ok):
    assert (seguranca.senha_aceitavel(senha) is None) is ok


def test_matriz_de_permissoes():
    assert seguranca.pode("administrador", "usuarios:gerir")
    assert not seguranca.pode("gestor", "usuarios:gerir")
    assert not seguranca.pode("solicitante", "auditoria:ver")
    assert not seguranca.pode("perfil-inexistente", "usuarios:ver")
