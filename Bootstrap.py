from pathlib import Path
import requests


class Bootstrap:
    def __init__(self):
        self.cwd = Path.cwd()

    def create_gitignore(self):
        currrent_dir = self.cwd
        gitignore_file = currrent_dir / ".gitignore"
        gitignore = requests.get(
            "https://www.toptal.com/developers/gitignore/api/osx,linux,python,windows,pycharm,visualstudiocode,sam,sam+config,terraform"
        )
        gitignore_file.write_text(gitignore.text)
        print("✅ .gitignore created")

    def create_readme(self):
        Path.touch(self.cwd / "README.md")
        print("✅ README.md created")

    def create_github_actions(self):
        deploy_yml = self.cwd / ".github" / "workflows" / "deploy.yml"
        deploy_yml.parent.mkdir(parents=True, exist_ok=True)
        deploy_yml.write_text(
            """
name: 'Deploy Workflow'

on:
  push:
    branches:
      - develop
      - main
    paths:
      - 'infra/**'
permissions:
  id-token: write
  contents: read

jobs:
  terraform:
    # dentro do repositorio foi criado 2 enviroments dev e prod 
    # um para a branch develop e outro para a branch main
    # dentro de cada possui variaveis e secrets configurados para cada ambiente
    # assim é possivel recuperar envs e secrets de acordo com o ambiente de forma dinamica
    environment: ${{ github.ref == 'refs/heads/develop' && 'dev' || 'prod' }}
    runs-on: ubuntu-latest
    defaults:
      run:
        shell: bash
    env:
      ENVIRON: ${{ github.ref == 'refs/heads/develop' && 'dev' || 'prod' }}
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
          DESTROY="$(jq -r ".$ENVIRON" ./infra/destroy_config.json)"
          echo "destroy=$(echo $DESTROY)" >> $GITHUB_OUTPUT

      - name: Terraform Init
        run: |
          cd infra && terraform init /\
            -backend-config="bucket=${{ vars.BACKEND_BUCKET }}" /\
            -backend-config="key=${{ github.event.repository.name }}" /\
            -backend-config="region=${{ vars.BACKEND_REGION }}" /\
            -backend-config="use_lockfile=true"

      - name: Terraform Validate
        run: terraform validate

      - name: Terraform Destroy
        if: steps.read-destroy-config.outputs.destroy == 'true'
        id: terraform-destroy
        run: cd infra &&
          terraform workspace select $ENVIRON || terraform workspace new $ENVIRON &&
          terraform destroy -var-file="./envs/$ENVIRON/terraform.tfvars" -auto-approve

      - name: Terraform Plan
        if: steps.read-destroy-config.outputs.destroy != 'true'
        id: terraform-plan
        run: cd infra &&
          terraform workspace select $ENVIRON || terraform workspace new $ENVIRON &&
          terraform plan -var-file="./envs/$ENVIRON/terraform.tfvars" -out="$ENVIRON.plan"

      - name: Terraform Apply
        if: steps.read-destroy-config.outputs.destroy != 'true'
        id: terraform-apply
        run: cd infra &&
          terraform workspace select $ENVIRON || terraform workspace new $ENVIRON &&
          terraform apply "$ENVIRON.plan"
      """
        )

    def create_terraform_template(self):
        ### Create infra directory
        infra_dir = self.cwd / "infra"
        envs_dir = infra_dir / "envs"
        dev_dir = envs_dir / "dev"
        prod_dir = envs_dir / "prod"
        dirs = [infra_dir, envs_dir, dev_dir, prod_dir]
        for dir in dirs:
            dir.mkdir(parents=True, exist_ok=True)
            print(f"✅ {dir} created")
            if dir == dev_dir or dir == prod_dir:
                Path.touch(dir / "terraform.tfvars")
                print(f"✅ {dir / 'terraform.tfvars'} created")

        (infra_dir / "destroy_config.json").write_text(
            """
{
  "dev": false,
  "prod": false
}
      """
        )

        terraform_files = ["main.tf", "providers.tf", "variables.tf"]
        for file in terraform_files:
            if file == "providers.tf":
                (infra_dir / file).write_text(
                    """
terraform {
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
                    """
variable "env_name" {
  description = "The name of the environment"
  type        = string
}

variable "project_name" {
  description = "The name of the project"
  type        = string 
}
            """
                )
            (infra_dir / file).touch()
            print(f"✅ {infra_dir / file} created")

    def start(self):
        self.create_gitignore()
        self.create_readme()
        self.create_github_actions()
        self.create_terraform_template()
        print("✅ Project bootstrapped successfully")
