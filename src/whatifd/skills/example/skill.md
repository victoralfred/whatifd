---
name: example 
description: "Stub scorer demonstrating the skill template round-trip."
version: "0.1"
kind: scorer
parameters:
 - name: constant_score
   type: float
   required: false 
   default: "0.5"
   description: "Score returned for every trace (demonstration only - not for production use)."

---

## What this skill does 

A constant-return scorer for demonstration purposes only. 
It returns a fixed score for every trace, regardless of the input. 
Every trace receives the same score, which is configurable via the `constant_score` parameter.
This skill is intended for testing and validation of the skill framework, not for actual use in production environments.


## Implementation notes 

To produce a real score from this template: 
1. Replace `constant_score` with your actual model/rubric parameters. 
2. Implement `score()` to call your judge model and return a `JudgeResult`.
3. Implement `cache_key_components()` to return a `CacheKeyComponents` 
   that uniquely identifies the scoring call.
4. Wrap any user-content fields in `Sensitive[T]` before returning them (cardinal #5).


