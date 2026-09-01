# Documentar

## O que é

Sistema de documentação automática de projetos: gerar e manter uma documentação viva de "como o código funciona" (estrutura de pastas, dependências, arquitetura), determinística onde dá (Python puro, sempre regerado do zero) e com julgamento de IA só onde é realmente necessário (arquitetura, regras de negócio) — isso ainda não existe, ver seção de estado abaixo.

Princípio central: separar fato mecânico (dependências, estrutura) de julgamento (regras de negócio, arquitetura). O que é mecânico nunca é editado à mão; o que exige julgamento é gerado como rascunho e revisado por humano.

**Granularidade: um projeto por vez.** Cada execução escaneia UM projeto e gera artefatos só pra ele, em `artifacts/<projeto>/`. Isso é proposital — a ideia é que vários projetos reais (ex: `cuidepet-back`, `cuidepet-front`, `cuidepet-form`) convivam lado a lado dentro de `artifacts/`, cada um com sua própria documentação mecânica, **sem** a ferramenta tentar adivinhar como eles se comunicam entre si nessa etapa. Essa conexão (o que chama a API de quem, o que consome qual biblioteca de qual outro projeto) é uma camada posterior — construída em cima do levantamento bruto de cada projeto individual, não junto com ele. Nesse momento o objetivo não é saber *como* os projetos se falam, é só saber que eles *existem*.

**Estado atual:** a parte mecânica (por projeto individual) já cobre três frentes — dependências internas entre arquivos, mapa de estrutura (fan-in/fan-out) e dependências externas (pacote/biblioteca declarada em manifesto). O resto — arquitetura, BusinessRules, e a camada futura que conecta os projetos entre si — ainda não foi implementado.

## Roadmap

O projeto é dividido em camadas, da mais determinística pra mais aberta:

1. **Mecânica (scripts)** — Individual por projeto. Fato puro extraído do código por script, sem IA: dependências entre arquivos, estrutura de pastas, dependências externas, linguagens usadas. Determinístico, sempre regerado do zero, nunca editado à mão.
   **Estado: em andamento** — dependências internas (PHP/Python/JS, ver "Linguagens suportadas"), estrutura em mapa de calor fan-in/fan-out e dependências externas (Composer/npm/pip) já existem. Falta ampliar cobertura de linguagem (Vue/TypeScript, outros ecossistemas de pacote) e uma leitura mais rica de estrutura além do fan-in/fan-out.

2. **Interconexão (script + LLM)** — Camada que tenta achar as conexões *entre* projetos que a Mecânica deliberadamente não vê: o JS `XYZ` chama o PHP `ABC`, o front `FGH` consome a rota `HIJ`, e por aí vai. Combina script (achar candidatos — ex: strings de URL, chamadas HTTP, nomes de rota) com julgamento de LLM (confirmar a ligação). Construída em cima do levantamento bruto de cada projeto individual, não junto com ele.
   **Estado: não implementado.**

3. **Versionador** — Acompanha como a documentação gerada muda ao longo do tempo conforme o código muda, permitindo comparar entre versões sem precisar regerar tudo do zero.
   **Estado: não implementado.**

4. **Inteligência do projeto** — Camada de julgamento sobre o material bruto já levantado pelas camadas anteriores: regras de negócio, arquitetura, decisões de design — o que exige entender intenção, não só fato mecânico. Gerada como rascunho e sempre revisada por humano, nunca fonte de verdade sozinha. Pós integração com o versionador vai ser capaz de encontrar via script, toda documentação que deve ser analisada a cada atualização do código.
   **Estado: não implementado.**

5. **Extensões** — Você escreve suas próprias ferramentas em cima da estrutura existente (ex: um novo resolver de linguagem, um novo formato de saída, um novo tipo de análise) sem precisar mexer no core.
   **Estado: não implementado** — mas a separação já existente entre `dependency_parsers/` e `dependency_resolvers/` foi pensada com isso em mente.

## Como usar

### Instalação

```
pip install -r requirements.txt
```

### Rodando tudo de uma vez (`regenerate.py`)

É o jeito normal de usar no dia a dia — orquestra as ferramentas de `Tools/` pra cada projeto cadastrado em `registry.toml` (local, no `.gitignore` — copie [registry.example.toml](registry.example.toml) e ajuste os `path` pra sua máquina).

```
python regenerate.py                             # roda todos os projetos do registry.toml
python regenerate.py <nome>                      # roda so um projeto ja cadastrado
python regenerate.py --path <path> --name <nome> # cadastra um projeto novo e roda
```

Cada projeto no `registry.toml` declara sua própria sequência de steps (hoje, tipicamente `dependency/dependency.py` → `structure/structure.py` → `packages/packages.py`, nessa ordem porque o `structure.py` lê a saída do `dependency.py`). O rebuild é **atômico**: builda em `artifacts-temp/` primeiro, e só troca pra `artifacts/<projeto>/auto-generated/` de verdade se **todos** os steps de **todos** os projetos do escopo passarem. Se algum step falhar, o traceback completo vai pra `errors/<timestamp>.json` e nada de `artifacts/` é tocado.

### Ferramentas individuais

Cada uma também roda sozinha, sem o orquestrador — útil pra testar uma ferramenta isolada. Todas aceitam `--project-name` (organiza a saída) e `--auto-generated-dir` (raiz alternativa de saída, usada pelo `regenerate.py` durante o staging).

**Dependências internas** — mapeia import entre arquivos do próprio projeto:
```
python Tools/dependency/dependency.py <pasta_raiz> [--project-name nome]
```
Roda em duas fases: **extração** (lê cada arquivo, identifica classes/funções/imports via tree-sitter) e **resolução** (conecta cada import ao arquivo real que ele referencia — Composer/PSR-4 no PHP, `sys.path` no Python, caminho relativo no JS). Saída: `out-dependencies/dependencies.json`.

**Estrutura (mapa de calor)** — lê a saída acima e monta um mapa fan-in/fan-out (quantos arquivos dependem de X, de quantos X depende) por arquivo e por pasta:
```
python Tools/structure/structure.py --project-name nome [--sort-by fan-in|fan-out]
```
Saída: `out-structure/structure.json` e uma versão ordenada por fan-in ou fan-out.

**Dependências externas** — lê manifesto de empacotador (`composer.json`, `package.json`, `requirements.txt`/`pyproject.toml`), roda **todos** os leitores disponíveis (não para no primeiro que achar — um projeto pode ter PHP e JS ao mesmo tempo, por exemplo):
```
python Tools/packages/packages.py <pasta_raiz> [--project-name nome]
```
Saída: `out-packages/packages.json`.

**Visualizar o grafo de dependências (opcional)**:
```
python Tools/dependency/export_dot.py artifacts/<projeto>/auto-generated/out-dependencies/dependencies.json
```
Gera um `.dot` (Graphviz) ao lado do JSON. Renderizar depois com `dot -Tsvg grafo.dot -o grafo.svg` (precisa do Graphviz instalado). Ferramenta separada e opcional — lê só o JSON já resolvido, não depende de nada do `dependency.py`.

### O que sai em `artifacts/`

```
artifacts/<projeto>/auto-generated/
  out-dependencies/dependencies.json
  out-structure/structure.json
  out-structure/ordered-fan-in-structure.json   (ou ordered-fan-out-*, conforme --sort-by)
  out-packages/packages.json
```

`artifacts/` inteiro é gerado automaticamente (está no `.gitignore`) — nunca editar nada ali à mão, sempre regerado do zero.

## Linguagens suportadas

| Linguagem | Confiança | Observação |
|---|---|---|
| PHP | ~90% | É a que mais testei até agora, contra um projeto Laravel real (~270 arquivos): classe/interface/trait/enum, `extends`/`implements`, imports (`use`, alias, agrupado), type hint, `new`/chamada estática/`instanceof`/`catch`, resolução via Composer (PSR-4 + classmap) e via índice próprio (PHP sem autoloader/namespace). Já passou por algumas rodadas de bug real encontrado e corrigido. |
| Python | ~75% | Testado com projeto sintético (pacotes, `__init__.py`, import relativo em vários níveis) e contra o próprio código deste repositório. Cobre import absoluto e relativo, stdlib via `sys.stdlib_module_names`. Não testado ainda contra um projeto Python grande de verdade — pode ter bug em caso de layout mais exótico (`src/`, imports dinâmicos, etc). |
| JavaScript | ~60% | O que tenho menos confiança. Testado contra um punhado de arquivos de config + dois projetos Vue 3 reais (`.js`/`.ts` soltos, não os `.vue`). Cobre `import`/`require`, classe/`extends`/`implements`, função/método, import relativo (`./`, `../`) e alias de path via `tsconfig.app.json`/`tsconfig.json` (`@/...` etc). `extends`/`implements` resolve por índice próprio (nome único no projeto) e por lista de globals nativos (`Error`, `Array`, `Map`, ...) gerada por reflection no Node, mesmo padrão do PHP. Pacote externo (`node_modules`) vem marcado `external: true` em vez de ficar ambíguo. **`.vue` conta no `_metadata` (aparece como `unsupported`) mas não tem parser** — o conteúdo do `<script>` não é extraído ainda, é a maior parte de um projeto Vue típico. **TypeScript de verdade também não tem parser** (`.ts`/`.tsx` reconhecidos, mesma situação). |

Em todas as linguagens, o que não é possível resolver (pacote de terceiro, biblioteca nativa) fica com `resolved_path: null` — e, quando dá pra saber que é uma biblioteca/módulo nativo e não um bug (built-in do PHP/JS, stdlib do Python), isso fica marcado explicitamente em vez de ficar ambíguo.

**Fora do escopo, de propósito:** grafo de chamadas (quem invoca qual método em qual objeto) — exigiria inferência de tipo, que é bem mais caro que o que este projeto faz hoje (achar nome de classe em posição sintática fixa, não interpretar lógica).

## Detecção de dependências externas (pacotes)

Lê o manifesto de empacotador do projeto e lista as bibliotecas declaradas — diferente da tabela acima, que é sobre dependência *entre arquivos do próprio projeto*. Cada leitor (`Tools/packages/package_detectors/`) só declara quais arquivos quer (por nome exato) e como interpretar o conteúdo; o hub (`packages.py`) varre o projeto uma vez e distribui.

| Ecossistema | Manifesto(s) | Observação |
|---|---|---|
| Composer (PHP) | `composer.json` | `require`/`require-dev`; ignora `php` e `ext-*` (requisito de plataforma, não biblioteca). |
| npm (JS/TS) | `package.json` | `dependencies`/`devDependencies`. |
| pip (Python) | `requirements.txt`, `pyproject.toml` | Trata `requirements.txt` (uma linha por pacote) e `pyproject.toml` (PEP 621 `[project.dependencies]`/`optional-dependencies`, e Poetry `[tool.poetry...]`) — os dois podem coexistir no mesmo projeto sem conflito. Ignora `python` como chave (versão do interpretador, não biblioteca). |

Se um projeto tiver mais de um manifesto (ex: `composer.json` **e** `package.json` juntos, comum em back-end PHP com pipeline de asset via Vite), todos são lidos — o hub não para no primeiro que achar. Nenhum leitor resolve se a versão declarada é a que está de fato instalada; é só o que o manifesto declara.
