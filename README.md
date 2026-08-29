# Documentar

## O que é

Sistema de documentação automática de projetos: gerar e manter uma documentação viva de "como o código funciona" (estrutura de pastas, dependências, arquitetura), determinística onde dá (Python puro, sempre regerado do zero) e com julgamento de IA só onde é realmente necessário (arquitetura, regras de negócio) — isso ainda não existe, ver seção de estado abaixo.

Princípio central: separar fato mecânico (dependências, estrutura) de julgamento (regras de negócio, arquitetura). O que é mecânico nunca é editado à mão; o que exige julgamento é gerado como rascunho e revisado por humano.

**Estado atual:** só a parte de mapeamento de dependências existe. O resto (estrutura de pastas, packages, arquitetura, BusinessRules) ainda não foi implementado.

## Como usar

Por hora só tem o mapeador de dependências.

### Instalação

```
pip install -r requirements.txt
```

### Mapear dependências de um projeto

```
python Tools/dependency/dependency.py <pasta_raiz> [--project-name nome]
```

- `<pasta_raiz>`: pasta do projeto a escanear (não precisa ser este repositório — é sempre um projeto externo sendo documentado).
- `--project-name`: nome usado para organizar a saída (default: nome da pasta escaneada).
- `--exclude a,b`: pastas extras a ignorar além do [ignored_folders.txt](ignored_folders.txt) padrão.
- `--out-dir`: sobrescreve a pasta de saída inteira (raramente necessário).

Roda em duas fases: **extração** (lê cada arquivo, identifica classes/funções/imports via tree-sitter) e **resolução** (conecta cada import ao arquivo real que ele referencia — Composer/PSR-4 no PHP, `sys.path` no Python, caminho relativo no JS). O resultado sai em:

```
artifacts/<projeto>/auto-generated/out-dependencies/dependencies.json
```

`artifacts/auto-generated` é gerado automaticamente (está no `.gitignore`) — nunca editar nada ali à mão.

### Visualizar o grafo (opcional)

```
python Tools/dependency/export_dot.py artifacts/<projeto>/auto-generated/out-dependencies/dependencies.json
```

Gera um `.dot` (Graphviz) ao lado do JSON. Renderizar depois com `dot -Tsvg grafo.dot -o grafo.svg` (precisa do Graphviz instalado). Ferramenta separada e opcional — lê só o JSON já resolvido, não depende de nada do `dependency.py`.

## Linguagens suportadas

| Linguagem | Confiança | Observação |
|---|---|---|
| PHP | ~90% | É a que mais testei até agora, contra um projeto Laravel real (~270 arquivos): classe/interface/trait/enum, `extends`/`implements`, imports (`use`, alias, agrupado), type hint, `new`/chamada estática/`instanceof`/`catch`, resolução via Composer (PSR-4 + classmap) e via índice próprio (PHP sem autoloader/namespace). Já passou por algumas rodadas de bug real encontrado e corrigido. |
| Python | ~75% | Testado com projeto sintético (pacotes, `__init__.py`, import relativo em vários níveis) e contra o próprio código deste repositório. Cobre import absoluto e relativo, stdlib via `sys.stdlib_module_names`. Não testado ainda contra um projeto Python grande de verdade — pode ter bug em caso de layout mais exótico (`src/`, imports dinâmicos, etc). |
| JavaScript | ~55% | O que tenho menos confiança. Testado só contra um punhado de arquivos reais (majoritariamente config, pouca lógica de aplicação) + um snippet sintético. Cobre `import`/`require`, classe/`extends`, função/método. **Não cobre TypeScript** (`.ts`/`.tsx` são reconhecidos mas sem parser ainda) nem resolução via `node_modules`/`package.json`/alias de bundler (`@/`, `~/`) — só import relativo (`./`, `../`) resolve. |

Em todas as linguagens, o que não é possível resolver (pacote de terceiro, biblioteca nativa) fica com `resolved_path: null` — e, quando dá pra saber que é uma biblioteca/módulo nativo e não um bug (built-in do PHP, stdlib do Python), isso fica marcado explicitamente em vez de ficar ambíguo.

**Fora do escopo, de propósito:** grafo de chamadas (quem invoca qual método em qual objeto) — exigiria inferência de tipo, que é bem mais caro que o que este projeto faz hoje (achar nome de classe em posição sintática fixa, não interpretar lógica).
