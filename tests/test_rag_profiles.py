from app.config import Settings
from app.rag.profiles import (
    DEFAULT_RETRIEVAL_PROFILE_ID,
    builtin_retrieval_profiles,
    get_retrieval_profile,
    settings_for_profile,
)


def test_builtin_retrieval_profiles_have_unique_ids_and_hashes() -> None:
    profiles = builtin_retrieval_profiles()

    assert {profile.profile_id for profile in profiles} == {
        "lexical-v1",
        "vector-e5-content-v1",
        "hybrid-e5-content-v1",
        "vector-e5-metadata-v1",
        "hybrid-e5-metadata-v1",
    }
    assert len({profile.config_hash for profile in profiles}) == len(profiles)
    assert DEFAULT_RETRIEVAL_PROFILE_ID == "hybrid-e5-content-v1"


def test_profile_settings_freeze_embedding_and_fusion_configuration() -> None:
    base = Settings(
        rag_embedding_provider="feature-hash",
        rag_embedding_model="feature-hash-384-v1",
        rag_embedding_input_profile="content-v1",
        rag_hybrid_rrf_k=99,
        rag_source_diversity_max_per_file=9,
    )
    profile = get_retrieval_profile("hybrid-e5-metadata-v1")
    resolved = settings_for_profile(base, profile)

    assert resolved.rag_embedding_provider == "multilingual-e5"
    assert resolved.rag_embedding_model == "intfloat/multilingual-e5-small"
    assert resolved.rag_embedding_input_profile == "metadata-v1"
    assert resolved.rag_embedding_dimensions == 384
    assert resolved.rag_hybrid_rrf_k == 60
    assert resolved.rag_source_diversity_max_per_file == 2


def test_content_and_metadata_profiles_are_distinct_retrieval_artifacts() -> None:
    content = get_retrieval_profile("hybrid-e5-content-v1")
    metadata = get_retrieval_profile("hybrid-e5-metadata-v1")

    assert content.embedding_model == metadata.embedding_model
    assert content.embedding_input_profile == "content-v1"
    assert metadata.embedding_input_profile == "metadata-v1"
    assert content.config_hash != metadata.config_hash
