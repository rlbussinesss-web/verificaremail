"""Configuração da aplicação.

Mantém os parâmetros ajustáveis pelo usuário (domínio, partículas ignoradas,
sufixos que disparam revisão e algumas flags de comportamento) num objeto simples
e serializável para JSON, de modo que a tela de Configurações possa carregar e
salvar preferências entre execuções.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import List

# Domínio institucional padrão. Editável na interface para uso futuro, mas a
# regra atual continua sendo a padrão.
DOMINIO_PADRAO = "professor.educacao.pe.gov.br"

# Partículas que NÃO devem gerar iniciais nos nomes intermediários.
PARTICULAS_PADRAO: List[str] = ["da", "de", "do", "das", "dos", "e"]

# Sufixos de nome que exigem conferência manual. NÃO alteram a regra de geração,
# apenas marcam o registro para revisão.
SUFIXOS_REVISAO_PADRAO: List[str] = ["junior", "filho", "neto", "sobrinho"]

# Prefixo de cargo considerado "docente". Usado só para marcar REVISAR quando
# nenhuma matrícula da pessoa tem cargo começando assim.
PREFIXO_CARGO_DOCENTE = "PROF"

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.json"


@dataclass
class AppConfig:
    """Parâmetros de processamento."""

    dominio: str = DOMINIO_PADRAO
    particulas: List[str] = field(default_factory=lambda: list(PARTICULAS_PADRAO))
    sufixos_revisao: List[str] = field(
        default_factory=lambda: list(SUFIXOS_REVISAO_PADRAO)
    )
    prefixo_cargo_docente: str = PREFIXO_CARGO_DOCENTE

    # Colapsar várias linhas do mesmo servidor (matrículas diferentes) numa só.
    colapsar_por_pessoa: bool = True
    # Marcar REVISAR quando nenhuma ocorrência da pessoa tem cargo docente.
    # Desligado por padrão: o e-mail vale mesmo para quem não é professor.
    revisar_nao_docente: bool = False
    # Quando nomes diferentes geram o mesmo e-mail: manter só a 1ª pessoa (ordem do
    # CSV) e remover as demais do painel. As removidas ficam disponíveis à parte.
    descartar_conflitos: bool = True
    # Consultar DNS/MX do domínio (somente o domínio trafega na rede, nunca nomes).
    verificar_mx: bool = False
    # Comprimento mínimo do nome normalizado abaixo do qual marcamos "muito curto".
    min_len_nome: int = 6
    # Número de tokens acima do qual o nome é considerado suspeito de corrupção.
    max_tokens_nome: int = 6

    # ------------------------------------------------------------------ helpers
    def dominio_normalizado(self) -> str:
        d = (self.dominio or "").strip().lower().lstrip("@")
        return d or DOMINIO_PADRAO

    def particulas_set(self) -> set[str]:
        return {p.strip().lower() for p in self.particulas if p.strip()}

    def sufixos_set(self) -> set[str]:
        return {s.strip().lower() for s in self.sufixos_revisao if s.strip()}

    def chave_cache(self) -> tuple:
        """Tupla imutável usada para invalidar caches quando a config muda."""
        return (
            self.dominio_normalizado(),
            tuple(sorted(self.particulas_set())),
            tuple(sorted(self.sufixos_set())),
            self.prefixo_cargo_docente.upper(),
            self.colapsar_por_pessoa,
            self.revisar_nao_docente,
            self.descartar_conflitos,
            self.verificar_mx,
            self.min_len_nome,
            self.max_tokens_nome,
        )

    # ------------------------------------------------------------------ persist
    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, indent=2)

    def salvar(self, caminho: Path | str = CONFIG_PATH) -> None:
        Path(caminho).write_text(self.to_json(), encoding="utf-8")

    @classmethod
    def carregar(cls, caminho: Path | str = CONFIG_PATH) -> "AppConfig":
        p = Path(caminho)
        if not p.exists():
            return cls()
        try:
            dados = json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return cls()
        base = cls()
        for k, v in dados.items():
            if hasattr(base, k):
                setattr(base, k, v)
        return base
