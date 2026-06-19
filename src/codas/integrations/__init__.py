"""Platform Role Integrations: enforcement gates that invoke ``codas check``.

Per the §11 boundary these mappings shell out to the ``codas`` CLI (they render hook /
workflow bodies and install them); they do not import the correctness core, so the
engine stays adapter/integration-agnostic.
"""
