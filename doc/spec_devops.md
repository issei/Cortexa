# Prompt para Workflow de CI/CD com GitHub Actions e Terraform

## Objetivo

Este documento fornece um prompt detalhado e otimizado para ser usado por um assistente de IA (como o Jules.Google) para gerar o arquivo de workflow do GitHub Actions. O objetivo é criar um pipeline de CI/CD seguro e automatizado para fazer o deploy das funções Lambda do projeto Cortexa na AWS, utilizando Terraform para gerenciamento da infraestrutura como código (IaC).

---

## O Prompt

> ### Persona
>
> Você é um engenheiro de DevOps/Plataforma sênior, especialista em automação de CI/CD com GitHub Actions e Infraestrutura como Código com Terraform para a nuvem AWS. Sua prioridade é criar pipelines que sejam seguros, eficientes e sigam as melhores práticas da indústria, como a autenticação sem chaves de acesso de longa duração.
>
> ### Contexto
>
> Estamos trabalhando no projeto **Cortexa**, hospedado no repositório **[https://github.com/issei/Cortexa](https://github.com/issei/Cortexa)**. O objetivo é automatizar o deploy de três funções Lambda em Python: `ingest_function`, `query_function` e `openai-embedding-proxy`.
>
> A estrutura de diretórios do projeto é a seguinte:
>
> ```
> .
> ├── .github/
> │   └── workflows/
> │       └── deploy.yml  <-- Arquivo que você vai criar
> ├── src/
> │   ├── ingest_function/
> │   │   └── main.py
> │   ├── query_function/
> │   │   └── main.py
> │   └── openai_embedding_proxy/
> │       └── main.py
> ├── terraform/
> │   ├── main.tf         <-- Define a infraestrutura (Lambdas, API Gateway, Roles)
> │   ├── variables.tf
> │   └── outputs.tf
> └── .gitignore
> ```
>
> A configuração do Terraform (`terraform/main.tf`) irá definir os recursos da AWS. É crucial que o Terraform crie os pacotes `.zip` das funções Lambda a partir dos diretórios em `src/` antes de fazer o deploy.
>
> ### Tarefa
>
> Crie um workflow completo do GitHub Actions em um único arquivo YAML (`.github/workflows/deploy.yml`). O workflow deve ter dois gatilhos (triggers) principais, com lógicas distintas para cada um.
>
> #### 1. Trigger: Em Pull Requests para a branch `main`
>
> Este job deve apenas **validar** as mudanças, sem aplicar nada.
>
> * **Nome do Job:** `validate_terraform`
> * **Passos (Steps):**
>   1.  Fazer o checkout do código do repositório.
>   2.  Configurar as credenciais da AWS de forma segura usando **OIDC**. O rol de IAM para este passo deve ter permissões de **apenas leitura**.
>   3.  Instalar a versão desejada do Terraform (ex: 1.8.x).
>   4.  Navegar para o diretório `terraform/`.
>   5.  Executar `terraform fmt -check` para garantir que o código está formatado.
>   6.  Executar `terraform init` para inicializar o backend.
>   7.  Executar `terraform validate` para verificar a sintaxe.
>   8.  Executar `terraform plan` para gerar um plano de mudanças. O resultado do plano deve ser visível nos logs do workflow para revisão.
>
> #### 2. Trigger: Em Push para a branch `main` (após o merge de um PR)
>
> Este job deve **construir os pacotes e aplicar** as mudanças na AWS.
>
> * **Nome do Job:** `build_and_deploy`
> * **Passos (Steps):**
>   1.  Fazer o checkout do código do repositório.
>   2.  Configurar as credenciais da AWS de forma segura usando **OIDC**. O rol de IAM para este passo deve ter **permissões de escrita** para criar/atualizar os recursos (Lambda, API Gateway, etc.).
>   3.  Instalar a versão desejada do Terraform.
>   4.  **Construir os pacotes das Lambdas:**
>       * Para cada função em `src/` (`ingest_function`, `query_function`, `openai_embedding_proxy`):
>       * Criar um arquivo `.zip` contendo o `main.py` de cada uma.
>       * Mover os arquivos `.zip` gerados para o diretório `terraform/` para que o Terraform possa encontrá-los.
>   5.  Navegar para o diretório `terraform/`.
>   6.  Executar `terraform init`.
>   7.  Executar `terraform apply -auto-approve` para aplicar as mudanças de infraestrutura e fazer o deploy das novas versões das Lambdas.
>
> ### Requisitos e Boas Práticas
>
> 1.  **Autenticação Segura (OIDC):** A autenticação com a AWS **DEVE** ser feita via OIDC, usando a action `aws-actions/configure-aws-credentials`. Não use chaves de acesso AWS (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`) de longa duração. O ARN do rol de IAM a ser assumido deve ser armazenado em um secret do GitHub chamado `AWS_ROLE_ARN`.
> 2.  **Estado do Terraform:** O workflow deve ser compatível com um backend remoto para o estado do Terraform (ex: S3 + DynamoDB). O `terraform init` deve ser configurado para tal.
> 3.  **Reutilização:** Utilize actions populares e bem mantidas do GitHub Marketplace (ex: `actions/checkout@v4`, `hashicorp/setup-terraform@v3`, `aws-actions/configure-aws-credentials@v4`).
> 4.  **Clareza:** O arquivo YAML deve ser bem comentado, explicando o propósito de cada job e de cada step principal.
> 5.  **Variáveis de Ambiente:** Configure variáveis de ambiente no workflow (seção `env:`) para valores como `AWS_REGION`.
>
> ### Output Esperado
>
> Um único arquivo de código YAML, chamado `deploy.yml`, que implementa completamente o workflow de CI/CD descrito acima.

---

### Por que usar um prompt detalhado?

Para automação de infraestrutura, os detalhes são cruciais. Este prompt especifica:
- **A estratégia de segurança (OIDC):** A forma mais segura de integrar GitHub e AWS.
- **A lógica de separação (PR vs. Merge):** Essencial para um fluxo de trabalho seguro, onde as mudanças são validadas antes de serem aplicadas.
- **O passo de build:** Muitas vezes esquecido, é fundamental instruir a IA sobre como os artefatos de software (os `.zip` das Lambdas) devem ser construídos antes do deploy.
- **A estrutura do projeto:** Dá ao assistente o contexto exato de onde encontrar os arquivos, resultando em um script mais preciso.

Isso guia a IA a produzir um workflow que não apenas funciona, mas é seguro, robusto e segue os padrões modernos de DevOps.