"""The roles of the guidance loop, under contracts the code enforces.

LC-P2-12. A role is not a prompt: it works under a contract that is a
row (ADR-0018 D1) — the objective, the typed input and output schemas,
the capabilities it may exercise, the actions it may not take, the data
purposes, the budgets and the routing, the abstain and escalation
conditions — and the prompt is one field of it, the least load-bearing
one. The contract as data is :mod:`labcairn.roles.spec`; the three
roles themselves are the work order's later subtasks.
"""
