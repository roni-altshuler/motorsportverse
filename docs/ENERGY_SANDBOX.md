# Educational energy sandbox

The proposed F1 `/circuits#energy-sandbox` section is an original, browser-local
educational energy reservoir. It is separate from the existing capture workspace
and never reads a capture, telemetry, circuit, result or prediction artifact.
Its synthetic values are assumptions, not vehicle specifications or measured
performance. No race-prediction or model-accuracy claim follows from this feature.

## Inputs and fixed cycle

| Assumption             | Allowed range | Default | Meaning                                     |
| ---------------------- | ------------- | ------- | ------------------------------------------- |
| Usable capacity        | 0.5–20 kWh    | 4 kWh   | Upper stored-energy bound                   |
| Starting charge        | 0–100%        | 70%     | Initial stored energy divided by capacity   |
| Deployment output      | 0–200 kW      | 60 kW   | Requested energy output after conversion    |
| Available regeneration | 0–150 kW      | 50 kW   | Fictional incoming energy before conversion |
| Conversion efficiency  | 50–100%       | 90%     | Fixed, identical in each direction          |

Each fictional 60-second cycle deploys for 30 seconds, coasts for 10 seconds and
regenerates for 20 seconds. Six repeats give 360 seconds. The original simulation
uses one-second intervals; there is no playback timer, animation or real circuit
trace. Coasting has no loads. Decimal inputs are allowed; blank, nonfinite and
out-of-range values hide results until corrected. Reset restores the defaults.

SoC in this sandbox is an **energy-based proxy**:
`SoC (%) = 100 × stored energy (kWh) / usable capacity (kWh)`.
There is no voltage/current relationship, coulomb counting, temperature, cooling,
resistance, degradation, speed or regulatory model. Conversion losses are energy
only; the code does not derive a temperature from them. Real battery state
estimation needs information this model does not have. See
[MathWorks' battery-management overview](https://www.mathworks.com/discovery/battery-management-system.html).

## Energy accounting

Power in kW multiplied by duration in seconds, divided by 3,600, gives kWh.
Let efficiency be `η`, capacity be `C` and stored energy be `E`.

- Deploy: requested output `D = Pdeploy × Δt / 3600`; actual draw
  `A = min(E, D / η)`; delivered output `A × η`; loss `A × (1 − η)`;
  unmet demand `D − A × η`. The reservoir loses `A`.
- Regenerate: available incoming energy `R = Pregen × Δt / 3600`;
  recovered storage `S = min(C − E, R × η)`; accepted input `S / η`;
  loss `S / η − S`; rejected input `R − S / η`. The reservoir gains `S`.

Rejected input bypasses conversion; it causes no modeled conversion loss.
Unmet deployment demand is a shortfall, not an actual energy flow. Two identities
are tested independently, before display rounding:

```text
initial stored + recovered = final stored + drawn
initial stored + available regeneration = final stored + delivered + losses + rejected
```

The default supplies 3 kWh deployment, draws 3⅓ kWh, receives 1⅔ kWh incoming,
recovers 1.5 kWh and loses 0.5 kWh in conversion. Starting at 2.8 kWh leaves
29/30 kWh, or approximately 24.2% charge. No transfer is curtailed. The UI reports
empty/full constraints and the ledger's floating-point balance residual.

## Learning-resource provenance

The inspiration was a course recommendation, not a repository or a telemetry API.
Only original code and existing locked dependencies are used. These official
resources are outbound links; no course text, media, exercises or MATLAB runtime
are copied, installed or embedded:

- [MATLAB Onramp](https://matlabacademy.mathworks.com/details/matlab-onramp/gettingstarted), approximately 2 hours.
- [Simulink Onramp](https://matlabacademy.mathworks.com/details/simulink-onramp/simulink), approximately 2 hours.
- [Simscape Battery Onramp](https://matlabacademy.mathworks.com/details/simscape-battery-onramp/orsb), approximately 1 hour; start with Simulink and
  [Simscape Onramp](https://matlabacademy.mathworks.com/details/simscape-onramp/simscape).

Course durations and prerequisite recommendations were supplied with the task and
are approximate; the provider may change them. The official detail pages and
[MathWorks online-course FAQ](https://www.mathworks.com/learn/training/online-courses-faq.html)
were checked on 9 October 2026. The FAQ confirms free Onramps and the MathWorks
account requirement. No course-asset redistribution license was verified.

## Verification

[Browser evidence and screenshots](qa/energy-sandbox/README.md) record the exact
source hashes, production export and desktop/mobile journeys. Numerical tests
cover analytical defaults, coasting, empty/full storage, lossless conversion,
recovery after depletion, decimal/invalid inputs and conservation across 720
bounded scenarios. The component tests cover recalculation, hidden invalid
results, reset, chart descriptions and official learning links.

No source/model data, dependency versions, workflows, shared UI copies or
deployment settings change. Existing unmerged work and the laptop-only unpublished
weekend-navigation branch remain separate.
