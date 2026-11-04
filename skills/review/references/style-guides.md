# Style and convention sources

Read this when you are about to raise a `style` finding, or when the
collector shows no linter covering a changed language.

Every URL below was checked to resolve (HTTP 200) on 2026-10-24.

## Precedence: whose rule wins

1. **Repo configuration.** Linter and formatter configs (`ruff.toml`,
   `[tool.ruff]`, `eslint.config.*`, `.prettierrc`, `biome.json`,
   `.golangci.yml`, `rustfmt.toml`, `.markdownlint*`), `.editorconfig`,
   `CONTRIBUTING.md`, and `AGENTS.md`/`CLAUDE.md`. If the repo has decided,
   that's the rule, even where a published guide disagrees.
2. **The language's canonical guide** (the tables below). Use it only where
   the repo is silent.
3. **Taste.** Never a finding. If you can't cite a rule from 1 or 2, drop it
   or ask it as a question.

### Rules for style findings

- **Defer to tools.** If the collector ran a linter or formatter for that
  file (`tool_runs[].status == "ran"`), report its output. Don't paraphrase
  it or add a second opinion on what it already covers. If a configured
  tool was `skipped` or `timed_out`, say so under `not_inspected`. Don't
  hand-lint to make up for it.
- **Where no tool covers the file**, raise style findings yourself at
  **P3** (or `nit` for pure preference within a guide's leeway).
- **Cite the rule and the URL.** `rule` names the rule (`google-pystyle-2.12`,
  `PEP8-E711`, `SC2086`, `ruff:B006`). `references[]` carries the
  URL, deep-linked to the section where the page has anchors.
  `findings.py validate` rejects a style finding with no reference.
- **Check the guide before citing it.** If you are not sure what a section
  says, fetch it and quote it. Don't paraphrase from memory: guides get
  revised and section numbers move.
- A correctness bug that happens to be in a style guide (a mutable default
  argument, a bare `except:` that swallows `KeyboardInterrupt`) belongs on the
  `correctness` or `reliability` axis at its real severity. You can still cite
  the guide.

## Cross-language

| Source | URL |
| --- | --- |
| Google style guides (index) | https://google.github.io/styleguide/ |
| EditorConfig | https://editorconfig.org/ |
| Conventional Commits 1.0.0 | https://www.conventionalcommits.org/en/v1.0.0/ |
| Google Markdown style guide | https://google.github.io/styleguide/docguide/style.html |
| markdownlint rules | https://github.com/DavidAnson/markdownlint/blob/main/doc/Rules.md |

## Python

| Source | URL |
| --- | --- |
| PEP 8 (style) | https://peps.python.org/pep-0008/ |
| PEP 257 (docstrings) | https://peps.python.org/pep-0257/ |
| PEP 484 (type hints) | https://peps.python.org/pep-0484/ |
| PEP 621 (project metadata in pyproject.toml) | https://peps.python.org/pep-0621/ |
| pyproject.toml specification (current) | https://packaging.python.org/en/latest/specifications/pyproject-toml/ |
| Google Python Style Guide | https://google.github.io/styleguide/pyguide.html |
| - 2.4 Exceptions (no bare `except:`) | https://google.github.io/styleguide/pyguide.html#24-exceptions |
| - 2.12 Default argument values (no mutable defaults) | https://google.github.io/styleguide/pyguide.html#212-default-argument-values |
| Ruff rules | https://docs.astral.sh/ruff/rules/ |
| - B006 mutable-argument-default | https://docs.astral.sh/ruff/rules/mutable-argument-default/ |
| - E722 bare-except | https://docs.astral.sh/ruff/rules/bare-except/ |
| Black code style | https://black.readthedocs.io/en/stable/the_black_code_style/current_style.html |
| mypy | https://mypy.readthedocs.io/en/stable/ |

## JavaScript and TypeScript

| Source | URL |
| --- | --- |
| Google TypeScript Style Guide | https://google.github.io/styleguide/tsguide.html |
| Google JavaScript Style Guide | https://google.github.io/styleguide/jsguide.html |
| TypeScript handbook: Do's and Don'ts | https://www.typescriptlang.org/docs/handbook/declaration-files/do-s-and-don-ts.html |
| Airbnb JavaScript Style Guide | https://github.com/airbnb/javascript |
| StandardJS rules | https://standardjs.com/rules.html |
| ESLint rules | https://eslint.org/docs/latest/rules/ |
| typescript-eslint rules | https://typescript-eslint.io/rules/ |
| Biome linter rules | https://biomejs.dev/linter/ |
| Prettier rationale | https://prettier.io/docs/rationale.html |

## Go

| Source | URL |
| --- | --- |
| Effective Go | https://go.dev/doc/effective_go |
| Go Code Review Comments | https://go.dev/wiki/CodeReviewComments |
| Google Go Style Guide | https://google.github.io/styleguide/go/ |
| - Style decisions | https://google.github.io/styleguide/go/decisions |
| - Best practices | https://google.github.io/styleguide/go/best-practices |
| Uber Go Style Guide | https://github.com/uber-go/guide/blob/master/style.md |
| gofmt | https://pkg.go.dev/cmd/gofmt |
| golangci-lint | https://golangci-lint.run/ |

## Rust

| Source | URL |
| --- | --- |
| Rust API Guidelines | https://rust-lang.github.io/api-guidelines/ |
| - Checklist | https://rust-lang.github.io/api-guidelines/checklist.html |
| Rust Style Guide | https://doc.rust-lang.org/nightly/style-guide/ |
| rustfmt configuration | https://rust-lang.github.io/rustfmt/ |
| Clippy lints | https://rust-lang.github.io/rust-clippy/master/index.html |

## JVM, Apple, Dart, other languages

| Language | Source | URL |
| --- | --- | --- |
| Java | Google Java Style Guide | https://google.github.io/styleguide/javaguide.html |
| Kotlin | Kotlin coding conventions | https://kotlinlang.org/docs/coding-conventions.html |
| Swift | Swift API Design Guidelines | https://www.swift.org/documentation/api-design-guidelines/ |
| Dart | Effective Dart | https://dart.dev/effective-dart |
| Dart | Effective Dart: Style | https://dart.dev/effective-dart/style |
| C++ | Google C++ Style Guide | https://google.github.io/styleguide/cppguide.html |
| C# | .NET coding conventions | https://learn.microsoft.com/en-us/dotnet/csharp/fundamentals/coding-style/coding-conventions |
| Ruby | Ruby Style Guide | https://rubystyle.guide/ |
| PHP | PSR-12 extended coding style | https://www.php-fig.org/psr/psr-12/ |
| HTML/CSS | Google HTML/CSS Style Guide | https://google.github.io/styleguide/htmlcssguide.html |

## Shell

| Source | URL |
| --- | --- |
| Google Shell Style Guide | https://google.github.io/styleguide/shellguide.html |
| ShellCheck wiki | https://www.shellcheck.net/wiki/ |
| ShellCheck checks index | https://github.com/koalaman/shellcheck/wiki/Checks |
| SC2086 (quote to prevent word splitting) | https://www.shellcheck.net/wiki/SC2086 |

## Infrastructure and CI

| Source | URL |
| --- | --- |
| Terraform style conventions | https://developer.hashicorp.com/terraform/language/style |
| Dockerfile best practices | https://docs.docker.com/build/building/best-practices/ |
| hadolint rules | https://github.com/hadolint/hadolint#rules |
| GitHub Actions workflow syntax | https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax |
| GitHub Actions secure use | https://docs.github.com/en/actions/reference/security/secure-use |
| Preventing pwn requests (`pull_request_target`) | https://securitylab.github.com/resources/github-actions-preventing-pwn-requests/ |
