-- V1: Criação da estrutura inicial de tabelas para o projeto Cortexa
-- Data: 03 de Setembro de 2025
-- Autor: Cortexa Team

-- PASSO 1: Habilitar a extensão pg_vector
-- Esta extensão é fundamental para o armazenamento e a busca de embeddings vetoriais.
CREATE EXTENSION IF NOT EXISTS vector;

-- PASSO 2: Criar a tabela para gerenciar as bases de conhecimento (tenants)
-- Cada entrada nesta tabela representa uma base de conhecimento isolada para um usuário.
CREATE TABLE knowledge_bases (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    user_id UUID NOT NULL, -- Referência ao dono da base de conhecimento
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- PASSO 3: Criar a tabela principal para os chunks de dados e seus vetores
-- Esta é a tabela principal onde os pedaços de texto e seus vetores correspondentes são armazenados.
CREATE TABLE knowledge_chunks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    knowledge_base_id UUID NOT NULL REFERENCES knowledge_bases(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    embedding VECTOR(1536) NOT NULL, -- A dimensão corresponde ao modelo text-embedding-3-small da OpenAI
    metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- PASSO 4: Criar um índice para acelerar a busca por similaridade
-- Um índice IVFFlat é um bom ponto de partida para otimizar a performance
-- das buscas vetoriais. O número de listas (lists) pode ser ajustado
-- conforme o volume de dados aumenta.
CREATE INDEX ON knowledge_chunks USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);

-- PASSO 5 (Opcional, mas recomendado): Tabela para rastrear migrações
-- Esta tabela simples ajuda a evitar que o mesmo script de migração seja executado mais de uma vez.
CREATE TABLE IF NOT EXISTS schema_migrations (
    version VARCHAR(255) PRIMARY KEY,
    applied_at TIMESTAMPTZ DEFAULT NOW()
);

-- Registra que esta migração (versão '1') foi aplicada com sucesso.
INSERT INTO schema_migrations (version) VALUES ('1');