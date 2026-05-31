CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Системы (проекты аттестации)
CREATE TABLE systems (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(500) NOT NULL,
    classification_level VARCHAR(50) NOT NULL,  -- "1Г", "КЗ-1", "УЗ-1"
    description TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Компоненты системы
CREATE TABLE system_components (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    system_id UUID REFERENCES systems(id) ON DELETE CASCADE,
    component_name VARCHAR(300) NOT NULL,
    component_type VARCHAR(100),               -- "ОС", "СКЗИ", "СОВ", "СЗИ НСД"
    certificate_number VARCHAR(200),
    certificate_valid_until DATE,
    current_configuration JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Требования НПА (заполняется из ChromaDB + валидация)
CREATE TABLE npa_requirements (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source_document VARCHAR(500) NOT NULL,
    paragraph_id VARCHAR(50),
    requirement_text TEXT NOT NULL,
    class_relevance JSONB,                     -- ["1Г", "КЗ-1"]
    embedding vector(1024),
    metadata JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX ON npa_requirements USING ivfflat (embedding vector_cosine_ops);

-- Аудит-трейл
CREATE TABLE audit_trail (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    system_id UUID REFERENCES systems(id) ON DELETE CASCADE,
    requirement_id UUID REFERENCES npa_requirements(id) ON DELETE CASCADE,
    component_id UUID REFERENCES system_components(id) ON DELETE CASCADE,
    iteration INTEGER DEFAULT 1,
    
    status VARCHAR(50) CHECK (status IN (
        'NOT_CHECKED', 'COMPLIANT', 'NON_COMPLIANT',
        'NEED_MORE_INFO', 'HUMAN_OVERRIDE', 'WAIVED'
    )),
    
    ai_assessment JSONB,
    ai_recommendation TEXT,
    
    human_decision VARCHAR(50) CHECK (human_decision IN ('APPROVED', 'REJECTED', 'MODIFIED', NULL)),
    human_comment TEXT,
    expert_name VARCHAR(200),
    
    final_resolution TEXT,
    resolution_evidence TEXT,
    
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_audit_system ON audit_trail(system_id);
CREATE INDEX idx_audit_status ON audit_trail(status);
CREATE INDEX idx_npa_class ON npa_requirements USING gin(class_relevance);
