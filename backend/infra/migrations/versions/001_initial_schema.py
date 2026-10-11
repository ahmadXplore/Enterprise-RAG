"""Initial relational schema and seed roles

Revision ID: 001_initial_schema
Revises: 
Create Date: 2026-09-22 15:30:00.000000

"""
import uuid
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import table, column
from apps.api.app.models.types import GUID, CompatibleJSONB

revision: str = "001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. users
    op.create_table(
        "users",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("email", sa.String(255), unique=True, nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("full_name", sa.String(255), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("idx_users_email", "users", ["email"])

    # 2. roles
    op.create_table(
        "roles",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("name", sa.String(50), unique=True, nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
    )
    op.create_index("idx_roles_name", "roles", ["name"])

    # 3. user_roles
    op.create_table(
        "user_roles",
        sa.Column("user_id", GUID(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("role_id", GUID(), sa.ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
    )

    # 4. documents
    op.create_table(
        "documents",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("source_type", sa.String(50), nullable=False),
        sa.Column("document_type", sa.String(50), nullable=False),
        sa.Column("organization", sa.String(255), nullable=True),
        sa.Column("ticker", sa.String(20), nullable=True),
        sa.Column("report_year", sa.Integer(), nullable=True),
        sa.Column("source_uri", sa.Text(), nullable=True),
        sa.Column("content_hash", sa.String(64), unique=True, nullable=False),
        sa.Column("language", sa.String(20), server_default="en", nullable=True),
        sa.Column("status", sa.String(50), server_default="registered", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("idx_documents_org_year", "documents", ["organization", "report_year"])
    op.create_index("idx_documents_type", "documents", ["document_type"])
    op.create_index("idx_documents_hash", "documents", ["content_hash"])

    # 5. document_versions
    op.create_table(
        "document_versions",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("document_id", GUID(), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version_label", sa.String(50), server_default="v1.0", nullable=True),
        sa.Column("source_file_path", sa.Text(), nullable=True),
        sa.Column("file_name", sa.Text(), nullable=True),
        sa.Column("mime_type", sa.String(100), nullable=True),
        sa.Column("file_size", sa.BigInteger(), nullable=True),
        sa.Column("parser_name", sa.String(50), nullable=True),
        sa.Column("parser_version", sa.String(50), nullable=True),
        sa.Column("parse_status", sa.String(50), server_default="pending", nullable=True),
        sa.Column("page_count", sa.Integer(), nullable=True),
        sa.Column("checksum", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("idx_doc_versions_doc_id", "document_versions", ["document_id"])

    # 6. document_sections
    op.create_table(
        "document_sections",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("document_version_id", GUID(), sa.ForeignKey("document_versions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("parent_section_id", GUID(), sa.ForeignKey("document_sections.id", ondelete="CASCADE"), nullable=True),
        sa.Column("heading", sa.Text(), nullable=True),
        sa.Column("heading_level", sa.Integer(), nullable=True),
        sa.Column("section_order", sa.Integer(), nullable=True),
        sa.Column("page_start", sa.Integer(), nullable=True),
        sa.Column("page_end", sa.Integer(), nullable=True),
        sa.Column("path", sa.Text(), nullable=True),
        sa.Column("metadata", CompatibleJSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("idx_sections_version_id", "document_sections", ["document_version_id"])
    op.create_index("idx_sections_parent_id", "document_sections", ["parent_section_id"])

    # 7. document_chunks
    op.create_table(
        "document_chunks",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("document_version_id", GUID(), sa.ForeignKey("document_versions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("section_id", GUID(), sa.ForeignKey("document_sections.id", ondelete="SET NULL"), nullable=True),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("chunk_type", sa.String(50), server_default="paragraph", nullable=True),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=True),
        sa.Column("page_start", sa.Integer(), nullable=True),
        sa.Column("page_end", sa.Integer(), nullable=True),
        sa.Column("heading_path", sa.Text(), nullable=True),
        sa.Column("table_html", sa.Text(), nullable=True),
        sa.Column("metadata", CompatibleJSONB(), nullable=True),
        sa.Column("content_hash", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("document_version_id", "chunk_index", name="uq_version_chunk_index"),
    )
    op.create_index("idx_chunks_document", "document_chunks", ["document_version_id"])
    op.create_index("idx_chunks_section", "document_chunks", ["section_id"])

    # 8. document_access
    op.create_table(
        "document_access",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("document_id", GUID(), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", GUID(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=True),
        sa.Column("role_id", GUID(), sa.ForeignKey("roles.id", ondelete="CASCADE"), nullable=True),
        sa.Column("permission", sa.String(50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("idx_doc_access_doc_id", "document_access", ["document_id"])
    op.create_index("idx_doc_access_user_id", "document_access", ["user_id"])
    op.create_index("idx_doc_access_role_id", "document_access", ["role_id"])

    # 9. ingestion_jobs
    op.create_table(
        "ingestion_jobs",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("document_id", GUID(), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("document_version_id", GUID(), sa.ForeignKey("document_versions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("job_type", sa.String(50), nullable=False),
        sa.Column("status", sa.String(50), server_default="queued", nullable=False),
        sa.Column("progress", sa.Integer(), server_default="0", nullable=False),
        sa.Column("current_stage", sa.String(50), server_default="validation", nullable=True),
        sa.Column("retry_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("idx_jobs_status", "ingestion_jobs", ["status"])
    op.create_index("idx_jobs_document", "ingestion_jobs", ["document_id"])

    # 10. conversations
    op.create_table(
        "conversations",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("user_id", GUID(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(255), server_default="New Conversation", nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("idx_conversations_user_id", "conversations", ["user_id"])

    # 11. messages
    op.create_table(
        "messages",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("conversation_id", GUID(), sa.ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("query_type", sa.String(50), nullable=True),
        sa.Column("grounded", sa.Boolean(), nullable=True),
        sa.Column("abstained", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("token_usage", CompatibleJSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("idx_messages_conversation", "messages", ["conversation_id"])

    # 12. message_citations
    op.create_table(
        "message_citations",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("message_id", GUID(), sa.ForeignKey("messages.id", ondelete="CASCADE"), nullable=False),
        sa.Column("chunk_id", GUID(), sa.ForeignKey("document_chunks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("citation_label", sa.String(50), nullable=True),
        sa.Column("page_start", sa.Integer(), nullable=True),
        sa.Column("page_end", sa.Integer(), nullable=True),
        sa.Column("evidence_text", sa.Text(), nullable=True),
        sa.Column("validation_status", sa.String(50), server_default="valid", nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("idx_citations_message_id", "message_citations", ["message_id"])
    op.create_index("idx_citations_chunk_id", "message_citations", ["chunk_id"])

    # 13. queries
    op.create_table(
        "queries",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("user_id", GUID(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("message_id", GUID(), sa.ForeignKey("messages.id", ondelete="CASCADE"), nullable=True),
        sa.Column("raw_query", sa.Text(), nullable=False),
        sa.Column("normalized_query", sa.Text(), nullable=True),
        sa.Column("query_type", sa.String(50), nullable=True),
        sa.Column("filters", CompatibleJSONB(), nullable=True),
        sa.Column("retrieval_config", CompatibleJSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("idx_queries_user", "queries", ["user_id"])
    op.create_index("idx_queries_message", "queries", ["message_id"])

    # 14. retrieval_runs
    op.create_table(
        "retrieval_runs",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("query_id", GUID(), sa.ForeignKey("queries.id", ondelete="CASCADE"), nullable=False),
        sa.Column("dense_results", CompatibleJSONB(), nullable=True),
        sa.Column("sparse_results", CompatibleJSONB(), nullable=True),
        sa.Column("fusion_results", CompatibleJSONB(), nullable=True),
        sa.Column("reranked_results", CompatibleJSONB(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("idx_runs_query_id", "retrieval_runs", ["query_id"])

    # 15. evaluation_sets
    op.create_table(
        "evaluation_sets",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("version", sa.String(50), server_default="1.0", nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    # 16. evaluation_cases
    op.create_table(
        "evaluation_cases",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("evaluation_set_id", GUID(), sa.ForeignKey("evaluation_sets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("expected_answer", sa.Text(), nullable=True),
        sa.Column("query_type", sa.String(50), nullable=True),
        sa.Column("metadata", CompatibleJSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("idx_eval_cases_set_id", "evaluation_cases", ["evaluation_set_id"])

    # 17. evaluation_references
    op.create_table(
        "evaluation_references",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("evaluation_case_id", GUID(), sa.ForeignKey("evaluation_cases.id", ondelete="CASCADE"), nullable=False),
        sa.Column("chunk_id", GUID(), sa.ForeignKey("document_chunks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("relevance_grade", sa.Integer(), server_default="1", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("idx_eval_refs_case_id", "evaluation_references", ["evaluation_case_id"])
    op.create_index("idx_eval_refs_chunk_id", "evaluation_references", ["chunk_id"])

    # 18. evaluation_runs
    op.create_table(
        "evaluation_runs",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("evaluation_set_id", GUID(), sa.ForeignKey("evaluation_sets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("configuration", CompatibleJSONB(), nullable=True),
        sa.Column("status", sa.String(50), server_default="queued", nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("idx_eval_runs_set_id", "evaluation_runs", ["evaluation_set_id"])

    # 19. evaluation_run_results
    op.create_table(
        "evaluation_run_results",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("evaluation_run_id", GUID(), sa.ForeignKey("evaluation_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("evaluation_case_id", GUID(), sa.ForeignKey("evaluation_cases.id", ondelete="CASCADE"), nullable=False),
        sa.Column("retrieved_chunk_ids", CompatibleJSONB(), nullable=True),
        sa.Column("answer", sa.Text(), nullable=True),
        sa.Column("recall_at_k", CompatibleJSONB(), nullable=True),
        sa.Column("mrr", sa.Float(), nullable=True),
        sa.Column("ndcg_at_k", CompatibleJSONB(), nullable=True),
        sa.Column("answer_relevance", sa.Float(), nullable=True),
        sa.Column("groundedness", sa.Float(), nullable=True),
        sa.Column("citation_accuracy", sa.Float(), nullable=True),
        sa.Column("abstention_correct", sa.Boolean(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("idx_eval_results_run_id", "evaluation_run_results", ["evaluation_run_id"])
    op.create_index("idx_eval_results_case_id", "evaluation_run_results", ["evaluation_case_id"])

    # 20. audit_logs
    op.create_table(
        "audit_logs",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("user_id", GUID(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("resource_type", sa.String(50), nullable=False),
        sa.Column("resource_id", GUID(), nullable=True),
        sa.Column("ip_hash", sa.String(64), nullable=True),
        sa.Column("metadata", CompatibleJSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("idx_audit_created", "audit_logs", ["created_at"])
    op.create_index("idx_audit_user_id", "audit_logs", ["user_id"])

    # Seed default roles: ADMIN, ANALYST, VIEWER
    roles_table = table(
        "roles",
        column("id", GUID()),
        column("name", sa.String),
        column("description", sa.Text),
    )
    op.bulk_insert(
        roles_table,
        [
            {
                "id": uuid.uuid4(),
                "name": "ADMIN",
                "description": "Full administrative access: register documents, run evaluations, manage users.",
            },
            {
                "id": uuid.uuid4(),
                "name": "ANALYST",
                "description": "Search documents, ask questions, inspect citations, compare documents.",
            },
            {
                "id": uuid.uuid4(),
                "name": "VIEWER",
                "description": "Read-only access to search and view permitted documents and citations.",
            },
        ],
    )


def downgrade() -> None:
    op.drop_table("audit_logs")
    op.drop_table("evaluation_run_results")
    op.drop_table("evaluation_runs")
    op.drop_table("evaluation_references")
    op.drop_table("evaluation_cases")
    op.drop_table("evaluation_sets")
    op.drop_table("retrieval_runs")
    op.drop_table("queries")
    op.drop_table("message_citations")
    op.drop_table("messages")
    op.drop_table("conversations")
    op.drop_table("ingestion_jobs")
    op.drop_table("document_access")
    op.drop_table("document_chunks")
    op.drop_table("document_sections")
    op.drop_table("document_versions")
    op.drop_table("documents")
    op.drop_table("user_roles")
    op.drop_table("roles")
    op.drop_table("users")
