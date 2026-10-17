# Benchmark V2 RQ3 generation-analysis gate deviation

Date: 2026-10-14

## Frozen protocol context

The frozen RQ3 protocol specified that answer content should not be inspected or analyzed until all three model-generation outputs had been completed and hashed.

## Deviation

After the Qwen generation output had been completed and frozen, an exploratory diagnostic inspection of Qwen answer content was performed before the remaining model generations were complete. After the Ministral output had also been completed and hashed, a comparable exploratory automated diagnostic was performed before Gemma generation was complete.

These diagnostics were not the frozen primary RQ3 endpoint and did not constitute the preregistered blinded ordinal semantic judging.

## Scientific configuration

No retrieval profile, top-k setting, query set, frozen evidence context, prompt, decoding parameter, seed, model selection, model weight, GGUF hash, input artifact, protocol artifact, or planned primary endpoint was changed in response to the exploratory inspection.

Gemma had already been selected and its GGUF hash and generation configuration had been frozen before these inspections. No additional model was added or removed.

## Mitigation

From this point until all three model-generation outputs are complete and hashed, no further answer-content inspection or answer-drift analysis will be performed.

The formal RQ3 analysis will use a deterministically generated blinded A/B judging package built only after all three raw outputs are frozen. Profile identity will remain hidden during semantic judging. The preregistered Qwen ordinal material-answer-change endpoint remains primary. Cross-model results remain secondary replication analyses.

The exploratory token-overlap and correlation diagnostics observed before Gemma completion will be treated only as non-primary diagnostics and will not replace or redefine the frozen analysis plan.

## Assessment

This is a procedural analysis-gate deviation, not a change to the scientific intervention or generation configuration. It is recorded explicitly for provenance and reproducibility.
