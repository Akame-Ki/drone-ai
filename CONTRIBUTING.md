# Contribuer

## Branches

- `main` : version stable.
- `dev` : branche de travail commune. On part de `dev` et on y revient par Pull Request.

```bash
git switch dev
git pull --rebase
git switch -c feat/ma-fonction     # une branche par tâche
# ... commits ...
git push -u origin feat/ma-fonction
```

Puis ouvre une Pull Request vers `dev` sur GitHub ; un autre membre relit avant le
merge. `dev` est fusionnée dans `main` quand c'est stable. On ne pousse pas
directement sur `main`.

## Messages de commit

On suit [Conventional Commits](https://www.conventionalcommits.org/fr/) :

```
<type>(portée optionnelle): description courte en minuscules, sans point final
```

| Type | Pour |
|---|---|
| `feat` | nouvelle fonctionnalité (`feat(control): add flip keys`) |
| `fix` | correction de bug (`fix(hud): clip 3d grid to its panel`) |
| `docs` | README, `docs/` uniquement |
| `refactor` | changement de code sans changement de comportement |
| `test` | ajout ou correction de tests |
| `chore` | config, dépendances, `.gitignore`… |
| `style` | mise en forme uniquement |

- Un commit = un changement. Ne mélange pas une fonctionnalité et de la doc.
- Impératif : « add », pas « added ».
- Changement cassant : ajoute `!` (`feat!: rename telemetry keys`).

## Noms de branches

`feat/...`, `fix/...`, `docs/...` : mêmes types que les commits.
