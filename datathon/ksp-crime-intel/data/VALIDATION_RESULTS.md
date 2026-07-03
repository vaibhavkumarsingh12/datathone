# Phase 6 Validation Results
*Generated for KSP Datathon 2026 Synthetic Data*

```text
Loading data...
============================================================
✅ PASS  T1 · FK integrity
        → orphan FKs: 0, accused rows missing from answer key: 0 (need 0 & 0)
✅ PASS  T2 · No identity leak in public Accused.csv
        → suspicious columns: none; PersonID is A1/A2-style labels only: True
✅ PASS  T3 · Name pool (collision fix)
        → 4012 distinct canonical names for 12000 people (worst collision: 'umesh devadiga' ×12; need ≥2500 distinct)
✅ PASS  T4 · FatherName field (second resolution key)
        → in PersonMaster: True, in Accused: True, filled: 85% (need >70%)
✅ PASS  T5 · Offender population structure
        → types: {'oneoff': 11723, 'repeat': 249, 'ring': 28} | non-ring people with 2+ cases NOT in repeat pool: 0 (need ≈0; ≤187 tolerated)
✅ PASS  T6 · Ring realism (turf + workload)
        → Ring 1: co-cases 33 (≥15), max cases/member 17 (≤30), in-turf 76% (≥60%) 
        → Ring 2: co-cases 50 (≥15), max cases/member 25 (≤30), in-turf 90% (≥60%) 
        → Ring 3: co-cases 38 (≥15), max cases/member 18 (≤30), in-turf 79% (≥60%) 
        → Ring 4: co-cases 35 (≥15), max cases/member 23 (≤30), in-turf 63% (≥60%)

Running entity-resolution simulation (30-60s)...
✅ PASS  T7 · Entity resolution recoverability
        → precision 0.882 · recall 0.929 · F1 0.905 (need F1 ≥ 0.80; 0.85+ is your demo-slide number)
✅ PASS  T8 · Gang recovery after resolution
        → 4/4 rings survive resolution well enough for graph detection (need all)
✅ PASS  T9 · Planted hotspots intact
        → d1/s203: 220 cases, std 0.0116 | d3/s204: 160 cases, std 0.0111 | d8/s205: 120 cases, std 0.0115 (need std<0.05, n≥80)
✅ PASS  T10 · Planted spikes intact
        → d5/s601: peak 2024-11 = 150 vs median 9 (×16.7) | d14/s202: peak 2025-06 = 147 vs median 32 (×4.5) (need peak ≥3× median)

============================================================
SCORECARD: 10/10 passed
  ✅ PASS  T1 · FK integrity
  ✅ PASS  T2 · No identity leak in public Accused.csv
  ✅ PASS  T3 · Name pool (collision fix)
  ✅ PASS  T4 · FatherName field (second resolution key)
  ✅ PASS  T5 · Offender population structure
  ✅ PASS  T6 · Ring realism (turf + workload)
  ✅ PASS  T7 · Entity resolution recoverability
  ✅ PASS  T8 · Gang recovery after resolution
  ✅ PASS  T9 · Planted hotspots intact
  ✅ PASS  T10 · Planted spikes intact

🎉 ALL GREEN — the data layer is DONE. Save this output; T7's F1 number
   goes straight onto your demo slide. Next stop: Module 1 (geo-hotspots).
```
