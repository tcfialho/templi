# Templi

Implementação Python do motor de plugins YAML. Aplica um plugin num projeto, renderiza templates e executa hooks.

## Uso básico

Pasta local:

```powershell
python -m templi.main apply plugin "C:\caminho\do\plugin"
```

Repositório Git (clone em cache, branch/tag opcional):

```powershell
python -m templi.main apply plugin "https://github.com/org/repo-plugins" `
  --subpath dot-net/my-plugin-api-rest --git-ref main -q -s
```

| Flag | O que faz |
|---|---|
| `-q` | não interativo (usa defaults ou `--inputs-json`) |
| `-s` | ignora aviso de workspace |
| `--inputs-json '{"chave":"valor"}'` | passa inputs sem prompt |
| `--subpath` | pasta do plugin dentro do clone ou do caminho local (monorepo) |
| `--git-ref` | branch ou tag no repositório remoto |

Clone em cache fixo: `%USERPROFILE%\.cache\templi\plugins\`. A cada apply o Templi atualiza o cache via **Dulwich** (biblioteca Python — clone/fetch sem `git` no PATH). Use URL **HTTPS** do repositório.

Repositórios privados reutilizam o mesmo login do Git: o Templi chama `git credential fill` (respeita `credential.helper` — GCM no Windows, osxkeychain no macOS, libsecret/store no Linux). Se `git` não estiver instalado, tenta `~/.git-credentials` / XDG (`credential.helper store`). Não é necessário PAT na URL.

## Chamando outro plugin dentro de um hook `run`

O hook `run` executa a linha no shell (`python -m templi.main`, etc.) — sem tratamento especial no Templi. Se o comando falhar, o apply do plugin pai é interrompido.

Exemplo com pasta local ou URL Git (o subprocesso do filho usa o mesmo resolvedor de plugin):

```yaml
- python -m templi.main apply plugin "https://github.com/org/plugin-x" --git-ref main -s -q --project_name '{{project_name}}'
```

Durante os hooks, o Templi mantém `.templi/manifest.lock` (ou `.compat/manifest.lock` em modo compat). Subprocessos que chamam `templi apply` no mesmo projeto não gravam o manifesto até o lock ser liberado; o apply pai grava uma vez no fim. Lock órfão (crash) é removido automaticamente se o PID dono não existir mais ou após 4 horas.    

**Migrando de outro runtime:** referências `company/...` no YAML continuam exigindo o CLI de referência no PATH, ou reescreva para caminho/URL explícitos.
## Emulando outro runtime (OSK)

> **OSK** (*Other Stack*) = runtime CLI externo de referência. Só muda onde o Templi grava estado.

| Variável | Para quê |
|---|---|
| `TEMPLI_COMPAT_NAME=osk` | usa `.osk/osk.yaml` em vez de `.templi/manifest.yaml` |
| `PYTHONPATH=C:\...\Templi\src` | se `templi` não estiver instalado via pip |

## Testes

```powershell
python -m pytest tests/
```
