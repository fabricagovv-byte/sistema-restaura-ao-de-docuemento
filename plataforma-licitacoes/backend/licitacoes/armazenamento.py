"""Armazenamento de arquivos: pasta local por padrão, S3 compatível (MinIO, AWS, R2) se configurado."""

from __future__ import annotations

from pathlib import Path

from .config import config


class Armazenamento:
    def salvar(self, chave: str, dados: bytes, mime: str | None = None) -> str: ...
    def ler(self, chave: str) -> bytes: ...
    def existe(self, chave: str) -> bool: ...


class ArmazenamentoLocal(Armazenamento):
    def __init__(self, raiz: str):
        self.raiz = Path(raiz)

    def _caminho(self, chave: str) -> Path:
        p = (self.raiz / chave).resolve()
        if self.raiz.resolve() not in p.parents and p != self.raiz.resolve():
            raise ValueError("chave fora do armazenamento")
        return p

    def salvar(self, chave: str, dados: bytes, mime: str | None = None) -> str:
        p = self._caminho(chave)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(dados)
        return chave

    def ler(self, chave: str) -> bytes:
        return self._caminho(chave).read_bytes()

    def existe(self, chave: str) -> bool:
        return self._caminho(chave).exists()


class ArmazenamentoS3(Armazenamento):
    def __init__(self):
        import boto3  # dependência opcional (pip install boto3)

        cfg = config()
        self.bucket = cfg.s3_bucket
        self.cli = boto3.client("s3", endpoint_url=cfg.s3_endpoint, aws_access_key_id=cfg.s3_access_key,
                                aws_secret_access_key=cfg.s3_secret_key, region_name=cfg.s3_regiao)

    def salvar(self, chave: str, dados: bytes, mime: str | None = None) -> str:
        extra = {"ContentType": mime} if mime else {}
        self.cli.put_object(Bucket=self.bucket, Key=chave, Body=dados, **extra)
        return chave

    def ler(self, chave: str) -> bytes:
        return self.cli.get_object(Bucket=self.bucket, Key=chave)["Body"].read()

    def existe(self, chave: str) -> bool:
        try:
            self.cli.head_object(Bucket=self.bucket, Key=chave)
            return True
        except Exception:
            return False


_inst: Armazenamento | None = None


def armazenamento() -> Armazenamento:
    global _inst
    if _inst is None:
        cfg = config()
        _inst = ArmazenamentoS3() if cfg.s3_bucket else ArmazenamentoLocal(cfg.armazenamento_dir)
    return _inst


def reiniciar() -> None:
    global _inst
    _inst = None
