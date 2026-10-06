"""Sistema de busca e restauração de documentos."""

from .pipeline import Resultado, executar, gerar_excel, gerar_zip, relatorio_texto, restaurar, salvar

__all__ = ["Resultado", "executar", "gerar_excel", "gerar_zip", "relatorio_texto", "restaurar", "salvar"]
