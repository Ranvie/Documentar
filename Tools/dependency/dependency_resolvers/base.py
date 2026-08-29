from __future__ import annotations


class LanguageResolver:
    """Interface que cada dependency_resolvers/<lang>_resolver.py implementa.

    Roda depois que TODOS os arquivos do projeto ja foram extraidos (fase 1),
    nunca arquivo a arquivo: resolver um import exige saber o que os OUTROS
    arquivos declaram, informacao que so existe depois da extracao completa.
    Cada linguagem resolve do seu proprio jeito (Composer/PSR-4 no PHP,
    node_modules/tsconfig no JS/TS, etc.) - essa classe so' fixa o contrato.
    """

    language: str

    def resolve(self, files: list, root: str) -> None:
        """Preenche import["resolved_path"] em `files` (lista de dict, no
        formato de FileParseResult.to_dict()), em memoria (in-place)."""
        raise NotImplementedError
