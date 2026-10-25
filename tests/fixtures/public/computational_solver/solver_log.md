# Synthetic solver log - fixture corpus

SYNTHETIC MATERIAL - authored for the LabCairn public fixture corpus.
The solver, the mesh and every number below are invented for testing.
Nothing here was computed by a real program, and no result here is a
result about any real problem.

## Configuration

The synthetic problem was solved on a uniform mesh of 64 cells with a
fixed time step of 0.01 s. The stopping tolerance on the residual was
1.0e-8.

## Runs

Five synthetic runs were performed. The per-run iterations and final
residual are tabulated in solver_runs.csv, one row per run.

## What is reported

The final residual of a run is the residual on its last iteration.
The mean final residual over the five runs is the quantity the
accompanying question asks for.
