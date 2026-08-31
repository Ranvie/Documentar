# Documentar

## O que é

Sistema de documentação automática de projetos: gerar e manter uma documentação viva de "como o código funciona" (estrutura de pastas, dependências, arquitetura), determinística onde dá (Python puro, sempre regerado do zero) e com julgamento de IA só onde é realmente necessário (arquitetura, regras de negócio) — isso ainda não existe, ver seção de estado abaixo.

Princípio central: separar fato mecânico (dependências, estrutura) de julgamento (regras de negócio, arquitetura). O que é mecânico nunca é editado à mão; o que exige julgamento é gerado como rascunho e revisado por humano.

**Granularidade: um projeto por vez.** Cada execução escaneia UM projeto e gera artefatos só pra ele, em `artifacts/<projeto>/`. Isso é proposital — a ideia é que vários projetos reais (ex: `cuidepet-back`, `cuidepet-front`, `cuidepet-form`) convivam lado a lado dentro de `artifacts/`, cada um com sua própria documentação mecânica, **sem** a ferramenta tentar adivinhar como eles se comunicam entre si nessa etapa. Essa conexão (o que chama a API de quem, o que consome qual biblioteca de qual outro projeto) é uma camada posterior — construída em cima do levantamento bruto de cada projeto individual, não junto com ele. Nesse momento o objetivo não é saber *como* os projetos se falam, é só saber que eles *existem*.

**Estado atual:** mapeamento de dependências e mapa de calor de fan-in/fan-out já existem (por projeto individual), orquestrados pelo `regenerate.py`. O resto — packages, arquitetura, BusinessRules, e a camada futura que conecta os projetos entre si — ainda não foi implementado.

## Como usar

### Instalação

```
pip install -r requirements.txt
```

### Rodar tudo pra um projeto (`regenerate.py`)

Copie [registry.example.toml](registry.example.toml) para `registry.toml` (fica fora do git — os paths são absolutos e específicos da máquina) e ajuste `path` pros projetos reais.

```
python regenerate.py                              # roda todos os projetos do registry.toml
python regenerate.py <nome>                        # roda so um projeto ja cadastrado
python regenerate.py --path <path> --name <nome>   # cadastra/atualiza o projeto e roda
```

Cada projeto no `registry.toml` tem uma lista de `steps` (ferramenta de `Tools/` + `args`), executados em ordem. O resultado de uma rodada é montado numa pasta de staging (`artifacts-temp/`) e só substitui o `artifacts/<projeto>/auto-generated/` definitivo se **todos** os steps de **todos** os projetos do escopo pedido tiverem sucesso — se algo falhar, nada é trocado e o staging é descartado. Falhas ficam registradas em `errors/YYYY-MM-DD_HH-mm-ss.json` (projeto, step, comando e stderr completo).

### Rodar uma ferramenta isolada (debug/manual)

Fora do `regenerate.py`, cada ferramenta em `Tools/` também roda sozinha — útil pra debug. Toda ferramenta aceita `--project-name` e `--auto-generated-dir` (raiz de `auto-generated/` do projeto); sem eles, cai no default `artifacts/<projeto>/auto-generated/`.

#### Mapeador de dependências

```
python Tools/dependency/dependency.py <pasta_raiz> [--project-name nome]
```

- `<pasta_raiz>`: pasta do projeto a escanear (não precisa ser este repositório — é sempre um projeto externo sendo documentado).
- `--project-name`: nome usado para organizar a saída (default: nome da pasta escaneada).
- `--auto-generated-dir`: raiz de `auto-generated/` do projeto (default: `artifacts/<projeto>/auto-generated`).
- `--exclude a,b`: pastas extras a ignorar além do [ignored_folders.txt](ignored_folders.txt) padrão.
- `--out-dir`: sobrescreve só a pasta de saída (raramente necessário — normalmente basta `--auto-generated-dir`).

Roda em duas fases: **extração** (lê cada arquivo, identifica classes/funções/imports via tree-sitter) e **resolução** (conecta cada import ao arquivo real que ele referencia — Composer/PSR-4 no PHP, `sys.path` no Python, caminho relativo no JS). O resultado sai em:

```
{auto-generated-dir}/out-dependencies/dependencies.json
```

#### Mapa de calor (fan-in/fan-out)

```
python Tools/structure/structure.py --project-name <nome> [--sort-by fan-in|fan-out]
```

- `--project-name`: obrigatório — usado para achar o `dependencies.json` do projeto (rode o mapeador de dependências antes) e organizar a saída.
- `--auto-generated-dir`: raiz de `auto-generated/` do projeto (default: `artifacts/<projeto>/auto-generated`).
- `--sort-by fan-in|fan-out`: métrica usada pra ordenar a árvore no segundo arquivo de saída (default: `fan-in`).

Lê o `dependencies.json` já resolvido e calcula, por arquivo e por pasta (rollup), quantos arquivos internos cada um referencia (fan-out) e é referenciado por (fan-in). Gera:

```
{auto-generated-dir}/out-structure/structure.json
{auto-generated-dir}/out-structure/ordered-<fan-in|fan-out>-structure.json
```

`artifacts/` é gerado automaticamente (está no `.gitignore`) — nunca editar nada ali à mão.

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
| JavaScript | ~60% | O que tenho menos confiança. Testado contra um punhado de arquivos de config + um projeto Vue 3 real (só os `.js`/`.ts` soltos, ~50 arquivos). Cobre `import`/`require`, classe/`extends`, função/método, import relativo (`./`, `../`) e alias de path via `tsconfig.app.json`/`tsconfig.json` (`@/...` etc). Pacote externo (`node_modules`) vem marcado `external: true` em vez de ficar ambíguo. **`.vue` conta no `_metadata` (aparece como `unsupported`) mas não tem parser** — o conteúdo do `<script>` não é extraído ainda, é a maior parte de um projeto Vue típico. **TypeScript de verdade também não tem parser** (`.ts`/`.tsx` reconhecidos, mesma situação). |

Em todas as linguagens, o que não é possível resolver (pacote de terceiro, biblioteca nativa) fica com `resolved_path: null` — e, quando dá pra saber que é uma biblioteca/módulo nativo e não um bug (built-in do PHP, stdlib do Python), isso fica marcado explicitamente em vez de ficar ambíguo.

**Fora do escopo, de propósito:** grafo de chamadas (quem invoca qual método em qual objeto) — exigiria inferência de tipo, que é bem mais caro que o que este projeto faz hoje (achar nome de classe em posição sintática fixa, não interpretar lógica).
