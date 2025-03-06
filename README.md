# Bootstrap CLI

Uma ferramenta de linha de comando (CLI) para criar rapidamente a estrutura inicial e boilerplate de projetos Terraform integrados com GitHub Actions. Projetada para agilizar o setup de infraestrutura como código (IaC), com flexibilidade para expansão futura para outros tipos de templates conforme necessário.

## Propósito

O objetivo inicial desta CLI é automatizar a criação de:
- Estrutura de diretórios para projetos Terraform.

- Arquivos de configuração básicos (ex.: main.tf, variables.tf).

- Workflow do GitHub Actions para deploy automatizado de infraestrutura.

No futuro, a CLI pode ser expandida para suportar outros templates e frameworks além do Terraform.

## Instalação

Basta clonar o repositório e executar o arquivo de instalação

```
git clone https://github.com/fabioalmeida08/bootstrap-cli.git
cd bootstrap-cli
bash install.sh
```

## Uso

somente executar o comando `bootstrap` dentro do diretorio desejado