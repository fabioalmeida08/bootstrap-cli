from pathlib import Path
import shutil


class Terraform_bootstrap:
    def __init__(self):
        self.cwd = Path.cwd()

    def create_gitignore(self):
        currrent_dir = self.cwd
        # gitignore_file = currrent_dir / ".gitignore"
        # gitignore = requests.get(
        #     "https://www.toptal.com/developers/gitignore/api/osx,linux,python,windows,pycharm,visualstudiocode,sam,sam+config,terraform"
        # )
        # gitignore_file.write_text(gitignore.text)
        gitignore_file = Path(__file__).parent / "gitignorefile"
        shutil.copy(gitignore_file, currrent_dir / ".gitignore")

    def create_readme(self):
        Path.touch(self.cwd / "README.md")

    def create_github_actions_workflow(self):
        deploy_yml = self.cwd / ".github" / "workflows" / "deploy.yml"
        configure_aws_credentials = (
            self.cwd / ".github" / "actions" / "configure-aws-credentials.yml"
        )
        configure_aws_credentials.parent.mkdir(parents=True, exist_ok=True)
        configure_aws_credentials.write_text(
            """name: 'Configure AWS Credentials'
description: 'Configura as credenciais da AWS usando OIDC'
inputs:
  role-to-assume:
    description: 'ARN da role da AWS a ser assumida'
    required: true
  aws-region:
    description: 'Região da AWS'
    required: true
runs:
  using: 'composite'
  steps:
    - name: Configure AWS credentials
      uses: aws-actions/configure-aws-credentials@v4
      with:
        role-to-assume: ${{ inputs.role-to-assume }}
        role-session-name: GitHub_to_AWS_via_FederatedOIDC
        aws-region: ${{ inputs.aws-region }}
            """
        )
        deploy_yml.parent.mkdir(parents=True, exist_ok=True)
        deploy_yml.write_text(
            """# variaveis/secrets de repositório que devem ser criadas
# criar também dois environments no repositorio dev e prod
# - DEFAULT_AWS_REGION / região default que o openid connect vai assumir para comandos aws
# - TERRAFORM_BACKEND_BUCKET / nome do bucket s3 para armazenar o estado do terraform
# - TERRAFORM_BACKEND_REGION / região do bucket s3 do backend do terraform
# - AWS_ASSUME_ROLE_ARN / arn da role que o workflow vai assumir com openid connect
# - SAM_STACK_NAME / nome do stack do sam
# - SAM_S3_BUCKET / nome do bucket s3 para armazenar o artefato do sam
# - SAM_AWS_REGION / região do bucket s3 do sam

name: 'Deploy Workflow'

on:
  push:
    branches:
      - develop
      - main
    paths:
      # somente executa o workflow se houver alterações no diretórios listados
      # possivel usar o paths-ignore para ignorar diretórios
      - 'infra/**'
      - 'sam-app/**'
      - 'destroy/**'
permissions:
  id-token: write
  contents: read
env:
  # aqui vão as variaveis globais de ambiente do workflow.
  # variaveis de ambiente no terraform são definidas com o prefixo TF_VAR_ e são recuperadas
  # de acordo com o environment selecionado pelo job
  ENVIRONMENT: ${{ github.ref == 'refs/heads/develop' && 'dev' || 'prod' }}
  TF_VAR_project_name: ${{ github.event.repository.name }}

jobs:
  check_destroy:
    runs-on: ubuntu-latest
    outputs:
      destroy: ${{ steps.read-destroy-config.outputs.destroy }}   
    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Read destroy configuration
        id: read-destroy-config
        run: |
          DESTROY="$(jq -r ".$ENVIRONMENT" ./destroy/destroy_config.json)"
          echo $DESTROY
          echo "destroy=$(echo $DESTROY)" >> $GITHUB_OUTPUT

  destroy-infra:
    needs: check_destroy
    if: needs.check_destroy.outputs.destroy == 'true'
    environment: ${{ github.ref == 'refs/heads/develop' && 'dev' || 'prod' }}
    runs-on: ubuntu-latest   
    steps:
      - name: Checkout code
        uses: actions/checkout@v4      
    
      - name: Configure AWS credentials
        uses: ./.github/actions/configure-aws-credentials
        with:
          role-to-assume: ${{ secrets.AWS_ASSUME_ROLE_ARN }}
          aws-region: ${{ secrets.AWS_REGION_DEFAULT }}          
      
      - name: Install AWS SAM CLI
        uses: aws-actions/setup-sam@v2      
          
      - name: Setup Terraform
        uses: hashicorp/setup-terraform@v3

      - name: Destroy Sam
        run: |
          cd sam-app
          sam delete \\
          --stack-name ${{ secrets.SAM_STACK_NAME }} \\
          --region ${{ secrets.SAM_AWS_REGION }} \\
          --no-prompts             

      - name: Terraform Init
        run: |
          cd infra && terraform init \\
            -backend-config="bucket=${{ secrets.TERRAFORM_BACKEND_BUCKET }}" \\
            -backend-config="key=${{ github.event.repository.name }}" \\
            -backend-config="region=${{ secrets.TERRAFORM_BACKEND_REGION }}" \\
            -backend-config="use_lockfile=true"                     
            
      - name: Terraform Destroy
        id: terraform-destroy
        run: cd infra &&
          terraform workspace select $ENVIRONMENT || terraform workspace new $ENVIRONMENT &&
          terraform destroy -var-file="./envs/$ENVIRONMENT/terraform.tfvars" -auto-approve

  terraform:
    # depende do job check_destroy
    needs: check_destroy
    # executa somente se o destroy for diferente de true
    if: needs.check_destroy.outputs.destroy != 'true'
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

    steps:
      - name: Checkout code
        uses: actions/checkout@v4      
      
      - name: Configure AWS credentials
        uses: ./.github/actions/configure-aws-credentials
        with:
          role-to-assume: ${{ secrets.AWS_ASSUME_ROLE_ARN }}
          aws-region: ${{ secrets.AWS_REGION_DEFAULT }}    

      - name: Setup Terraform
        uses: hashicorp/setup-terraform@v3


      - name: Terraform Init
        run: |
          cd infra && terraform init \\
            -backend-config="bucket=${{ secrets.TERRAFORM_BACKEND_BUCKET }}" \\
            -backend-config="key=${{ github.event.repository.name }}" \\
            -backend-config="region=${{ secrets.TERRAFORM_BACKEND_REGION }}" \\
            -backend-config="use_lockfile=true"

      - name: Terraform Validate
        run: terraform validate

      - name: Terraform Plan
        id: terraform-plan
        run: cd infra &&
          terraform workspace select $ENVIRONMENT || terraform workspace new $ENVIRONMENT &&
          terraform plan -var-file="./envs/$ENVIRONMENT/terraform.tfvars" -out="$ENVIRONMENT.plan"

      - name: Terraform Apply
        id: terraform-apply
        run: |
          cd infra
          terraform workspace select $ENVIRONMENT || terraform workspace new $ENVIRONMENT
          terraform apply "$ENVIRONMENT.plan"
          # exemplo de como criar um summary do workflow com outputs do comando
          BUCKET_NAME=$(terraform output -raw s3_bucket_name)
          echo "## Nome do Bucket S3" >> $GITHUB_STEP_SUMMARY
          echo "``````" >> $GITHUB_STEP_SUMMARY
          echo "$BUCKET_NAME" >> $GITHUB_STEP_SUMMARY
          echo "``````" >> $GITHUB_STEP_SUMMARY

  aws-sam:
    runs-on: ubuntu-latest
    needs:
      - terraform
    environment: ${{ github.ref == 'refs/heads/develop' && 'dev' || 'prod' }}

    steps:
    - name: Checkout code
      uses: actions/checkout@v4      

    - name: Configure AWS credentials
      uses: ./.github/actions/configure-aws-credentials
      with:
        role-to-assume: ${{ secrets.AWS_ASSUME_ROLE_ARN }}
        aws-region: ${{ secrets.AWS_REGION_DEFAULT }}    

    - name: Setup python
      uses: actions/setup-python@v5
      with:
        python-version: '3.13' 
    
    - name: Install AWS SAM CLI
      uses: aws-actions/setup-sam@v2

    - name: Build and Deploy API
      run: |
        cd sam-app
        sam build
        sam deploy \\
        --stack-name ${{ secrets.SAM_STACK_NAME }} \\
        --s3-bucket ${{ secrets.SAM_S3_BUCKET }} \\
        --capabilities CAPABILITY_IAM \\
        --region ${{ secrets.SAM_AWS_REGION }} \\
        --no-confirm-changeset \\
        --no-fail-on-empty-changeset         

    - name: Capture API URL and Update Summary
      run: |
        cd sam-app
        API_URL=$(sam list stack-outputs --stack-name ${{ secrets.SAM_STACK_NAME }} --output json | jq -r '.[] | select(.OutputKey=="HelloWorldApi") | .OutputValue')
        echo "## Hello World API URL" >> $GITHUB_STEP_SUMMARY
        echo "``````" >> $GITHUB_STEP_SUMMARY
        echo "$API_URL" >> $GITHUB_STEP_SUMMARY
        echo "``````" >> $GITHUB_STEP_SUMMARY        
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


    def create_destroy_config(self):
        destroy_dir = self.cwd / "destroy"
        destroy_dir.mkdir(parents=True, exist_ok=True)
        destroy_config = destroy_dir / "destroy_config.json"
        destroy_config.write_text(
            """{
  "dev": false,
  "prod": false
}
            """
        )
    def start(self):
        self.create_gitignore()
        self.create_readme()
        self.create_github_actions_workflow()
        self.create_destroy_config()
        self.create_terraform_template()
