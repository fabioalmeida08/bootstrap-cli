from pathlib import Path
import requests


class Terraform_bootstrap:
    def __init__(self):
        self.cwd = Path.cwd()

    def create_gitignore(self):
        currrent_dir = self.cwd
        gitignore_file = currrent_dir / ".gitignore"
        gitignore = requests.get(
            "https://www.toptal.com/developers/gitignore/api/osx,linux,python,windows,pycharm,visualstudiocode,sam,sam+config,terraform"
        )
        gitignore_file.write_text(gitignore.text)

    def create_readme(self):
        Path.touch(self.cwd / "README.md")

    def create_github_actions(self):
        deploy_yml = self.cwd / ".github" / "workflows" / "deploy.yml"
        deploy_yml.parent.mkdir(parents=True, exist_ok=True)
        deploy_yml.write_text(
            """# variaveis/secrets de repositório que devem ser criadas
# criar também dois environments no repositorio dev e prod
# - AWS_REGION / região da aws
# - BACKEND_BUCKET / nome do bucket s3 para armazenar o estado do terraform
# - BACKEND_REGION / região do bucket s3
# - AWS_ASSUME_ROLE_ARN / arn da role que o workflow vai assumir para executar o terraform

name: 'Terraform Workflow'

on:
  push:
    branches:
      - develop
      - main
    paths:
      # somente executa o workflow se houver alterações no diretórios listados
      # possivel usar o paths-ignore para ignorar diretórios
      - 'infra/**'
permissions:
  id-token: write
  contents: read

jobs:
  terraform:
    # dentro do repositorio foi criado 2 enviroments dev e prod. 
    # um para o branch develop e outro para a branch main.
    # cada environment do repositorio possui variaveis e secrets diferentes
    # assim é possivel recuperar envs e secrets de acordo com o ambiente de forma dinamica.
    # aqui é o enviroment é selecionado de acordo com a branch que disparou o workflow
    environment: ${{ github.ref == 'refs/heads/develop' && 'dev' || 'prod' }}
    runs-on: ubuntu-latest
    defaults:
      run:
        shell: bash
    env:
      # aqui vão as variaveis de ambiente dentro da vm do workflow.
      # variaveis de ambiente no terraform são definidas com o prefixo TF_VAR_ e são recuperadas
      # de acordo com o environment selecionado pelo job
      ENVIRONMENT: ${{ github.ref == 'refs/heads/develop' && 'dev' || 'prod' }}
      TF_VAR_env_name: ${{ vars.ENV_NAME }}
      TF_VAR_project_name: ${{ github.event.repository.name }}

    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Setup Terraform
        uses: hashicorp/setup-terraform@v3

      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: ${{ secrets.AWS_ASSUME_ROLE_ARN }}
          role-session-name: GitHub_to_AWS_via_FederatedOIDC
          aws-region: ${{ vars.AWS_REGION }}

      - name: Read destroy configuration
        id: read-destroy-config
        run: |
          DESTROY="$(jq -r ".$ENVIRONMENT" ./infra/destroy_config.json)"
          echo "destroy=$(echo $DESTROY)" >> $GITHUB_OUTPUT

      - name: Terraform Init
        run: |
          cd infra && terraform init \\
            -backend-config="bucket=${{ vars.BACKEND_BUCKET }}" \\
            -backend-config="key=${{ github.event.repository.name }}" \\
            -backend-config="region=${{ vars.BACKEND_REGION }}" \\
            -backend-config="use_lockfile=true"

      - name: Terraform Validate
        run: terraform validate

      - name: Terraform Destroy
        if: steps.read-destroy-config.outputs.destroy == 'true'
        id: terraform-destroy
        run: cd infra &&
          terraform workspace select $ENVIRONMENT || terraform workspace new $ENVIRONMENT &&
          terraform destroy -var-file="./envs/$ENVIRONMENT/terraform.tfvars" -auto-approve

      - name: Terraform Plan
        if: steps.read-destroy-config.outputs.destroy != 'true'
        id: terraform-plan
        run: cd infra &&
          terraform workspace select $ENVIRONMENT || terraform workspace new $ENVIRONMENT &&
          terraform plan -var-file="./envs/$ENVIRONMENT/terraform.tfvars" -out="$ENVIRONMENT.plan"

      - name: Terraform Apply
        if: steps.read-destroy-config.outputs.destroy != 'true'
        id: terraform-apply
        run: cd infra &&
          terraform workspace select $ENVIRONMENT || terraform workspace new $ENVIRONMENT &&
          terraform apply "$ENVIRONMENT.plan"

      """
        )

    def create_terraform_template(self):
        infra_dir = self.cwd / "infra"
        envs_dir = infra_dir / "envs"
        dev_dir = envs_dir / "dev"
        prod_dir = envs_dir / "prod"
        dirs = [infra_dir, envs_dir, dev_dir, prod_dir]
        for dir in dirs:
            dir.mkdir(parents=True, exist_ok=True)
            if dir == dev_dir or dir == prod_dir:
                Path.touch(dir / "terraform.tfvars")

        (infra_dir / "destroy_config.json").write_text(
            """{
  "dev": false,
  "prod": false
}
      """
        )

        terraform_files = ["main.tf", "providers.tf", "variables.tf", "backend.tf"]
        for file in terraform_files:
            if file == "providers.tf":
                (infra_dir / file).write_text(
                    """terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
    }
  }
}

provider "aws" {
  # Configuration options
  region = "us-east-1"

  default_tags {
    tags = {
      Environment = var.env_name
      Project     = var.project_name
    }
  }
}
          """
                )
            elif file == "variables.tf":
                (infra_dir / file).write_text(
                    """variable "env_name" {
  description = "The name of the environment"
  type        = string
}

variable "project_name" {
  description = "The name of the project"
  type        = string 
}
            """
                )
            elif file == "backend.tf":
                (infra_dir / file).write_text(
                    """terraform {
  backend "s3" {}
}
                    """
                )
            (infra_dir / file).touch()

    def start(self):
        self.create_gitignore()
        self.create_readme()
        self.create_github_actions()
        self.create_terraform_template()
