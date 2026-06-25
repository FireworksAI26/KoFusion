# KovaFusion Evaluation Report

This lightweight local report is generated without Cloudflare credentials. The pytest suite provides the mocked evaluation harness for adaptive-conductor behavior.

| metric | value | notes |
| --- | ---: | --- |
| avg internal steps | 5.0 | easy-task path: plan → spawn → verify → synthesize → stop |
| avg models called | 2.0 | thinker plus first cheap worker; no fixed three-model fanout |
| pass@1 | 1.00 | mocked easy verifiable task passes on first candidate |
| $/solved estimate | $0.11 | coarse governor estimate from `COST_ESTIMATES_USD` |

## Expected efficiency signal

The adaptive conductor stops early when a cheap worker passes, avoiding the previous fixed three-model fanout on easy verifiable tasks while preserving escalation for failures.
